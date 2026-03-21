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
        round_index = _match(prompt, r"ROUND_INDEX:\s*(\d+)", default="1")
        stance = _stance_for(persona_name)
        confidence = _confidence_for(persona_name)
        message = f"{persona_name} says the main tradeoff still hinges on whether this path survives real execution in round {round_index}."
        return json.dumps(
            {
                "message": message,
                "stance": stance,
                "confidence": confidence,
                "rationale": f"{persona_name} is leaning based on the strongest tradeoff visible so far.",
            }
        )

    if "TASK: STANCE_INTERVIEW" in prompt:
        persona_name = _match(" ".join(str(m.get("content", "")) for m in messages), r"Persona name:\s*(.+)")
        stance = _stance_for(persona_name)
        confidence = _confidence_for(persona_name)
        return json.dumps(
            {
                "stance": stance,
                "confidence": confidence,
                "rationale": f"{persona_name or 'This persona'} is reacting to the latest discussion and weighing its own frame.",
            }
        )

    if "TASK: PANEL_SELECTION" in prompt:
        persona_catalog = _parse_json_block(prompt, "PERSONA_CATALOG_JSON:")
        manual_ids = _parse_json_array(prompt, "Manual ids that must be preserved:")
        recommended_ids = list(dict.fromkeys([*manual_ids, *[entry["id"] for entry in persona_catalog][:5]]))[:5]
        rationales = {
            persona_id: [f"{persona_id} adds a distinct lens.", "Selected to increase panel diversity."]
            for persona_id in recommended_ids
        }
        return json.dumps(
            {
                "recommended_ids": recommended_ids,
                "rationales": rationales,
                "blind_spot_message": "This opening panel intentionally adds perspectives you usually underweight.",
            }
        )

    if "TASK: FINAL_BRIEF" in prompt:
        return json.dumps(
            {
                "headline": "The room stayed divided enough to surface a real decision.",
                "landscape_summary": "The panel surfaced real tension between upside, execution drag, and adoption risk.",
                "strongest_arguments": [
                    {
                        "persona_name": "Panel",
                        "title": "Execution burden matters",
                        "explanation": "Several speakers kept returning to the cost of making the plan real.",
                    }
                ],
                "key_uncertainties": [
                    "Whether the target user would change behavior fast enough.",
                    "Whether the team can absorb the added complexity.",
                ],
                "blind_spots": [
                    "Operations and user behavior still deserve explicit follow-up."
                ],
                "suggested_next_steps": [
                    "Run one bounded validation step before fully committing.",
                    "Pressure-test the plan with an operator or buyer.",
                ],
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
