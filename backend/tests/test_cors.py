"""service-foundation: cross-origin access limited to configured origins."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

CONFIGURED = "http://localhost:5173"
UNCONFIGURED = "http://evil.example"


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_configured_origin_is_granted_with_credentials(settings: Settings) -> None:
    response = _client(settings).get("/health", headers={"Origin": CONFIGURED})
    assert response.headers["access-control-allow-origin"] == CONFIGURED
    assert response.headers["access-control-allow-credentials"] == "true"


def test_unconfigured_origin_is_not_granted(settings: Settings) -> None:
    response = _client(settings).get("/health", headers={"Origin": UNCONFIGURED})
    granted = response.headers.get("access-control-allow-origin")
    assert granted != UNCONFIGURED
    assert granted != "*"


def test_preflight_from_configured_origin_is_allowed(settings: Settings) -> None:
    response = _client(settings).options(
        "/health",
        headers={"Origin": CONFIGURED, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code in (200, 204)
    assert response.headers["access-control-allow-origin"] == CONFIGURED


def test_no_response_ever_returns_a_wildcard_origin(settings: Settings) -> None:
    client = _client(settings)
    for origin in (CONFIGURED, UNCONFIGURED, "null"):
        response = client.get("/health", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") != "*"


def test_startup_fails_on_a_wildcard_origin() -> None:
    with pytest.raises(Exception) as caught:
        Settings(
            database_url="postgresql://u:p@localhost:5432/d",
            openrouter_api_key="sk-or-test",
            cors_origins="*",
            owner_email="owner@example.com",
            owner_password="an-initial-owner-password",
            _env_file=None,
        )
    assert "wildcard" in str(caught.value)
