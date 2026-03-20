from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import CreatePersonaRequest, Persona, StoredDocument, UploadedDocument, UserReasoningProfile

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "agora.sqlite3"
PERSONA_SEED_PATH = DATA_DIR / "personas.json"
PROFILE_SEED_PATH = DATA_DIR / "user_profile.json"
UPLOADS_DIR = DATA_DIR / "uploads"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                forked_from TEXT,
                visibility TEXT NOT NULL,
                summary TEXT NOT NULL,
                identity_anchor TEXT NOT NULL,
                epistemic_style TEXT NOT NULL,
                cognitive_biases TEXT NOT NULL,
                argumentative_voice TEXT NOT NULL,
                opinion_change_threshold TEXT NOT NULL,
                tags TEXT NOT NULL,
                avatar_emoji TEXT NOT NULL,
                times_used INTEGER NOT NULL DEFAULT 0,
                effectiveness_score REAL NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                sessions_count INTEGER NOT NULL,
                most_engaged_tags TEXT NOT NULL,
                least_engaged_tags TEXT NOT NULL,
                personas_favorited TEXT NOT NULL,
                ignored_perspective_types TEXT NOT NULL,
                override_frequency REAL NOT NULL,
                avg_rounds_before_ending REAL NOT NULL,
                position_change_rate REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                extraction_status TEXT NOT NULL,
                extracted_text_preview TEXT NOT NULL,
                extracted_char_count INTEGER NOT NULL,
                extracted_text TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        personas_count = connection.execute(
            "SELECT COUNT(*) AS count FROM personas"
        ).fetchone()["count"]
        if personas_count == 0:
            seed_personas = json.loads(PERSONA_SEED_PATH.read_text())
            connection.executemany(
                """
                INSERT INTO personas (
                    id, name, creator_id, forked_from, visibility, summary,
                    identity_anchor, epistemic_style, cognitive_biases,
                    argumentative_voice, opinion_change_threshold, tags,
                    avatar_emoji, times_used, effectiveness_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        persona["id"],
                        persona["name"],
                        persona["creator_id"],
                        persona["forked_from"],
                        persona["visibility"],
                        persona["summary"],
                        persona["identity_anchor"],
                        persona["epistemic_style"],
                        json.dumps(persona["cognitive_biases"]),
                        persona["argumentative_voice"],
                        persona["opinion_change_threshold"],
                        json.dumps(persona["tags"]),
                        persona["avatar_emoji"],
                        persona["times_used"],
                        persona["effectiveness_score"],
                    )
                    for persona in seed_personas
                ],
            )

        profile_count = connection.execute(
            "SELECT COUNT(*) AS count FROM user_profile"
        ).fetchone()["count"]
        if profile_count == 0:
            profile = json.loads(PROFILE_SEED_PATH.read_text())
            connection.execute(
                """
                INSERT INTO user_profile (
                    id, sessions_count, most_engaged_tags, least_engaged_tags,
                    personas_favorited, ignored_perspective_types,
                    override_frequency, avg_rounds_before_ending,
                    position_change_rate
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile["sessions_count"],
                    json.dumps(profile["most_engaged_tags"]),
                    json.dumps(profile["least_engaged_tags"]),
                    json.dumps(profile["personas_favorited"]),
                    json.dumps(profile["ignored_perspective_types"]),
                    profile["override_frequency"],
                    profile["avg_rounds_before_ending"],
                    profile["position_change_rate"],
                ),
            )


def _row_to_persona(row: sqlite3.Row) -> Persona:
    return Persona(
        id=row["id"],
        name=row["name"],
        creator_id=row["creator_id"],
        forked_from=row["forked_from"],
        visibility=row["visibility"],
        summary=row["summary"],
        identity_anchor=row["identity_anchor"],
        epistemic_style=row["epistemic_style"],
        cognitive_biases=json.loads(row["cognitive_biases"]),
        argumentative_voice=row["argumentative_voice"],
        opinion_change_threshold=row["opinion_change_threshold"],
        tags=json.loads(row["tags"]),
        avatar_emoji=row["avatar_emoji"],
        times_used=row["times_used"],
        effectiveness_score=row["effectiveness_score"],
    )


def _row_to_document(row: sqlite3.Row) -> StoredDocument:
    return StoredDocument(
        id=row["id"],
        filename=row["filename"],
        mime_type=row["mime_type"],
        size_bytes=row["size_bytes"],
        extraction_status=row["extraction_status"],
        extracted_text_preview=row["extracted_text_preview"],
        extracted_char_count=row["extracted_char_count"],
        created_at=row["created_at"],
        storage_path=row["storage_path"],
        extracted_text=row["extracted_text"],
    )


def list_personas() -> list[Persona]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM personas ORDER BY visibility DESC, times_used DESC, name ASC"
        ).fetchall()
    return [_row_to_persona(row) for row in rows]


def get_persona(persona_id: str) -> Persona | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM personas WHERE id = ?",
            (persona_id,),
        ).fetchone()
    return _row_to_persona(row) if row else None


def create_persona(payload: CreatePersonaRequest, persona_id: str) -> Persona:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO personas (
                id, name, creator_id, forked_from, visibility, summary,
                identity_anchor, epistemic_style, cognitive_biases,
                argumentative_voice, opinion_change_threshold, tags,
                avatar_emoji, times_used, effectiveness_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                persona_id,
                payload.name,
                payload.creator_id,
                None,
                payload.visibility,
                payload.summary,
                payload.identity_anchor,
                payload.epistemic_style,
                json.dumps([bias.model_dump() for bias in payload.cognitive_biases]),
                payload.argumentative_voice,
                payload.opinion_change_threshold,
                json.dumps(payload.tags),
                payload.avatar_emoji,
                0,
                0.0,
            ),
        )
    persona = get_persona(persona_id)
    assert persona is not None
    return persona


def increment_persona_usage(persona_ids: list[str]) -> None:
    with get_connection() as connection:
        connection.executemany(
            "UPDATE personas SET times_used = times_used + 1 WHERE id = ?",
            [(persona_id,) for persona_id in persona_ids],
        )


def get_profile() -> UserReasoningProfile:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    return UserReasoningProfile(
        sessions_count=row["sessions_count"],
        most_engaged_tags=json.loads(row["most_engaged_tags"]),
        least_engaged_tags=json.loads(row["least_engaged_tags"]),
        personas_favorited=json.loads(row["personas_favorited"]),
        ignored_perspective_types=json.loads(row["ignored_perspective_types"]),
        override_frequency=row["override_frequency"],
        avg_rounds_before_ending=row["avg_rounds_before_ending"],
        position_change_rate=row["position_change_rate"],
    )


def create_document(
    *,
    document_id: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
    extraction_status: str,
    extracted_text_preview: str,
    extracted_char_count: int,
    extracted_text: str,
    storage_path: str,
) -> StoredDocument:
    created_at = datetime.now(UTC).isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO documents (
                id, filename, mime_type, size_bytes, extraction_status,
                extracted_text_preview, extracted_char_count, extracted_text,
                storage_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                filename,
                mime_type,
                size_bytes,
                extraction_status,
                extracted_text_preview,
                extracted_char_count,
                extracted_text,
                storage_path,
                created_at,
            ),
        )
    document = get_document(document_id)
    assert document is not None
    return document


def get_document(document_id: str) -> StoredDocument | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
    return _row_to_document(row) if row else None


def get_documents(document_ids: list[str]) -> list[StoredDocument]:
    documents: list[StoredDocument] = []
    for document_id in document_ids:
        document = get_document(document_id)
        if document is not None:
            documents.append(document)
    return documents


def delete_document(document_id: str) -> UploadedDocument | None:
    document = get_document(document_id)
    if document is None:
        return None

    with get_connection() as connection:
        connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    file_path = Path(document.storage_path)
    if file_path.exists():
        file_path.unlink()

    return UploadedDocument(**document.model_dump())
