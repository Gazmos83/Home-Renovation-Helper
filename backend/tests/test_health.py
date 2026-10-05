"""service-foundation: health reporting."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from conftest import UNREACHABLE_DSN

SECRET_PASSWORD = "sup3rs3cret"


def test_healthy_when_database_is_reachable(settings: Settings) -> None:
    response = TestClient(create_app(settings)).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ok"
    assert body["database"] == "reachable"


def test_not_ready_when_database_refuses_connections() -> None:
    settings = Settings(
        database_url=f"postgresql://postgres:{SECRET_PASSWORD}@127.0.0.1:1/none",
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email="owner@example.com",
        owner_password="an-initial-owner-password",
        gateway_probe_enabled=False,
        _env_file=None,
    )
    response = TestClient(create_app(settings)).get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["service"] == "ok", "the process is up even though the database is not"
    assert body["database"] == "unreachable"

    raw = response.text
    assert SECRET_PASSWORD not in raw
    assert "Traceback" not in raw
    assert "psycopg" not in raw


def test_unreachable_dsn_constant_is_actually_unreachable() -> None:
    from app.db.session import database_reachable, make_engine

    assert database_reachable(make_engine(UNREACHABLE_DSN)) is False
