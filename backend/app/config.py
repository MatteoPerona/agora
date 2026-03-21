from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR.parent / ".env"),
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_database_url: str = Field(
        default=f"sqlite:///{(DATA_DIR / 'agora.sqlite3').as_posix()}",
        alias="APP_DATABASE_URL",
    )
    personas_seed_path: Path = Field(
        default=DATA_DIR / "personas.json",
        alias="PERSONAS_SEED_PATH",
    )
    user_profile_seed_path: Path = Field(
        default=DATA_DIR / "user_profile.json",
        alias="USER_PROFILE_SEED_PATH",
    )
    uploads_dir: Path = Field(default=DATA_DIR / "uploads", alias="UPLOADS_DIR")
    simulations_dir: Path = Field(
        default=DATA_DIR / "simulations",
        alias="SIMULATIONS_DIR",
    )

    sim_provider: str = Field(default="stub", alias="SIM_PROVIDER")
    sim_model: str = Field(default="stub", alias="SIM_MODEL")
    sim_api_key: str | None = Field(default=None, alias="SIM_API_KEY")
    sim_base_url: str | None = Field(default=None, alias="SIM_BASE_URL")
    sim_summary_model: str | None = Field(default=None, alias="SIM_SUMMARY_MODEL")
    sim_selector_model: str | None = Field(default=None, alias="SIM_SELECTOR_MODEL")
    sim_max_concurrency: int = Field(default=8, alias="SIM_MAX_CONCURRENCY")

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "Settings":
        provider = self.normalized_provider
        if provider == "stub":
            return self

        if not self.sim_model:
            raise ValueError("SIM_MODEL must be set when using a real simulation provider.")

        if provider in {"openai-compatible-model", "openai", "anthropic"} and not self.sim_api_key:
            raise ValueError(f"SIM_API_KEY must be set for provider {provider}.")

        if provider == "openai-compatible-model" and not self.sim_base_url:
            raise ValueError("SIM_BASE_URL must be set for provider openai-compatible-model.")

        return self

    @property
    def normalized_provider(self) -> str:
        aliases = {
            "openai-compatible": "openai-compatible-model",
            "openai_compatible_model": "openai-compatible-model",
        }
        lowered = self.sim_provider.strip().lower()
        return aliases.get(lowered, lowered)

    @property
    def summary_model(self) -> str:
        return self.sim_summary_model or self.sim_model

    @property
    def selector_model(self) -> str:
        return self.sim_selector_model or self.sim_model


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
