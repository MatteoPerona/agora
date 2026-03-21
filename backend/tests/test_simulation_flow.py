from __future__ import annotations


def test_stub_session_lifecycle(client) -> None:
    personas = client.get("/api/personas").json()
    create_payload = {
        "decision": "We need to decide whether to pivot our product toward enterprise scenario planning while preserving enough momentum to keep learning quickly.",
        "persona_ids": [personas[0]["id"], personas[1]["id"], personas[2]["id"]],
        "round_goal": 3,
        "document_ids": [],
    }

    created = client.post("/api/sessions", json=create_payload)
    assert created.status_code == 200
    created_payload = created.json()
    session_id = created_payload["session_id"]
    assert len(created_payload["messages"]) == 1
    assert len(created_payload["roster"]) == 3
    assert all(len(series["points"]) == 1 for series in created_payload["trajectories"])

    advanced = client.post(f"/api/sessions/{session_id}/advance")
    assert advanced.status_code == 200
    advanced_payload = advanced.json()
    assert advanced_payload["current_round"] == 1
    assert len(advanced_payload["messages"]) >= 4

    interjected = client.post(
        f"/api/sessions/{session_id}/interjections",
        json={"content": "The enterprise path may slow us down too much."},
    )
    assert interjected.status_code == 200
    interjected_payload = interjected.json()
    assert interjected_payload["messages"][-1]["role"] == "user"

    finished = client.post(f"/api/sessions/{session_id}/finish")
    assert finished.status_code == 200
    finished_payload = finished.json()
    assert finished_payload["brief"] is not None
    assert finished_payload["status"] == "complete"

    restored = client.get(f"/api/sessions/{session_id}")
    assert restored.status_code == 200
    restored_payload = restored.json()
    assert restored_payload["session_id"] == session_id
    assert restored_payload["brief"] is not None
