from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from ..config import Settings

T = TypeVar("T", bound=BaseModel)


@dataclass
class _CompletionMessage:
    content: str


@dataclass
class _CompletionChoice:
    message: _CompletionMessage


@dataclass
class _CompletionResponse:
    choices: list[_CompletionChoice]


class AsyncChatBackend(Protocol):
    async def arun(self, messages: list[dict[str, Any]]) -> _CompletionResponse:
        ...


class LocalScriptedBackend:
    def __init__(self, *, model_config_dict: dict[str, Any] | None = None):
        self.model_config_dict = model_config_dict or {}

    async def arun(self, messages: list[dict[str, Any]]) -> _CompletionResponse:
        content = _script_response(messages)
        return _CompletionResponse(choices=[_CompletionChoice(message=_CompletionMessage(content=content))])


class SimulationProviderFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_agent_backend(self) -> AsyncChatBackend:
        return self._create_backend(
            model_name=self.settings.sim_model,
            temperature=0.6,
            max_tokens=1024,
        )

    def create_selector_backend(self) -> AsyncChatBackend:
        return self._create_backend(
            model_name=self.settings.selector_model,
            temperature=0.2,
            max_tokens=1024,
        )

    def create_summary_backend(self) -> AsyncChatBackend:
        return self._create_backend(
            model_name=self.settings.summary_model,
            temperature=0.2,
            max_tokens=1536,
        )

    def _create_backend(
        self,
        *,
        model_name: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncChatBackend:
        model_config_dict = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.settings.normalized_provider in {"", "stub"}:
            raise RuntimeError(
                "The stub provider is disabled. Configure a real AI provider, model, and API key."
            )

        try:
            from camel.models import ModelFactory
            from camel.types import ModelPlatformType
        except ImportError:
            raise RuntimeError(
                "camel-ai is required for non-stub simulation providers. "
                "Use SIM_PROVIDER=stub on Python 3.12, or install a Python version supported by camel-ai."
            )

        platform = ModelPlatformType(self.settings.normalized_provider)
        return ModelFactory.create(
            model_platform=platform,
            model_type=model_name,
            model_config_dict=model_config_dict,
            api_key=self.settings.sim_api_key,
            url=self.settings.sim_base_url,
        )


class StructuredLLMClient:
    def __init__(self, backend: AsyncChatBackend):
        self.backend = backend

    async def generate_json(self, *, system_prompt: str, user_prompt: str, schema: type[T]) -> T:
        result = await self.backend.arun(
            [
                {"role": "system", "content": system_prompt + "\n\nNever use em dashes (—) in any output. Use a comma, a colon, or a new sentence instead."},
                {"role": "user", "content": user_prompt},
            ]
        )
        content = result.choices[0].message.content or ""
        payload = _extract_json_payload(content)
        return schema.model_validate(payload)


def _extract_json_payload(raw_text: str) -> Any:
    candidates = _extract_json_candidates(raw_text)
    for candidate in candidates:
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, (dict, list)):
            return payload

    raise ValueError(f"Could not find a JSON payload in model output: {raw_text!r}")


def _extract_json_candidates(raw_text: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"```(?:json)?\s*(.*?)```", raw_text, re.IGNORECASE | re.DOTALL):
        candidates.append(match.group(1).strip())

    for start, _ in enumerate(raw_text):
        if raw_text[start] not in "{[":
            continue
        payload = _extract_balanced_json(raw_text, start)
        if payload:
            candidates.append(payload)
            break

    return candidates


def _extract_balanced_json(raw_text: str, start: int) -> str | None:
    open_to_close = {"{": "}", "[": "]"}
    stack: list[str] = []
    in_string = False
    escaped = False

    for index in range(start, len(raw_text)):
        char = raw_text[index]

        if escaped:
            escaped = False
            continue

        if char == "\\" and in_string:
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char in open_to_close:
            stack.append(char)
            continue

        if not stack:
            continue

        if char == open_to_close[stack[-1]]:
            stack.pop()
            if not stack:
                return raw_text[start : index + 1]

    return None


def _script_response(messages: list[dict[str, Any]]) -> str:
    prompt = str(messages[-1].get("content", ""))

    if "TASK: CONTRIBUTION" in prompt:
        persona_name = _match(prompt, r"PERSONA_NAME:\s*(.+)")
        round_index_str = _match(prompt, r"ROUND_INDEX:\s*(\d+)", default="1")
        cue = _match(prompt, r"ROUND_CUE:\s*(.+)", default="deliberation")
        decision_snippet = _match(prompt, r"Decision:\s*(.+)", default="the question at hand")
        stance = _stance_for(persona_name)
        confidence = _confidence_for(persona_name)
        cue_messages: dict[str, str] = {
            "decision framing": f"Before we go further, we need to agree on what we're actually deciding. The framing of '{decision_snippet[:60]}' matters more than most realize.",
            "market and demand": "The demand side of this is underdeveloped in our analysis. Who actually wants this, and how badly? That drives everything downstream.",
            "execution and operations": "I've seen this pattern before. The plan looks clean on paper, but the operational burden will be three times what anyone is budgeting for.",
            "behavior and adoption": "People do not change behavior just because the option is better. Adoption is a social and psychological problem, not a logical one.",
            "risk and downside": "We keep anchoring on the upside scenario. What does the failure mode actually look like, and can we survive it?",
            "synthesis and decision rule": "The meta-question is what would have to be true for this to be obviously correct. I do not think we have answered that yet.",
        }
        message = cue_messages.get(cue, f"In round {round_index_str}, the core tradeoff remains unresolved. We need to be more precise about what we're willing to give up.")
        return json.dumps(
            {
                "message": message,
                "stance": stance,
                "confidence": confidence,
                "rationale": f"{persona_name} is weighing the strongest available evidence through their particular frame of reference.",
            }
        )

    if "TASK: STANCE_INTERVIEW" in prompt:
        persona_name = _match(" ".join(str(message.get("content", "")) for message in messages), r"Persona name:\s*(.+)")
        stance = _stance_for(persona_name)
        confidence = _confidence_for(persona_name)
        direction = "leaning toward" if stance > 0 else "skeptical of"
        return json.dumps(
            {
                "stance": stance,
                "confidence": confidence,
                "rationale": f"{persona_name or 'This persona'} is {direction} the proposal after weighing the arguments presented, though key uncertainties remain.",
            }
        )

    if "TASK: PANEL_SELECTION" in prompt:
        persona_catalog = _parse_json_block(prompt, "PERSONA_CATALOG_JSON:")
        manual_ids = _parse_json_array(prompt, "Manual ids that must be preserved:")
        recommended_ids = list(dict.fromkeys([*manual_ids, *[entry["id"] for entry in persona_catalog][:5]]))[:5]
        rationales = {
            persona_id: [f"{persona_id} brings a perspective that will stress-test the core assumption.", "Adds cognitive diversity to the panel."]
            for persona_id in recommended_ids
        }
        return json.dumps(
            {
                "recommended_ids": recommended_ids,
                "rationales": rationales,
                "blind_spot_message": "This panel thinks clearly and argues well. It might be worth pausing to ask what a poet or a fool would say instead.",
            }
        )

    if "TASK: FINAL_BRIEF" in prompt:
        decision_snippet = _match(prompt, r'"decision":\s*"([^"]{0,80})', default="the question at hand")
        return json.dumps(
            {
                "headline": f"The panel reached a conditional recommendation on: {decision_snippet[:60]}.",
                "landscape_summary": "The deliberation surfaced genuine tension between the potential upside and the execution burden required to reach it. Personas divided roughly between those who weighted opportunity cost and those anchoring on operational risk. No single view commanded consensus, but the debate clarified the conditions under which each position would be correct.",
                "strongest_arguments": [
                    {
                        "persona_name": "Panel",
                        "title": "Execution risk is underpriced",
                        "explanation": "Multiple speakers returned to the operational cost of carrying the plan through to completion. The effort required is higher than the opening framing suggested.",
                    },
                    {
                        "persona_name": "Panel",
                        "title": "Adoption cannot be assumed",
                        "explanation": "The behavior-change required of end users or stakeholders was flagged as a key unknown. Demand-side assumptions need validation before committing.",
                    },
                ],
                "key_uncertainties": [
                    "Whether the target stakeholders will change behavior at the pace the plan requires.",
                    "Whether the team has the capacity to absorb the operational complexity.",
                    "Whether the competitive or contextual environment will remain stable long enough.",
                ],
                "blind_spots": [
                    "Operations complexity was raised but never fully stress-tested against available capacity.",
                    "Second-order effects on existing relationships or systems were not addressed.",
                ],
                "suggested_next_steps": [
                    "Run one bounded validation experiment before committing resources at scale.",
                    "Pressure-test adoption assumptions with a real end-user or buyer in the next two weeks.",
                ],
            }
        )

    if "TASK: PERSONA_EXPANSION" in prompt:
        description = _match(prompt, r'"(.+)"', default=prompt[:80])
        return json.dumps(
            {
                "name": "The Reluctant Optimist",
                "summary": f"Someone who has seen enough to be skeptical but cannot quite stop believing things will work out. Shaped by: {description[:80]}.",
                "identity_anchor": f"You are The Reluctant Optimist. You have been burned before, and yet here you are, still curious, still showing up, still arguing that it matters. You were formed by: {description[:100]}",
                "epistemic_style": "You trust lived experience over theory, and you are always looking for the one detail that changes everything.",
                "argumentative_voice": "Wry and warm. You make your point with a story, a raised eyebrow, and occasionally a laugh at yourself.",
                "tags": ["philosophy", "psychology", "culture"],
                "opinion_change_threshold": "MODERATE",
                "avatar_emoji": "",
                "cognitive_biases": [
                    {"type": "optimism bias", "strength": "MODERATE", "description": "Defaults to hope even when the numbers say otherwise."},
                    {"type": "narrative bias", "strength": "HIGH", "description": "A compelling story can move you more than a spreadsheet ever will."},
                ],
                "creator_id": "local-user",
                "visibility": "private",
            }
        )

    return json.dumps({"message": "Stub response"})


def _stance_for(seed_text: str) -> float:
    import hashlib

    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    raw = int(digest[:4], 16) / 0xFFFF
    return round((raw * 1.8) - 0.9, 2)


def _confidence_for(seed_text: str) -> float:
    import hashlib

    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    raw = int(digest[4:8], 16) / 0xFFFF
    return round(0.45 + raw * 0.45, 2)


def _match(text: str, pattern: str, default: str = "Persona") -> str:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else default


def _parse_json_block(text: str, marker: str) -> list[dict[str, Any]]:
    if marker not in text:
        return []
    block = text.split(marker, 1)[1].lstrip()
    start = block.find("[")
    if start == -1:
        return []

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(block[start:], start=start):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return json.loads(block[start : index + 1])
    return []


def _parse_json_array(text: str, marker: str) -> list[str]:
    match = re.search(re.escape(marker) + r"\s*(\[[^\n]+\])", text)
    if not match:
        return []
    return json.loads(match.group(1))
