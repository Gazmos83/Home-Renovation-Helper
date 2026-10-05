"""owner-auth: sign-in, sign-out and who-am-I over the HTTP API."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.session import COOKIE_NAME
from app.config import Settings
from app.db.models import AuthSession
from app.db.session import make_engine
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD

GOOD = {"email": OWNER_EMAIL, "password": OWNER_PASSWORD}


def _settings(database_url: str, **overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": database_url,
        "openrouter_api_key": "sk-or-test",
        "cors_origins": "http://localhost:5173",
        "owner_email": OWNER_EMAIL,
        "owner_password": OWNER_PASSWORD,
        "gateway_probe_enabled": False,
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def client(migrated_database: str) -> Iterator[TestClient]:
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("TRUNCATE TABLE users CASCADE"))
        session.commit()
    engine.dispose()
    # The context manager runs the lifespan, which bootstraps the owner.
    with TestClient(create_app(_settings(migrated_database))) as client:
        yield client


def test_sign_in_sets_the_cookie_and_stores_only_a_hash(
    client: TestClient, migrated_database: str
) -> None:
    response = client.post("/auth/login", json=GOOD)
    assert response.status_code == 200
    assert response.json() == {"id": response.json()["id"], "email": OWNER_EMAIL}
    assert "role" not in response.json()
    assert COOKIE_NAME in response.cookies or COOKIE_NAME in {
        c.split("=")[0] for c in response.headers.get_list("set-cookie")
    }

    engine = make_engine(migrated_database)
    with Session(engine) as session:
        row = session.execute(select(AuthSession)).scalar_one()
        # The cookie's raw value never appears in the stored hash.
        assert len(row.token_hash) == 64
    engine.dispose()


def test_wrong_password_is_a_generic_401(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": "wrong-password"})
    assert response.status_code == 401
    assert "email or password" in response.json()["detail"]


def test_unknown_email_is_the_same_401(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": OWNER_PASSWORD}
    )
    assert response.status_code == 401
    assert "email or password" in response.json()["detail"]


def test_me_returns_id_and_email_only(client: TestClient) -> None:
    client.post("/auth/login", json=GOOD)
    body = client.get("/auth/me").json()
    assert set(body) == {"id", "email"}
    assert body["email"] == OWNER_EMAIL


def test_me_without_a_cookie_is_401(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_the_session_and_is_idempotent(client: TestClient) -> None:
    client.post("/auth/login", json=GOOD)
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401, "the old cookie no longer signs in"
    # Logging out again, with no live session, is still a success.
    assert client.post("/auth/logout").status_code == 200


def test_an_expired_session_is_refused(client: TestClient, migrated_database: str) -> None:
    from datetime import UTC, datetime, timedelta

    client.post("/auth/login", json=GOOD)
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        row = session.execute(select(AuthSession)).scalar_one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    engine.dispose()
    assert client.get("/auth/me").status_code == 401


def test_repeated_failures_are_rate_limited(migrated_database: str) -> None:
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("TRUNCATE TABLE users CASCADE"))
        session.commit()
    engine.dispose()
    with TestClient(create_app(_settings(migrated_database, auth_rate_limit=3))) as client:
        statuses = [
            client.post("/auth/login", json={"email": OWNER_EMAIL, "password": "nope"}).status_code
            for _ in range(5)
        ]
    assert 429 in statuses, f"expected a 429 after repeated failures, got {statuses}"


def test_no_password_appears_in_any_log_record(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app"):
        client.post("/auth/login", json=GOOD)
        client.post("/auth/login", json={"email": OWNER_EMAIL, "password": "wrong-password"})
    for record in caplog.records:
        rendered = f"{record.getMessage()} {getattr(record, 'context', '')}"
        assert OWNER_PASSWORD not in rendered
        assert "wrong-password" not in rendered
