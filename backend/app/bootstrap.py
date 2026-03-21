from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
import sqlite3

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import BASE_DIR, Settings
from .database import SessionLocal
from .entities import PersonaEntity, UserProfileEntity


def ensure_directories(settings: Settings) -> None:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.simulations_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.app_database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


def run_migrations(settings: Settings) -> None:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.app_database_url)
    command.upgrade(config, "head")


def seed_reference_data(settings: Settings) -> None:
    with SessionLocal(settings)() as session:
        _seed_personas(session, settings.personas_seed_path)
        _seed_user_profile(session, settings.user_profile_seed_path)
        session.commit()


def initialize_app(settings: Settings) -> None:
    ensure_directories(settings)
    _prepare_legacy_database(settings)
    run_migrations(settings)
    seed_reference_data(settings)


def _prepare_legacy_database(settings: Settings) -> None:
    if not settings.app_database_url.startswith("sqlite:///"):
        return

    database_path = Path(settings.app_database_url.removeprefix("sqlite:///"))
    if not database_path.exists():
        return

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    legacy_markers = bool({"user_profile", "documents"} & tables) and "user_profiles" not in tables
    if "alembic_version" in tables and not legacy_markers:
        return

    if not tables:
        return

    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    backup_path = database_path.with_suffix(f".legacy-{timestamp}.sqlite3")
    shutil.move(str(database_path), str(backup_path))


def _seed_personas(session: Session, seed_path: Path) -> None:
    existing = session.scalar(select(PersonaEntity.id).limit(1))
    if existing is not None:
        return

    seed_personas = json.loads(seed_path.read_text())
    for persona in seed_personas:
        session.add(
            PersonaEntity(
                id=persona["id"],
                name=persona["name"],
                creator_id=persona["creator_id"],
                forked_from=persona["forked_from"],
                visibility=persona["visibility"],
                summary=persona["summary"],
                identity_anchor=persona["identity_anchor"],
                epistemic_style=persona["epistemic_style"],
                cognitive_biases=persona["cognitive_biases"],
                argumentative_voice=persona["argumentative_voice"],
                opinion_change_threshold=persona["opinion_change_threshold"],
                tags=persona["tags"],
                avatar_emoji=persona["avatar_emoji"],
                times_used=persona["times_used"],
                effectiveness_score=persona["effectiveness_score"],
            )
        )


def _seed_user_profile(session: Session, seed_path: Path) -> None:
    existing = session.get(UserProfileEntity, 1)
    if existing is not None:
        return

    profile = json.loads(seed_path.read_text())
    session.add(
        UserProfileEntity(
            id=1,
            sessions_count=profile["sessions_count"],
            most_engaged_tags=profile["most_engaged_tags"],
            least_engaged_tags=profile["least_engaged_tags"],
            personas_favorited=profile["personas_favorited"],
            ignored_perspective_types=profile["ignored_perspective_types"],
            override_frequency=profile["override_frequency"],
            avg_rounds_before_ending=profile["avg_rounds_before_ending"],
            position_change_rate=profile["position_change_rate"],
        )
    )
