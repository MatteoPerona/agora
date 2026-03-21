from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

for existing in list(sys.path):
    if "Projects/Mozzi-dep" in existing:
        sys.path.remove(existing)

backend_module: ModuleType = sys.modules.get("backend") or types.ModuleType("backend")
backend_module.__path__ = [str(BACKEND_ROOT)]
sys.modules["backend"] = backend_module


@pytest.fixture()
def test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{tmp_path / 'app.sqlite3'}")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("SIMULATIONS_DIR", str(tmp_path / "simulations"))
    monkeypatch.setenv("SIM_PROVIDER", "stub")
    monkeypatch.setenv("SIM_MODEL", "stub")
    monkeypatch.delenv("SIM_API_KEY", raising=False)
    monkeypatch.delenv("SIM_BASE_URL", raising=False)

    from backend.app.config import get_settings
    from backend.app.database import get_session_factory

    get_settings.cache_clear()
    get_session_factory.cache_clear()

    for module_name in list(sys.modules):
        if module_name == "backend.app.main" or module_name.startswith("backend.app."):
            del sys.modules[module_name]

    yield tmp_path

    get_settings.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture()
def client(test_env: Path) -> TestClient:
    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def app_harness(test_env: Path, client: TestClient):
    app_module = importlib.import_module("backend.app.main")
    yield SimpleNamespace(
        client=client,
        app_module=app_module,
    )
