from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional, Type, Union

from openai import AsyncStream, Stream
from pydantic import BaseModel

from camel.messages import OpenAIMessage
from camel.models import BaseModelBackend
from camel.types import ChatCompletion, ChatCompletionChunk, ChatCompletionMessage, Choice, CompletionUsage, ModelType
from camel.utils import BaseTokenCounter


class ScriptedTokenCounter(BaseTokenCounter):
    def count_tokens_from_messages(self, messages: List[OpenAIMessage]) -> int:
        return max(10, sum(len(str(message.get("content", ""))) for message in messages) // 4)

    def encode(self, text: str) -> List[int]:
        return [0] * max(1, len(text) // 4)

    def decode(self, token_ids: List[int]) -> str:
        return " ".join("token" for _ in token_ids)


class ScriptedModelBackend(BaseModelBackend):
    model_type = ModelType.STUB

    @property
    def token_counter(self) -> BaseTokenCounter:
        if not self._token_counter:
            self._token_counter = ScriptedTokenCounter()
        return self._token_counter

    def _run(
        self,
        messages: List[OpenAIMessage],
        response_format: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[ChatCompletion, Stream[ChatCompletionChunk]]:
        return self._build_completion(messages)

    async def _arun(
        self,
        messages: List[OpenAIMessage],
        response_format: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[ChatCompletion, AsyncStream[ChatCompletionChunk]]:
        return self._build_completion(messages)

    def _build_completion(self, messages: List[OpenAIMessage]) -> ChatCompletion:
        content = _script_response(messages)
        return ChatCompletion(
            id="scripted-model",
            model="stub",
            object="chat.completion",
            created=int(time.time()),
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(content=content, role="assistant"),
                    logprobs=None,
                )
            ],
            usage=CompletionUsage(completion_tokens=20, prompt_tokens=20, total_tokens=40),
        )


def _script_response(messages: List[OpenAIMessage]) -> str:
    prompt = str(messages[-1].get("content", ""))

    if "TASK: CONTRIBUTION" in prompt:
        persona_name = _match(prompt, r"PERSONA_NAME:\s*(.+)")
        round_index_str = _match(prompt, r"ROUND_INDEX:\s*(\d+)", default="1")
        cue = _match(prompt, r"ROUND_CUE:\s*(.+)", default="deliberation")
        decision_snippet = _match(prompt, r"Decision:\s*(.+)", default="the question at hand")
        stance = _stance_for(persona_name)
        confidence = _confidence_for(persona_name)
        # Vary message by round cue so each round feels different
        cue_messages: dict[str, str] = {
            "decision framing": f"Before we go further, we need to agree on what we're actually deciding. The framing of '{decision_snippet[:60]}' matters more than most realize.",
            "market and demand": "The demand side of this is underdeveloped in our analysis. Who actually wants this, and how badly? That drives everything downstream.",
            "execution and operations": "I've seen this pattern before — the plan looks clean on paper but the operational burden will be three times what anyone is budgeting for.",
            "behavior and adoption": "People don't change behavior just because the option is better. Adoption is a social and psychological problem, not a logical one.",
            "risk and downside": "We keep anchoring on the upside scenario. What does the failure mode actually look like, and can we survive it?",
            "synthesis and decision rule": "The meta-question is: what would have to be true for this to be obviously correct? I don't think we've answered that yet.",
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
        persona_name = _match(" ".join(str(m.get("content", "")) for m in messages), r"Persona name:\s*(.+)")
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
                "blind_spot_message": "This panel thinks clearly and argues well — it might be worth pausing to ask what a poet or a fool would say instead.",
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
                "summary": f"Someone who has seen enough to be skeptical but can't quite stop believing things will work out. Shaped by: {description[:80]}.",
                "identity_anchor": f"You are The Reluctant Optimist. You've been burned before, and yet here you are — still curious, still showing up, still arguing that it matters. You were formed by: {description[:100]}",
                "epistemic_style": "You trust lived experience over theory, and you're always looking for the one detail that changes everything.",
                "argumentative_voice": "Wry and warm — you make your point with a story, a raised eyebrow, and occasionally a laugh at yourself.",
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
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    raw = int(digest[:4], 16) / 0xFFFF
    return round((raw * 1.8) - 0.9, 2)


def _confidence_for(seed_text: str) -> float:
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
