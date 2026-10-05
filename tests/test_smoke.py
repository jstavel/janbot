from importlib.metadata import version

from fastapi.testclient import TestClient

import janbot
from janbot.api.main import app


def test_package_imports() -> None:
    assert janbot is not None


def test_dependencies_importable() -> None:
    assert version("fastapi") == "0.142.2"
    assert version("pydantic") == "2.13.5"
    assert version("dspy") == "3.4.0"
    assert version("chromadb") == "1.5.9"
    assert version("orgparse") == "0.5.20260926"


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
