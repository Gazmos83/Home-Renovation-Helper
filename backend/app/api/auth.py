"""Sign-in, sign-out and who-am-I (owner-auth).

Three ungated routes: this is how the owner *obtains* the credential the gates
check. There is no registration and no bootstrap — the owner is created from
configuration at startup. A failed sign-in answers one generic 401 whether the
email is unknown or the password wrong, and `verify_password` does the same work
in both cases so timing cannot tell them apart either.
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api import limits
from app.api.session import (
    clear_session_cookie,
    get_db_session,
    resolve_login,
    set_session_cookie,
)
from app.auth.accounts import find_by_email
from app.auth.passwords import verify_password
from app.auth.sessions import create_auth_session, revoke
from app.config import Settings

logger = logging.getLogger("app")

router = APIRouter(prefix="/auth", tags=["auth"])

BAD_CREDENTIALS = "the email or password is not correct"
NOT_SIGNED_IN = "not signed in"


class CredentialsIn(BaseModel):
    """What sign-in accepts. No role field of any kind."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class AccountOut(BaseModel):
    id: str
    email: str


def _out(user_id: UUID, email: str) -> AccountOut:
    return AccountOut(id=str(user_id), email=email)


@router.post("/login")
def login(
    body: CredentialsIn,
    request: Request,
    response: Response,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AccountOut:
    settings: Settings = request.app.state.settings
    # Before hashing: a throttled attempt costs no argon2 work.
    limits.check_auth(request, body.email)
    row = find_by_email(db_session, body.email)
    # Runs a full verification either way, so an unknown email costs what a
    # wrong password costs.
    if not verify_password(body.password, row.password_hash if row else None):
        logger.info("login refused", extra={"context": {"outcome": "bad_credentials"}})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=BAD_CREDENTIALS)
    assert row is not None

    issued = create_auth_session(db_session, row.id, days=settings.auth_session_days)
    db_session.commit()
    assert issued.token is not None
    set_session_cookie(
        response,
        issued.token,
        secure=settings.session_cookie_secure,
        max_age=settings.auth_session_days * 24 * 60 * 60,
    )
    logger.info("login accepted", extra={"context": {"user_id": str(row.id)}})
    return _out(row.id, row.email)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, bool]:
    """Revoke this sign-in. Silent when there was none — signing out twice is
    not an error."""
    settings: Settings = request.app.state.settings
    token = request.cookies.get("hr_session")
    if token:
        revoke(db_session, token)
        db_session.commit()
    clear_session_cookie(response, secure=settings.session_cookie_secure)
    logger.info("logout", extra={"context": {"had_cookie": bool(token)}})
    return {"signed_out": True}


@router.get("/me")
def me(
    request: Request,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AccountOut:
    settings: Settings = request.app.state.settings
    login_record = resolve_login(db_session, request, days=settings.auth_session_days)
    db_session.commit()
    if login_record is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=NOT_SIGNED_IN)
    return _out(login_record.user_id, login_record.email)
