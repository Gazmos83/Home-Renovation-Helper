"""owner-auth: the single owner account, created from configuration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.accounts import ensure_owner, get_owner
from app.auth.passwords import hash_password, verify_password
from app.config import ConfigurationError, load_settings
from app.db.models import User
from conftest import OWNER_PASSWORD


@pytest.fixture
def accounts(db_session: Session) -> Iterator[Session]:
    db_session.execute(text("TRUNCATE TABLE users CASCADE"))
    db_session.commit()
    yield db_session
    db_session.rollback()


def test_first_start_creates_the_owner_with_the_configured_password(accounts: Session) -> None:
    ensure_owner(accounts, "Owner@Example.com", OWNER_PASSWORD)
    accounts.commit()

    owner = get_owner(accounts)
    assert owner is not None
    assert owner.email == "owner@example.com", "stored lower-cased"
    row = accounts.execute(select(User)).scalar_one()
    assert verify_password(OWNER_PASSWORD, row.password_hash)
    assert OWNER_PASSWORD not in row.password_hash


def test_a_later_start_does_not_overwrite_a_changed_hash(accounts: Session) -> None:
    ensure_owner(accounts, "owner@example.com", OWNER_PASSWORD)
    accounts.commit()
    # Simulate a password the owner changed later.
    changed = hash_password("a-different-password-entirely")
    row = accounts.execute(select(User)).scalar_one()
    row.password_hash = changed
    accounts.commit()

    ensure_owner(accounts, "owner@example.com", OWNER_PASSWORD)
    accounts.commit()

    row = accounts.execute(select(User)).scalar_one()
    assert row.password_hash == changed, "the configured password must not overwrite the stored hash"
    assert accounts.execute(select(User)).scalars().all().__len__() == 1


def test_a_weak_configured_password_fails_startup_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigurationError) as caught:
        load_settings(
            database_url="postgresql://u:p@localhost:5432/d",
            openrouter_api_key="sk-or-test",
            cors_origins="http://localhost:5173",
            owner_email="owner@example.com",
            owner_password="short",
            _env_file=None,
        )
    assert "OWNER_PASSWORD" in str(caught.value)
