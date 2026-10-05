"""owner-auth: the owner gate and the developer gate.

Exercised against a miniature app rather than the real routers, so what is
asserted is each gate's own decision — who is admitted, what a refusal says, and
that a refused request never reaches the handler.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.gate import REFUSAL, require_dev, require_owner
from app.api.session import COOKIE_NAME
from app.auth.accounts import ensure_owner
from app.auth.sessions import AuthSessionRecord, create_auth_session
from app.config import Settings
from app.db.session import make_engine
from conftest import OWNER_EMAIL, OWNER_PASSWORD


def make_app(settings: Settings, database_url: str) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings
    app.state.engine = make_engine(database_url)

    @app.get("/home")
    def home(owner: Annotated[AuthSessionRecord, Depends(require_owner)]) -> dict[str, str]:
        return {"email": owner.email}

    @app.get("/admin/panel")
    def panel(owner: Annotated[AuthSessionRecord, Depends(require_dev)]) -> dict[str, str]:
        return {"email": owner.email}

    return app


def _settings(database_url: str, *, dev: bool) -> Settings:
    return Settings(
        database_url=database_url,
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        dev_panel_enabled=dev,
        _env_file=None,
    )


@pytest.fixture
def accounts(db_session: Session) -> Iterator[Session]:
    db_session.execute(text("TRUNCATE TABLE users CASCADE"))
    db_session.commit()
    yield db_session
    db_session.rollback()


def _sign_in(accounts: Session) -> str:
    record = ensure_owner(accounts, OWNER_EMAIL, OWNER_PASSWORD)
    accounts.flush()
    issued = create_auth_session(accounts, record.id, days=14)
    accounts.commit()
    assert issued.token is not None
    return issued.token


def test_a_valid_cookie_reaches_a_homeowner_route(
    accounts: Session, test_database_url: str
) -> None:
    token = _sign_in(accounts)
    client = TestClient(make_app(_settings(test_database_url, dev=False), test_database_url))
    client.cookies.set(COOKIE_NAME, token)
    response = client.get("/home")
    assert response.status_code == 200
    assert response.json()["email"] == OWNER_EMAIL


def test_no_cookie_is_refused_with_the_fixed_message(
    accounts: Session, test_database_url: str
) -> None:
    client = TestClient(make_app(_settings(test_database_url, dev=False), test_database_url))
    response = client.get("/home")
    assert response.status_code == 401
    assert response.json()["detail"] == REFUSAL


def test_an_owner_named_in_the_body_is_ignored(accounts: Session, test_database_url: str) -> None:
    client = TestClient(make_app(_settings(test_database_url, dev=False), test_database_url))
    # No cookie, but a body claiming an owner id: still refused, nothing read.
    response = client.request("GET", "/home", json={"owner_id": "whoever"})
    assert response.status_code == 401
    assert response.json()["detail"] == REFUSAL


def test_the_dev_route_runs_with_the_panel_enabled(
    accounts: Session, test_database_url: str
) -> None:
    token = _sign_in(accounts)
    client = TestClient(make_app(_settings(test_database_url, dev=True), test_database_url))
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/admin/panel").status_code == 200


def test_the_dev_route_is_404_with_the_panel_disabled(
    accounts: Session, test_database_url: str
) -> None:
    """Even with a valid cookie: the route's existence is hidden."""
    token = _sign_in(accounts)
    client = TestClient(make_app(_settings(test_database_url, dev=False), test_database_url))
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/admin/panel").status_code == 404


def test_the_dev_route_is_401_when_not_signed_in_with_the_panel_enabled(
    accounts: Session, test_database_url: str
) -> None:
    client = TestClient(make_app(_settings(test_database_url, dev=True), test_database_url))
    response = client.get("/admin/panel")
    assert response.status_code == 401
    assert response.json()["detail"] == REFUSAL
