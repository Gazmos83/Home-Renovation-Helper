"""The owner's session cookie (owner-auth).

One cookie, `hr_session`, carrying an opaque unguessable token. It is never
trusted directly: every request resolves it to an `auth_sessions` row by the
*hash* of the value, so a leaked database does not yield a usable cookie and a
value the service never issued resolves to nothing. There is no anonymous
session cookie — this is a single-owner product (CLAUDE.md §1).
"""

from __future__ import annotations

from typing import Final

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.auth.sessions import AuthSessionRecord, find_auth_session

COOKIE_NAME: Final = "hr_session"


def set_session_cookie(response: Response, token: str, *, secure: bool, max_age: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(
        COOKIE_NAME, httponly=True, samesite="lax", secure=secure, path="/"
    )


def resolve_login(
    db_session: Session, request: Request, *, days: int
) -> AuthSessionRecord | None:
    """The owner behind the session cookie, or `None` for an unauthenticated
    request. Every non-live case — no cookie, a token we never issued, expired,
    revoked — is `None` and not an error."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return find_auth_session(db_session, token, days=days)


def get_db_session(request: Request):
    with Session(request.app.state.engine) as db_session:
        yield db_session
