from __future__ import annotations

from collections import Counter, defaultdict
import logging
import random
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (
    ContributionPayload,
    CreateSessionRequest,
    DecisionBriefPayload,
    NetworkEdge,
    Persona,
    PersonaStance,
    SessionEvent,
    SessionSnapshot,
    StanceInterviewPayload,
    TrajectoryPoint,
    TrajectorySeries,
    UserReasoningProfile,
)
from ..repository import AppRepository, message_from_entity, persona_from_entity
from ..services.panel import extract_decision_frame, stance_label
from .prompts import (
    ROUND_CUES,
    build_brief_prompt,
    build_contribution_prompt,
    build_initial_stance_prompt,
    build_opening_system_message,
    build_round_stance_prompt,
)
from .provider import SimulationProviderFactory, StructuredLLMClient, _extract_json_payload

try:
    from .runtime import OasisDeliberationRuntime
except ImportError:
    OasisDeliberationRuntime = None


T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class SimulationService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.repository = AppRepository(session)
        self.provider_factory = SimulationProviderFactory(settings)

    async def create_session(
        self,
        *,
        request: CreateSessionRequest,
        personas: list[Persona],
        profile: UserReasoningProfile,
        document_context: str,
        document_names: list[str],
    ) -> SessionSnapshot:
        simulation_id = str(uuid4())
        oasis_db_path = str(self.settings.simulations_dir / f"{simulation_id}.db")
        logger.info(
            "Creating simulation %s with %d personas using provider=%s model=%s",
            simulation_id,
            len(request.persona_ids),
            self.settings.normalized_provider,
            self.settings.sim_model,
        )
        frame = extract_decision_frame(f"{request.decision}\n\nSupporting documents:\n{document_context}" if document_context else request.decision)

        persona_entities = self.repository.get_persona_entities(request.persona_ids)
        simulation = self.repository.create_simulation(
            simulation_id=simulation_id,
            decision=request.decision,
            document_ids=request.document_ids,
            document_names=document_names,
            round_goal=request.round_goal,
            oasis_db_path=oasis_db_path,
            decision_frame=frame.model_dump(),
            persona_entities=persona_entities,
        )
        self.repository.increment_persona_usage(request.persona_ids)

        if self._should_use_local_stub_runtime():
            await self._create_stub_session(
                simulation_id=simulation_id,
                simulation=simulation,
                request=request,
                frame=frame.model_dump(),
                document_context=document_context,
                document_names=document_names,
            )
        else:
            await self._create_oasis_session(
                simulation_id=simulation_id,
                simulation=simulation,
                request=request,
                frame=frame.model_dump(),
                document_context=document_context,
                document_names=document_names,
            )

        self.session.commit()
        logger.info("Simulation %s created successfully.", simulation_id)
        return self.get_snapshot(simulation_id)

    def get_snapshot(self, simulation_id: str) -> SessionSnapshot:
        simulation = self.repository.get_simulation(simulation_id)
        roster = [
            PersonaStance(
                persona_id=participant.persona.id,
                persona_name=participant.persona.name,
                avatar_emoji=participant.persona.avatar_emoji,
                stance=round(participant.current_stance or 0.0, 2),
                confidence=round(participant.current_confidence or 0.0, 2),
                label=stance_label(participant.current_stance or 0.0),
                rationale=participant.last_rationale or "Still establishing an opening position.",
            )
            for participant in simulation.participants
        ]

        trajectory_records = self.repository.get_trajectory_metrics(simulation_id)
        grouped: dict[str, list[TrajectoryPoint]] = defaultdict(list)
        for metric in trajectory_records:
            if metric.persona_id is None:
                continue
            grouped[metric.persona_id].append(
                TrajectoryPoint(
                    round_index=metric.round_index or 0,
                    stance=round(metric.numeric_value or 0.0, 2),
                    confidence=round(float((metric.json_value or {}).get("confidence", 0.0)), 2),
                )
            )

        trajectories = [
            TrajectorySeries(
                persona_id=participant.persona.id,
                persona_name=participant.persona.name,
                avatar_emoji=participant.persona.avatar_emoji,
                points=grouped.get(participant.persona.id, []),
            )
            for participant in simulation.participants
        ]

        messages = [message_from_entity(message) for message in simulation.messages]
        brief = self.repository.get_brief(simulation_id)

        return SessionSnapshot(
            session_id=simulation.id,
            decision=simulation.decision,
            current_round=simulation.current_round,
            round_goal=simulation.round_goal,
            status="complete" if simulation.status == "complete" else "running",
            messages=messages,
            roster=roster,
            trajectories=trajectories,
            network_edges=self._build_network([persona_from_entity(participant.persona) for participant in simulation.participants]),
            brief=brief,
        )

    def add_interjection(self, simulation_id: str, content: str) -> SessionSnapshot:
        simulation = self.repository.get_simulation(simulation_id)
        self.repository.add_message(
            simulation_id=simulation_id,
            author_id="user",
            author_name="You",
            avatar_emoji="✍️",
            role="user",
            round_index=simulation.current_round,
            cue="user interjection",
            content=content,
        )
        self.repository.add_pending_interjection(simulation_id, content, simulation.current_round)
        self.session.commit()
        return self.get_snapshot(simulation_id)

    async def advance_session(
        self,
        *,
        simulation_id: str,
        documents: list[str],
    ) -> SessionSnapshot:
        simulation = self.repository.get_simulation(simulation_id)
        if simulation.status == "complete":
            return self.get_snapshot(simulation_id)

        next_round = simulation.current_round + 1
        cue = ROUND_CUES.get(next_round, "deliberation")
        logger.info("Advancing simulation %s to round %d (%s).", simulation_id, next_round, cue)
        self.repository.create_round(simulation_id, next_round, cue)

        if self._should_use_local_stub_runtime():
            await self._advance_stub_session(
                simulation_id=simulation_id,
                simulation=simulation,
                next_round=next_round,
                cue=cue,
                documents=documents,
            )
        else:
            await self._advance_oasis_session(
                simulation_id=simulation_id,
                simulation=simulation,
                next_round=next_round,
                cue=cue,
                documents=documents,
            )

        if next_round >= simulation.round_goal:
            logger.info("Simulation %s reached round goal, finalizing brief.", simulation_id)
            await self._finalize_simulation(
                simulation_id=simulation_id,
                documents=documents,
                profile=self.repository.get_profile(),
            )

        self.session.commit()
        logger.info("Simulation %s advanced to round %d.", simulation_id, next_round)
        return self.get_snapshot(simulation_id)

    async def finish_session(
        self,
        *,
        simulation_id: str,
        documents: list[str],
        profile: UserReasoningProfile,
    ) -> SessionSnapshot:
        simulation = self.repository.get_simulation(simulation_id)
        if self.repository.get_brief(simulation_id) is not None:
            self.repository.mark_simulation_complete(simulation_id)
            self.session.commit()
            logger.info("Simulation %s already had a brief; returning existing completion.", simulation_id)
            return self.get_snapshot(simulation_id)

        logger.info("Finishing simulation %s on demand.", simulation_id)
        await self._finalize_simulation(
            simulation_id=simulation_id,
            documents=documents,
            profile=profile,
        )
        self.session.commit()
        logger.info("Simulation %s finished successfully.", simulation_id)
        return self.get_snapshot(simulation_id)

    def list_events(self, simulation_id: str, last_event_id: int | None = None) -> list[SessionEvent]:
        return [
            SessionEvent(
                id=event.id,
                event_type=event.event_type,
                round_index=event.round_index,
                payload=event.payload_json,
                created_at=event.created_at.isoformat(),
            )
            for event in self.repository.list_events_after(simulation_id, last_event_id)
        ]

    async def _finalize_simulation(
        self,
        *,
        simulation_id: str,
        documents: list[str],
        profile: UserReasoningProfile,
    ) -> None:
        simulation = self.repository.get_simulation(simulation_id)
        if self.repository.get_brief(simulation_id) is not None:
            self.repository.mark_simulation_complete(simulation_id)
            return

        transcript = [message.model_dump() for message in [message_from_entity(item) for item in simulation.messages]]
        trajectories: dict[str, list[dict[str, object]]] = defaultdict(list)
        for metric in self.repository.get_trajectory_metrics(simulation_id):
            if metric.persona_id is None:
                continue
            trajectories[metric.persona_id].append(
                {
                    "round_index": metric.round_index or 0,
                    "stance": metric.numeric_value or 0.0,
                    "confidence": float((metric.json_value or {}).get("confidence", 0.0)),
                }
            )

        client = StructuredLLMClient(self.provider_factory.create_summary_backend())
        brief_payload = await client.generate_json(
            system_prompt="You synthesize deliberation transcripts into structured decision briefs.",
            user_prompt=build_brief_prompt(
                decision=simulation.decision,
                transcript=transcript,
                trajectories=trajectories,
                blind_spots=profile.least_engaged_tags,
                document_context="\n\n".join(documents),
            ),
            schema=DecisionBriefPayload,
        )
        self.repository.set_artifact(simulation_id, "brief", brief_payload.model_dump())
        self.repository.mark_simulation_complete(simulation_id)
        self._update_profile_after_completion(simulation_id, profile, simulation)

    def _update_profile_after_completion(
        self,
        simulation_id: str,
        profile: UserReasoningProfile,
        simulation,
    ) -> None:
        selected_tags = Counter(tag for participant in simulation.participants for tag in participant.persona.tags)
        most_common = [tag for tag, _ in selected_tags.most_common(5)]
        least_common = [tag for tag, _ in selected_tags.most_common()][-3:] if selected_tags else profile.least_engaged_tags
        avg_rounds = ((profile.avg_rounds_before_ending * profile.sessions_count) + simulation.current_round) / max(1, profile.sessions_count + 1)

        updated = UserReasoningProfile(
            sessions_count=profile.sessions_count + 1,
            most_engaged_tags=most_common or profile.most_engaged_tags,
            least_engaged_tags=least_common or profile.least_engaged_tags,
            personas_favorited=[participant.persona_id for participant in simulation.participants[:3]],
            ignored_perspective_types=profile.ignored_perspective_types,
            override_frequency=profile.override_frequency,
            avg_rounds_before_ending=round(avg_rounds, 2),
            position_change_rate=self._calculate_position_change_rate(simulation_id),
        )
        self.repository.update_profile(updated)

    def _calculate_position_change_rate(self, simulation_id: str) -> float:
        trajectories = self.repository.get_trajectory_metrics(simulation_id)
        by_persona: dict[str, list[float]] = defaultdict(list)
        for metric in trajectories:
            if metric.persona_id is None:
                continue
            by_persona[metric.persona_id].append(metric.numeric_value or 0.0)

        total = 0
        changed = 0
        for values in by_persona.values():
            if len(values) < 2:
                continue
            total += 1
            if abs(values[-1] - values[0]) >= 0.1:
                changed += 1
        return round(changed / total, 2) if total else 0.0

    def _build_network(self, personas: list[Persona]) -> list[NetworkEdge]:
        if len(personas) < 2:
            return []
        edges: list[NetworkEdge] = []
        total = len(personas)
        for index, persona in enumerate(personas):
            neighbor = personas[(index + 1) % total]
            edges.append(NetworkEdge(source_id=persona.id, target_id=neighbor.id))
            bridge = personas[(index + 2) % total]
            if bridge.id != neighbor.id:
                edges.append(NetworkEdge(source_id=persona.id, target_id=bridge.id))
        return edges

    @staticmethod
    def _parse_agent_payload(raw_payload: str, schema: type[T]) -> T:
        return schema.model_validate(_extract_json_payload(raw_payload))

    def _should_use_local_stub_runtime(self) -> bool:
        return self.settings.normalized_provider == "stub" and OasisDeliberationRuntime is None

    async def _create_stub_session(
        self,
        *,
        simulation_id: str,
        simulation,
        request: CreateSessionRequest,
        frame: dict[str, Any],
        document_context: str,
        document_names: list[str],
    ) -> None:
        opening_text = build_opening_system_message(request.decision, frame, document_names)
        self.repository.add_message(
            simulation_id=simulation_id,
            author_id="orchestrator",
            author_name="Deliberation Engine",
            avatar_emoji="🛰️",
            role="system",
            round_index=0,
            cue="frame",
            content=opening_text,
        )

        client = StructuredLLMClient(self.provider_factory.create_agent_backend())
        for participant in simulation.participants:
            persona = persona_from_entity(participant.persona)
            payload = await client.generate_json(
                system_prompt=self._persona_system_prompt(persona, request.decision, document_context),
                user_prompt=build_initial_stance_prompt(
                    decision=request.decision,
                    document_context=document_context,
                ),
                schema=StanceInterviewPayload,
            )
            self.repository.set_participant_state(
                simulation_id=simulation_id,
                persona_id=participant.persona_id,
                stance=payload.stance,
                confidence=payload.confidence,
                rationale=payload.rationale,
                round_index=0,
            )

    async def _create_oasis_session(
        self,
        *,
        simulation_id: str,
        simulation,
        request: CreateSessionRequest,
        frame: dict[str, Any],
        document_context: str,
        document_names: list[str],
    ) -> None:
        if OasisDeliberationRuntime is None:
            raise RuntimeError("OASIS runtime is unavailable in this environment.")

        runtime = OasisDeliberationRuntime(
            provider_factory=self.provider_factory,
            decision=request.decision,
            personas=[(participant.agent_id, persona_from_entity(participant.persona)) for participant in simulation.participants],
            document_context=document_context,
            db_path=simulation.oasis_db_path,
        )
        await runtime.start_new()
        try:
            group_id = await runtime.create_room("Deliberation Room")
            self.repository.set_group_id(simulation_id, group_id)

            opening_text = build_opening_system_message(request.decision, frame, document_names)
            await runtime.send_moderator_message(group_id=group_id, content=opening_text)
            self.repository.add_message(
                simulation_id=simulation_id,
                author_id="orchestrator",
                author_name="Deliberation Engine",
                avatar_emoji="🛰️",
                role="system",
                round_index=0,
                cue="frame",
                content=opening_text,
            )

            for participant in simulation.participants:
                prompt = build_initial_stance_prompt(decision=request.decision, document_context=document_context)
                payload = self._parse_agent_payload(
                    raw_payload=await runtime.interview(agent_id=participant.agent_id, prompt=prompt),
                    schema=StanceInterviewPayload,
                )
                self.repository.set_participant_state(
                    simulation_id=simulation_id,
                    persona_id=participant.persona_id,
                    stance=payload.stance,
                    confidence=payload.confidence,
                    rationale=payload.rationale,
                    round_index=0,
                )
        finally:
            await runtime.close()

    async def _advance_stub_session(
        self,
        *,
        simulation_id: str,
        simulation,
        next_round: int,
        cue: str,
        documents: list[str],
    ) -> None:
        document_context = "\n\n".join(documents)
        client = StructuredLLMClient(self.provider_factory.create_agent_backend())

        for event in self.repository.get_pending_interjections(simulation_id):
            self.repository.mark_interjection_processed(event.id)

        speaking_order = list(simulation.participants)
        random.shuffle(speaking_order)

        for participant in speaking_order:
            persona = persona_from_entity(participant.persona)
            contribution_prompt = build_contribution_prompt(
                persona=persona,
                decision=simulation.decision,
                round_index=next_round,
                cue=cue,
                room_context=self._room_context(simulation_id),
                document_context=document_context,
            )
            payload = await client.generate_json(
                system_prompt=self._persona_system_prompt(persona, simulation.decision, document_context),
                user_prompt=contribution_prompt,
                schema=ContributionPayload,
            )
            self.repository.add_message(
                simulation_id=simulation_id,
                author_id=persona.id,
                author_name=persona.name,
                avatar_emoji=persona.avatar_emoji,
                role="persona",
                round_index=next_round,
                cue=cue,
                content=payload.message,
                stance=payload.stance,
                confidence=payload.confidence,
            )

        for participant in simulation.participants:
            persona = persona_from_entity(participant.persona)
            stance_prompt = build_round_stance_prompt(
                decision=simulation.decision,
                round_index=next_round,
                cue=cue,
                room_context=self._room_context(simulation_id),
                document_context=document_context,
            )
            payload = await client.generate_json(
                system_prompt=self._persona_system_prompt(persona, simulation.decision, document_context),
                user_prompt=stance_prompt,
                schema=StanceInterviewPayload,
            )
            self.repository.set_participant_state(
                simulation_id=simulation_id,
                persona_id=participant.persona_id,
                stance=payload.stance,
                confidence=payload.confidence,
                rationale=payload.rationale,
                round_index=next_round,
            )
            self.repository.update_message_metrics(
                simulation_id=simulation_id,
                author_id=persona.id,
                round_index=next_round,
                stance=payload.stance,
                confidence=payload.confidence,
            )

        self.repository.complete_round(simulation_id, next_round)

    async def _advance_oasis_session(
        self,
        *,
        simulation_id: str,
        simulation,
        next_round: int,
        cue: str,
        documents: list[str],
    ) -> None:
        if OasisDeliberationRuntime is None:
            raise RuntimeError("OASIS runtime is unavailable in this environment.")

        runtime = OasisDeliberationRuntime(
            provider_factory=self.provider_factory,
            decision=simulation.decision,
            personas=[(participant.agent_id, persona_from_entity(participant.persona)) for participant in simulation.participants],
            document_context="\n\n".join(documents),
            db_path=simulation.oasis_db_path,
        )
        await runtime.attach_existing()
        try:
            group_id = simulation.oasis_group_id
            if group_id is None:
                raise RuntimeError("Simulation OASIS group is not initialized.")

            for event in self.repository.get_pending_interjections(simulation_id):
                content = str(event.payload_json["content"])
                await runtime.send_moderator_message(group_id=group_id, content=f"User interjection: {content}")
                self.repository.mark_interjection_processed(event.id)

            await runtime.send_moderator_message(group_id=group_id, content=f"Round {next_round}: {cue}. Each persona should contribute one concise message.")

            speaking_order = list(simulation.participants)
            random.shuffle(speaking_order)

            for participant in speaking_order:
                room_context = await runtime.room_context(agent_id=participant.agent_id)
                contribution_prompt = build_contribution_prompt(
                    persona=participant.persona,
                    decision=simulation.decision,
                    round_index=next_round,
                    cue=cue,
                    room_context=room_context,
                    document_context="\n\n".join(documents),
                )
                payload = self._parse_agent_payload(
                    raw_payload=await runtime.interview(
                        agent_id=participant.agent_id,
                        prompt=contribution_prompt,
                    ),
                    schema=ContributionPayload,
                )
                await runtime.send_participant_message(
                    agent_id=participant.agent_id,
                    group_id=group_id,
                    content=payload.message,
                )
                self.repository.add_message(
                    simulation_id=simulation_id,
                    author_id=participant.persona.id,
                    author_name=participant.persona.name,
                    avatar_emoji=participant.persona.avatar_emoji,
                    role="persona",
                    round_index=next_round,
                    cue=cue,
                    content=payload.message,
                    stance=payload.stance,
                    confidence=payload.confidence,
                )

            for participant in simulation.participants:
                room_context = await runtime.room_context(agent_id=participant.agent_id)
                stance_prompt = build_round_stance_prompt(
                    decision=simulation.decision,
                    round_index=next_round,
                    cue=cue,
                    room_context=room_context,
                    document_context="\n\n".join(documents),
                )
                payload = self._parse_agent_payload(
                    raw_payload=await runtime.interview(agent_id=participant.agent_id, prompt=stance_prompt),
                    schema=StanceInterviewPayload,
                )
                self.repository.set_participant_state(
                    simulation_id=simulation_id,
                    persona_id=participant.persona_id,
                    stance=payload.stance,
                    confidence=payload.confidence,
                    rationale=payload.rationale,
                    round_index=next_round,
                )
                self.repository.update_message_metrics(
                    simulation_id=simulation_id,
                    author_id=participant.persona.id,
                    round_index=next_round,
                    stance=payload.stance,
                    confidence=payload.confidence,
                )

            self.repository.complete_round(simulation_id, next_round)
        finally:
            await runtime.close()

    def _room_context(self, simulation_id: str) -> str:
        simulation = self.repository.get_simulation(simulation_id)
        if not simulation.messages:
            return "The room is quiet so far."
        lines = []
        for message in simulation.messages[-20:]:
            speaker = "System" if message.role == "system" else message.author_name
            lines.append(f"{speaker}: {message.content}")
        return "\n".join(lines)

    @staticmethod
    def _persona_system_prompt(persona: Persona, decision: str, document_context: str) -> str:
        biases = ", ".join(f"{bias.type} ({bias.strength})" for bias in persona.cognitive_biases) or "None"
        return (
            f"Persona name: {persona.name}\n"
            f"Persona summary: {persona.summary}\n"
            f"Identity anchor: {persona.identity_anchor}\n"
            f"Epistemic style: {persona.epistemic_style}\n"
            f"Argumentative voice: {persona.argumentative_voice}\n"
            f"Cognitive biases: {biases}\n"
            f"Decision: {decision}\n"
            f"Relevant document context:\n{document_context or 'No documents attached.'}\n"
            "Stay in character. Never address the user directly. Never use em dashes."
        )
