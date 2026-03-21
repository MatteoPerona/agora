from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from camel.models import BaseModelBackend, ModelFactory
from camel.types import ModelPlatformType
from pydantic import BaseModel

from ..config import Settings
from .stub_model import ScriptedModelBackend

T = TypeVar("T", bound=BaseModel)


class SimulationProviderFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_agent_backend(self) -> BaseModelBackend:
        return self._create_backend(
            model_name=self.settings.sim_model,
            temperature=0.6,
            max_tokens=1024,
        )

    def create_selector_backend(self) -> BaseModelBackend:
        return self._create_backend(
            model_name=self.settings.selector_model,
            temperature=0.2,
            max_tokens=1024,
        )

    def create_summary_backend(self) -> BaseModelBackend:
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
    ) -> BaseModelBackend:
        model_config_dict = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.settings.normalized_provider == "stub":
            return ScriptedModelBackend(model_type="stub", model_config_dict=model_config_dict)

        platform = ModelPlatformType(self.settings.normalized_provider)
        return ModelFactory.create(
            model_platform=platform,
            model_type=model_name,
            model_config_dict=model_config_dict,
            api_key=self.settings.sim_api_key,
            url=self.settings.sim_base_url,
        )


class StructuredLLMClient:
    def __init__(self, backend: BaseModelBackend):
        self.backend = backend

    async def generate_json(self, *, system_prompt: str, user_prompt: str, schema: type[T]) -> T:
        result = await self.backend.arun(
            [
                {"role": "system", "content": system_prompt},
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
