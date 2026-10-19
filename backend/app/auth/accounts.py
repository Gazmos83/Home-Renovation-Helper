"""The owner account and its members: ensure the owner exists, find it, and let
the owner add or remove members (owner-auth).

There is no registration and no role column. The owner is the earliest account,
created from configuration on first start and never overwritten afterwards, so a
password changed later survives restarts. Every later account is a member: it
uses the Studio with its own house file, never the developer panel. Every function takes a SQLAlchemy
session and plain values; nothing here reads a request, a cookie or a model
argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.db.models import User


class AccountExists(ValueError):
    """An account with this email already exists."""


class OwnerAccount(ValueError):
    """The owner account cannot be removed."""


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    email: str
    created_at: datetime


def normalise_email(email: str) -> str:
    return email.strip().lower()


def _record(row: User) -> UserRecord:
    return UserRecord(id=row.id, email=row.email, created_at=row.created_at)


def find_by_email(session: Session, email: str) -> User | None:
    """The row itself, because the caller needs `password_hash` to verify."""
    return session.execute(
        select(User).where(User.email == normalise_email(email))
    ).scalar_one_or_none()


def get_owner(session: Session) -> UserRecord | None:
    """The single owner account, or `None` before it has been created."""
    row = session.execute(select(User).order_by(User.created_at)).scalars().first()
    return _record(row) if row is not None else None


def _account_count(session: Session) -> int:
    return int(session.execute(select(func.count()).select_from(User)).scalar_one())


def ensure_owner(session: Session, email: str, password: str) -> UserRecord:
    """Create the owner from configuration when the account table is empty.

    When an account already exists, the configured password does NOT overwrite
    the stored hash — a password changed later survives restarts. Raises
    `WeakPassword` if the configured password is too short, though configuration
    validation catches that before startup reaches here.
    """
    existing = get_owner(session)
    if existing is not None:
        return existing

    # Hashed before the row exists, so a refused weak password leaves no
    # half-made account behind.
    digest = hash_password(password)
    row = User(id=uuid4(), email=normalise_email(email), password_hash=digest)
    session.add(row)
    session.flush()
    return _record(row)


def list_accounts(session: Session) -> list[UserRecord]:
    """Every account, the owner first."""
    rows = session.execute(select(User).order_by(User.created_at)).scalars()
    return [_record(row) for row in rows]


def create_member(session: Session, email: str, password: str) -> UserRecord:
    """Add a member account. Raises `AccountExists` for a known email and
    `WeakPassword` for a short password; the owner must already exist, so a
    member can never become the owner."""
    if get_owner(session) is None:
        raise RuntimeError("the owner account does not exist yet")
    if find_by_email(session, email) is not None:
        raise AccountExists(f"an account for {normalise_email(email)} already exists")
    digest = hash_password(password)
    row = User(id=uuid4(), email=normalise_email(email), password_hash=digest)
    session.add(row)
    session.flush()
    return _record(row)


def delete_member(session: Session, user_id: UUID) -> bool:
    """Remove a member and its sign-ins. False when no such account exists;
    raises `OwnerAccount` for the owner."""
    owner = get_owner(session)
    if owner is not None and owner.id == user_id:
        raise OwnerAccount("the owner account cannot be removed")
    removed = session.execute(delete(User).where(User.id == user_id)).rowcount
    session.flush()
    return bool(removed)
