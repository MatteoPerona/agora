from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from fastapi import Request, Response

from .config import Settings
from .models import RuntimeLLMConfig

SESSION_COOKIE_NAME = "agora_session"
SESSION_TTL = timedelta(days=30)


@dataclass
class _StoredRuntimeConfig:
    value: RuntimeLLMConfig
    updated_at: datetime


_SESSION_RUNTIME_CONFIG: dict[str, _StoredRuntimeConfig] = {}
_STORE_LOCK = Lock()
_LAST_PRUNED = datetime.now(UTC)


def get_session_id(request: Request, response: Response) -> str:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        session_id = uuid4().hex
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
            max_age=int(SESSION_TTL.total_seconds()),
            path="/",
        )
    return session_id


def clear_runtime_config(session_id: str) -> None:
    with _STORE_LOCK:
        _SESSION_RUNTIME_CONFIG.pop(session_id, None)


def get_runtime_config(session_id: str) -> RuntimeLLMConfig | None:
    _prune_stale_configs()
    stored = _SESSION_RUNTIME_CONFIG.get(session_id)
    return stored.value if stored else None


def set_runtime_config(session_id: str, config: RuntimeLLMConfig) -> None:
    with _STORE_LOCK:
        _SESSION_RUNTIME_CONFIG[session_id] = _StoredRuntimeConfig(
            value=config,
            updated_at=datetime.now(UTC),
        )


def build_effective_settings(base_settings: Settings, runtime_config: RuntimeLLMConfig | None = None) -> Settings:
    if runtime_config is None:
        return base_settings

    updates: dict[str, object] = {}
    if runtime_config.provider is not None:
        provider = runtime_config.provider.strip()
        if provider:
            updates["sim_provider"] = provider
    if runtime_config.model is not None:
        model = runtime_config.model.strip()
        if model:
            updates["sim_model"] = model
    if runtime_config.selector_model is not None:
        value = runtime_config.selector_model.strip()
        updates["sim_selector_model"] = value or None
    if runtime_config.summary_model is not None:
        value = runtime_config.summary_model.strip()
        updates["sim_summary_model"] = value or None
    if runtime_config.base_url is not None:
        value = runtime_config.base_url.strip()
        updates["sim_base_url"] = value or None
    if runtime_config.api_key is not None:
        key = runtime_config.api_key.strip()
        updates["sim_api_key"] = key or None

    resolved = base_settings.model_copy(update=updates)
    return resolved.validate_provider_settings()


def _prune_stale_configs() -> None:
    global _LAST_PRUNED
    now = datetime.now(UTC)
    if now - _LAST_PRUNED < timedelta(minutes=5):
        return

    cutoff = now - SESSION_TTL
    with _STORE_LOCK:
        stale = [
            session_id
            for session_id, config in _SESSION_RUNTIME_CONFIG.items()
            if now - config.updated_at > SESSION_TTL
        ]
        for session_id in stale:
            _SESSION_RUNTIME_CONFIG.pop(session_id, None)
        _LAST_PRUNED = now
