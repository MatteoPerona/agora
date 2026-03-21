from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from oasis import ActionType, AgentGraph, SocialAgent, UserInfo, make
from oasis.social_agent.agents_generator import connect_platform_channel
from oasis.social_platform.channel import Channel

from ..models import Persona
from .platform import DeliberationPlatform
from .prompts import PERSONA_TEMPLATE
from .provider import SimulationProviderFactory

MODERATOR_AGENT_ID = 0


@dataclass
class RuntimeParticipant:
    persona: Persona
    agent_id: int
    agent: SocialAgent


class OasisDeliberationRuntime:
    def __init__(
        self,
        *,
        provider_factory: SimulationProviderFactory,
        decision: str,
        personas: list[tuple[int, Persona]],
        document_context: str,
        db_path: str,
    ):
        self.provider_factory = provider_factory
        self.decision = decision
        self.document_context = document_context
        self.db_path = db_path
        self.channel = Channel()
        self.platform = DeliberationPlatform(db_path=db_path, channel=self.channel)
        self.agent_graph = AgentGraph()
        self.agent_backend = provider_factory.create_agent_backend()
        self.moderator = self._build_moderator()
        self.agent_graph.add_agent(self.moderator)
        self.participants = [
            RuntimeParticipant(persona=persona, agent_id=agent_id, agent=self._build_participant(agent_id, persona))
            for agent_id, persona in personas
        ]
        for participant in self.participants:
            self.agent_graph.add_agent(participant.agent)
        self.env = make(
            agent_graph=self.agent_graph,
            platform=self.platform,
            database_path=self.db_path,
            semaphore=provider_factory.settings.sim_max_concurrency,
        )

    async def start_new(self) -> None:
        await self.env.reset()

    async def attach_existing(self) -> None:
        self.env.platform_task = asyncio.create_task(self.platform.running())
        self.agent_graph = connect_platform_channel(channel=self.channel, agent_graph=self.agent_graph)

    async def close(self) -> None:
        await self.env.close()

    async def create_room(self, room_name: str) -> int:
        result = await self.moderator.perform_action_by_data(ActionType.CREATE_GROUP, group_name=room_name)
        if not result.get("success"):
            raise RuntimeError(f"Failed to create OASIS group: {result}")
        group_id = int(result["group_id"])
        for participant in self.participants:
            join_result = await participant.agent.perform_action_by_data(ActionType.JOIN_GROUP, group_id=group_id)
            if not join_result.get("success"):
                raise RuntimeError(f"Failed to join OASIS group for {participant.persona.id}: {join_result}")
        return group_id

    async def send_moderator_message(self, *, group_id: int, content: str) -> None:
        result = await self.moderator.perform_action_by_data(ActionType.SEND_TO_GROUP, group_id=group_id, message=content)
        if not result.get("success"):
            raise RuntimeError(f"Moderator send failed: {result}")

    async def send_participant_message(self, *, agent_id: int, group_id: int, content: str) -> None:
        agent = self._participant_by_agent_id(agent_id).agent
        result = await agent.perform_action_by_data(ActionType.SEND_TO_GROUP, group_id=group_id, message=content)
        if not result.get("success"):
            raise RuntimeError(f"Participant send failed for {agent_id}: {result}")

    async def interview(self, *, agent_id: int, prompt: str) -> str:
        agent = self._agent_for_interview(agent_id)
        response = await agent.perform_interview(prompt)
        return str(response["content"])

    async def room_context(self, *, agent_id: int) -> str:
        agent = self._agent_for_interview(agent_id)
        return await agent.env.get_group_env()

    def _participant_by_agent_id(self, agent_id: int) -> RuntimeParticipant:
        for participant in self.participants:
            if participant.agent_id == agent_id:
                return participant
        raise ValueError(f"Unknown participant agent id {agent_id}.")

    def _agent_for_interview(self, agent_id: int) -> SocialAgent:
        if agent_id == MODERATOR_AGENT_ID:
            return self.moderator
        return self._participant_by_agent_id(agent_id).agent

    def _build_moderator(self) -> SocialAgent:
        user_info = UserInfo(
            user_name="deliberation-engine",
            name="Deliberation Engine",
            description="System moderator for a structured panel simulation.",
            profile={"other_info": {"user_profile": "System moderator"}},
            recsys_type="twitter",
        )
        return SocialAgent(
            agent_id=MODERATOR_AGENT_ID,
            user_info=user_info,
            channel=self.channel,
            agent_graph=self.agent_graph,
            available_actions=[
                ActionType.CREATE_GROUP,
                ActionType.SEND_TO_GROUP,
                ActionType.JOIN_GROUP,
                ActionType.LISTEN_FROM_GROUP,
                ActionType.DO_NOTHING,
            ],
            model=self.agent_backend,
        )

    def _build_participant(self, agent_id: int, persona: Persona) -> SocialAgent:
        user_info = UserInfo(
            user_name=persona.id,
            name=persona.name,
            description=persona.summary,
            recsys_type="twitter",
            profile={
                "persona_name": persona.name,
                "summary": persona.summary,
                "identity_anchor": persona.identity_anchor,
                "epistemic_style": persona.epistemic_style,
                "argumentative_voice": persona.argumentative_voice,
                "cognitive_biases": ", ".join(
                    f"{bias.type} ({bias.strength})" for bias in persona.cognitive_biases
                ),
                "opinion_change_threshold": persona.opinion_change_threshold,
                "decision": self.decision,
                "document_context": self.document_context or "No documents attached.",
            },
        )
        return SocialAgent(
            agent_id=agent_id,
            user_info=user_info,
            user_info_template=PERSONA_TEMPLATE,
            channel=self.channel,
            model=self.agent_backend,
            agent_graph=self.agent_graph,
            available_actions=[
                ActionType.SEND_TO_GROUP,
                ActionType.LISTEN_FROM_GROUP,
                ActionType.DO_NOTHING,
            ],
        )
