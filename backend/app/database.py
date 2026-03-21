from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def create_engine_from_settings(settings: Settings) -> Engine:
    connect_args = {}
    if settings.app_database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
        database_path = settings.app_database_url.removeprefix("sqlite:///")
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        settings.app_database_url,
        connect_args=connect_args,
        future=True,
    )


@lru_cache(maxsize=8)
def get_session_factory(database_url: str) -> sessionmaker[Session]:
    settings = get_settings()
    if settings.app_database_url != database_url:
        settings = settings.model_copy(update={"app_database_url": database_url})
    engine = create_engine_from_settings(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def get_engine(settings: Settings | None = None) -> Engine:
    resolved = settings or get_settings()
    return get_session_factory(resolved.app_database_url).kw["bind"]


def SessionLocal(settings: Settings | None = None) -> sessionmaker[Session]:
    resolved = settings or get_settings()
    return get_session_factory(resolved.app_database_url)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()()
    try:
        yield session
    finally:
        session.close()
