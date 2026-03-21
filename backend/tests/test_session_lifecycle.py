from __future__ import annotations


def _bootstrap_persona_ids(client) -> list[str]:
    response = client.get("/api/personas")
    assert response.status_code == 200
    personas = response.json()
    assert len(personas) >= 3
    return [persona["id"] for persona in personas[:3]]


def test_stub_provider_session_lifecycle_create_advance_interject_finish_restore(app_harness) -> None:
    client = app_harness.client

    create_payload = {
        "decision": (
            "Should we shift the roadmap toward "
            "enterprise scenario planning and defer core "
            "consumer features this quarter?"
        ),
        "persona_ids": _bootstrap_persona_ids(client),
        "round_goal": 3,
        "document_ids": [],
    }

    created_response = client.post("/api/sessions", json=create_payload)
    assert created_response.status_code == 200
    created = created_response.json()
    session_id = created["session_id"]
    assert created["status"] in {"running", "idle"}
    assert created["current_round"] == 0
    assert created["session_id"] == session_id
    assert len(created["roster"]) == 3

    advanced_response = client.post(f"/api/sessions/{session_id}/advance")
    assert advanced_response.status_code == 200
    advanced = advanced_response.json()
    assert advanced["current_round"] == 1
    assert advanced["status"] in {"running", "complete"}
    assert any(message["round_index"] == 1 for message in advanced["messages"])

    interjection = {"content": "Could we benchmark against a smaller pilot first?"}
    interjected_response = client.post(
        f"/api/sessions/{session_id}/interjections",
        json=interjection,
    )
    assert interjected_response.status_code == 200
    interjected = interjected_response.json()
    assert interjected["current_round"] == advanced["current_round"]
    assert any(
        message["author_id"] == "user" and message["content"] == interjection["content"]
        for message in interjected["messages"]
    )

    finished_response = client.post(f"/api/sessions/{session_id}/finish")
    assert finished_response.status_code == 200
    finished = finished_response.json()
    assert finished["status"] == "complete"
    assert finished["brief"] is not None
    assert finished["brief"]["headline"]
    assert finished["session_id"] == session_id

    restored_response = client.get(f"/api/sessions/{session_id}")
    assert restored_response.status_code == 200
    restored = restored_response.json()
    assert restored["session_id"] == session_id
    assert restored["status"] == "complete"
    assert restored["brief"] == finished["brief"]
