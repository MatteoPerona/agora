from __future__ import annotations

import json

import pytest
from importlib import import_module

def _to_fenced_json(payload: object) -> str:
    return f"```json\n{json.dumps(payload)}\n```"


def _bootstrap_persona_ids(client) -> list[str]:
    response = client.get("/api/personas")
    assert response.status_code == 200
    personas = response.json()
    assert len(personas) >= 3
    return [persona["id"] for persona in personas[:3]]


class _FencedOasisRuntime:
    def __init__(
        self,
        *,
        provider_factory: object,
        decision: str,
        personas: list[tuple[int, object]],
        document_context: str,
        db_path: str,
    ) -> None:
        self.personas_by_id = {agent_id: persona for agent_id, persona in personas}

    async def start_new(self) -> None:
        return None

    async def attach_existing(self) -> None:
        return None

    async def create_room(self, room_name: str) -> int:
        return 123

    async def send_moderator_message(self, *, group_id: int, content: str) -> None:
        return None

    async def send_participant_message(self, *, agent_id: int, group_id: int, content: str) -> None:
        return None

    async def room_context(self, *, agent_id: int) -> str:
        return f"Context for {self.personas_by_id[agent_id].name}"

    async def interview(self, *, agent_id: int, prompt: str) -> str:
        persona = self.personas_by_id[agent_id]
        if "TASK: CONTRIBUTION" in prompt:
            return _to_fenced_json(
                {
                    "message": f"{persona.name} argues that constraints are meaningful in this round.",
                    "stance": 0.2 * agent_id,
                    "confidence": min(0.7 + agent_id * 0.01, 0.95),
                    "rationale": f"{persona.name} balances upside and execution risk.",
                }
            )

        if "TASK: STANCE_INTERVIEW" in prompt:
            return _to_fenced_json(
                {
                    "stance": round(-0.15 + 0.1 * agent_id, 2),
                    "confidence": round(0.55 + 0.02 * agent_id, 2),
                    "rationale": f"{persona.name} is adjusting stance from prior context.",
                }
            )

        raise RuntimeError(f"Unhandled interview prompt: {prompt}")

    async def close(self) -> None:
        return None


class _FencedSummaryLLMClient:
    call_count: int = 0

    def __init__(self, backend: object):
        self.backend = backend

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type,
    ) -> object:
        from backend.app.simulation import provider as provider_module

        self.__class__.call_count += 1
        return schema.model_validate(
            provider_module._extract_json_payload(
                _to_fenced_json(
                    {
                        "headline": "Fenced brief for simulation",
                        "landscape_summary": "A concise summary captured from fenced model output.",
                        "strongest_arguments": [
                            {
                                "persona_name": "Panel",
                                "title": "Execution risk stays central",
                                "explanation": "Participants kept returning to delivery constraints.",
                            }
                        ],
                        "key_uncertainties": [
                            "What operational commitments are realistic?",
                            "How quickly can behavior shift?",
                        ],
                        "blind_spots": ["Need explicit owner buy-in dynamics."],
                        "suggested_next_steps": [
                            "Run a short operational feasibility check.",
                        ],
                    }
                )
            )
        )


def _patch_runtime_and_summary_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    service_module = import_module("backend.app.simulation.service")
    monkeypatch.setattr(service_module, "OasisDeliberationRuntime", _FencedOasisRuntime)
    monkeypatch.setattr(service_module, "StructuredLLMClient", _FencedSummaryLLMClient)


def test_extract_json_payload_handles_anthropic_fenced_json() -> None:
    from backend.app.simulation import provider as provider_module

    payload = provider_module._extract_json_payload(
        "\n".join(
            [
                "I can provide this in JSON.",
                "```json",
                '{"stance": 0.17, "confidence": 0.88, "rationale": "Calibrated output."}',
                "```",
                "Done.",
            ]
        )
    )
    assert payload["stance"] == 0.17
    assert payload["confidence"] == 0.88


def test_session_lifecycle_parses_fenced_outputs_for_start_advance_finish(
    app_harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime_and_summary_backend(monkeypatch)
    client = app_harness.client

    payload = {
        "decision": "Should we prioritize enterprise planning features over core consumer upgrades this quarter?",
        "persona_ids": _bootstrap_persona_ids(client),
        "round_goal": 3,
        "document_ids": [],
    }

    created = client.post("/api/sessions", json=payload)
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["status"] == "running"
    assert created_payload["current_round"] == 0
    assert len(created_payload["messages"]) == 1
    assert len(created_payload["roster"]) == 3

    interjected = client.post(
        f"/api/sessions/{created_payload['session_id']}/interjections",
        json={"content": "Could we run a smaller pilot before full rollout?"},
    )
    assert interjected.status_code == 200
    assert any(
        message["round_index"] == 0 and message["role"] == "user" for message in interjected.json()["messages"]
    )

    advanced = client.post(f"/api/sessions/{created_payload['session_id']}/advance")
    assert advanced.status_code == 200
    advanced_payload = advanced.json()
    assert advanced_payload["current_round"] == 1
    assert advanced_payload["status"] in {"running", "complete"}
    round_1_persona_messages = [
        message
        for message in advanced_payload["messages"]
        if message["round_index"] == 1 and message["role"] == "persona"
    ]
    assert len(round_1_persona_messages) == len(payload["persona_ids"])

    finished = client.post(f"/api/sessions/{created_payload['session_id']}/finish")
    assert finished.status_code == 200
    finished_payload = finished.json()
    assert finished_payload["status"] == "complete"
    assert finished_payload["brief"] is not None
    assert finished_payload["brief"]["headline"] == "Fenced brief for simulation"
    assert _FencedSummaryLLMClient.call_count == 1

    finished_again = client.post(f"/api/sessions/{created_payload['session_id']}/finish")
    assert finished_again.status_code == 200
    assert finished_again.json()["brief"] == finished_payload["brief"]
    assert _FencedSummaryLLMClient.call_count == 1


def test_advance_is_noop_after_session_complete(
    app_harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_runtime_and_summary_backend(monkeypatch)
    client = app_harness.client

    payload = {
        "decision": "Should we defer the launch and optimize for reliability before expanding our channel partnerships?",
        "persona_ids": _bootstrap_persona_ids(client),
        "round_goal": 3,
        "document_ids": [],
    }

    created = client.post("/api/sessions", json=payload)
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    first_advance = client.post(f"/api/sessions/{session_id}/advance")
    assert first_advance.status_code == 200
    first_payload = first_advance.json()
    assert first_payload["current_round"] == 1
    assert first_payload["status"] == "running"
    first_message_count = len(first_payload["messages"])

    second_advance = client.post(f"/api/sessions/{session_id}/advance")
    assert second_advance.status_code == 200
    second_payload = second_advance.json()
    assert second_payload["current_round"] == 2
    assert second_payload["status"] == "running"

    third_advance = client.post(f"/api/sessions/{session_id}/advance")
    assert third_advance.status_code == 200
    third_payload = third_advance.json()
    assert third_payload["current_round"] == 3
    assert third_payload["status"] == "complete"
    third_message_count = len(third_payload["messages"])

    repeat_advance = client.post(f"/api/sessions/{session_id}/advance")
    assert repeat_advance.status_code == 200
    repeat_payload = repeat_advance.json()
    assert repeat_payload["current_round"] == third_payload["current_round"]
    assert repeat_payload["status"] == "complete"
    assert len(repeat_payload["messages"]) == third_message_count

    finished = client.post(f"/api/sessions/{session_id}/finish")
    assert finished.status_code == 200
    assert finished.json()["status"] == "complete"
