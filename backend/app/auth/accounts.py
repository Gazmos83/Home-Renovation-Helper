"""The single owner account: ensure it exists, and find it (owner-auth).

There is no registration and no role model (CLAUDE.md §1). The owner is created
from configuration on first start and never overwritten afterwards, so a
password changed later survives restarts. Every function takes a SQLAlchemy
session and plain values; nothing here reads a request, a cookie or a model
argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.db.models import User


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
