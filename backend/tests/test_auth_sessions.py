"""owner-auth: server-side, revocable login sessions."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.accounts import ensure_owner
from app.auth.sessions import (
    create_auth_session,
    find_auth_session,
    hash_token,
    revoke,
)
from app.db.models import AuthSession
from conftest import OWNER_PASSWORD

DAYS = 14


@pytest.fixture
def accounts(db_session: Session) -> Iterator[Session]:
    db_session.execute(text("TRUNCATE TABLE users CASCADE"))
    db_session.commit()
    yield db_session
    db_session.rollback()


def _owner(accounts: Session):
    record = ensure_owner(accounts, "owner@example.com", OWNER_PASSWORD)
    accounts.flush()
    return record.id


def test_only_the_tokens_hash_is_stored(accounts: Session) -> None:
    user_id = _owner(accounts)
    issued = create_auth_session(accounts, user_id, days=DAYS)

    assert issued.token is not None
    row = accounts.execute(select(AuthSession)).scalar_one()
    assert row.token_hash == hash_token(issued.token)
    assert issued.token not in row.token_hash


def test_a_live_token_resolves_to_its_owner(accounts: Session) -> None:
    user_id = _owner(accounts)
    issued = create_auth_session(accounts, user_id, days=DAYS)
    assert issued.token is not None

    found = find_auth_session(accounts, issued.token, days=DAYS)
    assert found is not None
    assert found.user_id == user_id
    assert found.email == "owner@example.com"
    assert found.token is None, "the raw token is returned only on creation"


def test_a_token_the_service_never_issued_resolves_to_nothing(accounts: Session) -> None:
    assert find_auth_session(accounts, "made-up-token", days=DAYS) is None


def test_an_expired_session_resolves_to_nothing(accounts: Session) -> None:
    user_id = _owner(accounts)
    issued = create_auth_session(accounts, user_id, days=DAYS)
    assert issued.token is not None

    row = accounts.execute(select(AuthSession)).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    accounts.flush()

    assert find_auth_session(accounts, issued.token, days=DAYS) is None


def test_a_revoked_session_resolves_to_nothing_and_is_kept(accounts: Session) -> None:
    user_id = _owner(accounts)
    issued = create_auth_session(accounts, user_id, days=DAYS)
    assert issued.token is not None

    assert revoke(accounts, issued.token) is True
    assert find_auth_session(accounts, issued.token, days=DAYS) is None
    row = accounts.execute(select(AuthSession)).scalar_one()
    assert row.revoked_at is not None

    assert revoke(accounts, issued.token) is False, "revoking twice is not an error"
    assert revoke(accounts, "made-up-token") is False


def test_a_session_past_half_its_life_slides_forward(accounts: Session) -> None:
    user_id = _owner(accounts)
    issued = create_auth_session(accounts, user_id, days=DAYS)
    assert issued.token is not None

    row = accounts.execute(select(AuthSession)).scalar_one()
    row.expires_at = datetime.now(UTC) + timedelta(days=1)
    accounts.flush()

    found = find_auth_session(accounts, issued.token, days=DAYS)
    assert found is not None
    assert found.expires_at > datetime.now(UTC) + timedelta(days=DAYS - 1)


def test_a_fresh_session_is_not_rewritten_on_every_request(accounts: Session) -> None:
    user_id = _owner(accounts)
    issued = create_auth_session(accounts, user_id, days=DAYS)
    assert issued.token is not None
    original = accounts.execute(select(AuthSession)).scalar_one().expires_at

    find_auth_session(accounts, issued.token, days=DAYS)
    assert accounts.execute(select(AuthSession)).scalar_one().expires_at == original


def test_deleting_the_user_takes_its_sessions(accounts: Session) -> None:
    user_id = _owner(accounts)
    create_auth_session(accounts, user_id, days=DAYS)
    accounts.flush()

    accounts.execute(text("DELETE FROM users"))
    accounts.flush()

    assert accounts.execute(select(AuthSession)).first() is None
