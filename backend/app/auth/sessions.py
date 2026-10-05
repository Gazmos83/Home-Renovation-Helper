"""Login sessions: server-side, revocable, and stored only as a hash.

The token is opaque and unguessable, only its SHA-256 reaches the database, and
a value the service never issued resolves to nothing rather than to a session an
attacker picked. The session expires, slides forward while in use, and can be
revoked by signing out (owner-auth).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthSession, User

TOKEN_BYTES: Final = 32

# How much of the remaining life may elapse before the expiry is pushed
# forward. Without a threshold every request would write to the row.
_SLIDE_AFTER: Final = 0.5


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthSessionRecord:
    """A live login. `token` is present only on the call that created it."""

    id: UUID
    user_id: UUID
    email: str
    expires_at: datetime
    token: str | None = None


def create_auth_session(
    session: Session, user_id: UUID, *, days: int
) -> AuthSessionRecord:
    """Issue a login. The raw token is returned once and never stored."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = datetime.now(UTC)
    row = AuthSession(
        id=uuid4(),
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(days=days),
    )
    session.add(row)
    session.flush()
    user = session.get(User, user_id)
    assert user is not None  # the caller just authenticated against it
    return AuthSessionRecord(
        id=row.id,
        user_id=user_id,
        email=user.email,
        expires_at=row.expires_at,
        token=token,
    )


def find_auth_session(
    session: Session, token: str, *, days: int
) -> AuthSessionRecord | None:
    """The live login a raw token names, or `None`.

    `None` covers every non-live case — unknown token, expired, revoked — so a
    caller cannot tell them apart and none of them is an error. A session that
    is past half its life is slid forward, so an account in daily use is not
    signed out on a fixed schedule.
    """
    row = session.execute(
        select(AuthSession).where(AuthSession.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None

    now = datetime.now(UTC)
    if row.expires_at <= now:
        return None

    row.last_seen_at = now
    full_life = timedelta(days=days)
    if row.expires_at - now < full_life * _SLIDE_AFTER:
        row.expires_at = now + full_life

    user = session.get(User, row.user_id)
    if user is None:  # pragma: no cover - the cascade makes this unreachable
        return None
    return AuthSessionRecord(
        id=row.id,
        user_id=row.user_id,
        email=user.email,
        expires_at=row.expires_at,
    )


def revoke(session: Session, token: str) -> bool:
    """Revoke the login a raw token names. False when it named none."""
    row = session.execute(
        select(AuthSession).where(AuthSession.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(UTC)
    session.flush()
    return True
