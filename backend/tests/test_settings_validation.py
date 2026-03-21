from __future__ import annotations

import pytest

from backend.app.config import Settings


@pytest.mark.parametrize(
    "provider",
    ["openai", "openai-compatible", "openai-compatible-model", "anthropic"],
)
def test_real_provider_rejects_missing_api_key(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    monkeypatch.setenv("SIM_PROVIDER", provider)
    monkeypatch.setenv("SIM_MODEL", "provider-model")

    if provider.startswith("openai-compatible"):
        monkeypatch.setenv("SIM_BASE_URL", "https://example.invalid")
    else:
        monkeypatch.delenv("SIM_BASE_URL", raising=False)

    monkeypatch.delenv("SIM_API_KEY", raising=False)

    with pytest.raises(ValueError, match=r"SIM_API_KEY must be set for provider"):
        Settings(_env_file=None)


def test_openai_compatible_provider_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_PROVIDER", "openai-compatible-model")
    monkeypatch.setenv("SIM_MODEL", "provider-model")
    monkeypatch.setenv("SIM_API_KEY", "test-key")
    monkeypatch.delenv("SIM_BASE_URL", raising=False)

    with pytest.raises(ValueError, match=r"SIM_BASE_URL must be set for provider"):
        Settings(_env_file=None)


def test_stub_provider_does_not_require_model_key_or_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_PROVIDER", "stub")
    monkeypatch.delenv("SIM_MODEL", raising=False)
    monkeypatch.delenv("SIM_API_KEY", raising=False)
    monkeypatch.delenv("SIM_BASE_URL", raising=False)

    settings = Settings(_env_file=None)
    assert settings.normalized_provider == "stub"
