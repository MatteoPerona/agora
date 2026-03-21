from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select

from backend.app.entities import DocumentEntity
from backend.app.services.documents import chunk_document_text


def _normalise_text(raw_text: str) -> str:
    return re.sub(r"\s+", " ", raw_text).strip()


def test_upload_creates_document_and_chunks_via_api(app_harness) -> None:
    raw_text = "A deliberate policy memo should mention timing, cost, and impact. " * 95
    normalized = _normalise_text(raw_text)
    expected_chunks = chunk_document_text(normalized)

    response = app_harness.client.post(
        "/api/documents",
        files={"file": ("policy_notes.txt", raw_text, "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    document_id = payload["id"]
    assert payload["filename"] == "policy_notes.txt"

    from backend.app.database import SessionLocal

    with SessionLocal()() as session:
        document = session.scalar(select(DocumentEntity).where(DocumentEntity.id == document_id))
        assert document is not None
        assert document.filename == "policy_notes.txt"
        assert document.extracted_text == normalized
        assert document.extracted_char_count == len(normalized)
        assert len(document.chunks) == len(expected_chunks)
        assert document.chunks[0].content == expected_chunks[0]
        assert document.chunks[-1].content == expected_chunks[-1]
        assert document.extracted_text_preview == normalized[:260]

        stored_file = Path(document.storage_path)
        assert stored_file.exists()
        assert stored_file.read_bytes() == raw_text.encode("utf-8")
