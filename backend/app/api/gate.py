"""The two gates every later route depends on (owner-auth).

`require_owner` admits a request only with a valid, unexpired, unrevoked session
cookie and resolves the owner from that cookie alone — never from a request
body, header or model output. `require_dev` is stricter: it additionally needs
the developer panel enabled by configuration and the owner account, not a member,
and answers 404 otherwise, so the homeowner surface shows no sign of the `/admin`
routes.

Never add a third gate or duplicate the logic: these two are what every gated
route depends on by name.

A member account is held to its own house file twice over: `AccountScope` sets the
request's scope (app/db/scope.py) so every query sees only its rows, and
`require_owner` refuses a path naming another account's piece, conversation,
upload or pricing (404), and any change to the data every account shares (403).
"""

from __future__ import annotations

import logging
from typing import Final
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.session import COOKIE_NAME
from app.auth.sessions import AuthSessionRecord, find_auth_session
from app.db import scope as account_scope
from app.db.models import CutListPricing, Piece, Thread, Upload

logger = logging.getLogger("app")

# What the caller is told. Deliberately fixed, so a refusal maps out nothing.
REFUSAL: Final = "sign-in is required"
SHARED_READ_ONLY: Final = "only the owner account can change this"

# Data every account shares (prices, stores, guidelines, hardware sheets): a member reads it only.
_SHARED_PREFIXES: Final = ("/price-list", "/snapshots", "/stores", "/guideline-notes", "/hardware-data")
_READS: Final = frozenset({"GET", "HEAD", "OPTIONS"})


def _refused() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=REFUSAL)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


def current_login(request: Request) -> AuthSessionRecord | None:
    """The owner behind the session cookie, or `None`.

    Opens its own short database session so a refused request returns before any
    parameter dependency runs. An unreachable store is not access.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    settings = request.app.state.settings
    try:
        with Session(request.app.state.engine) as db_session:
            found = find_auth_session(db_session, token, days=settings.auth_session_days)
            db_session.commit()
            return found
    except SQLAlchemyError as error:
        logger.warning(
            "login could not be resolved",
            extra={"context": {"error_type": type(error).__name__}},
        )
        return None


def require_owner(request: Request) -> AuthSessionRecord:
    """The owner gate. Admits only a valid session cookie; refuses with one
    fixed 401 message otherwise, resolving the owner from the cookie alone.
    A member is admitted only to its own rows and to reading shared data."""
    login = current_login(request)
    if login is None:
        raise _refused()
    if not login.is_owner:
        _hold_member(request, login.user_id)
    return login


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def _hold_member(request: Request, member_id: UUID) -> None:
    if request.method not in _READS and request.url.path.startswith(_SHARED_PREFIXES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=SHARED_READ_ONLY)
    params = request.path_params
    with Session(request.app.state.engine) as db_session, account_scope.scoped(member_id):
        owned = True
        if "package_id" in params:
            owned = db_session.get(Piece, params["package_id"]) is not None
        if owned and "thread_id" in params:
            thread_id = _uuid(str(params["thread_id"]))
            owned = thread_id is not None and db_session.get(Thread, thread_id) is not None
        if owned and "upload_id" in params:
            upload_id = _uuid(str(params["upload_id"]))
            owned = upload_id is not None and db_session.execute(
                select(Upload.id).join(Thread, Thread.id == Upload.thread_id).where(Upload.id == upload_id)
            ).first() is not None
        if owned and "pricing_id" in params:
            pricing_id = _uuid(str(params["pricing_id"]))
            owned = pricing_id is not None and db_session.execute(
                select(CutListPricing.id)
                .join(Piece, Piece.package_id == CutListPricing.package_id)
                .where(CutListPricing.id == pricing_id)
            ).first() is not None
    if not owned:
        raise _not_found()


class AccountScope:
    """ASGI middleware: every request runs in the signed-in account's house file
    (the owner's when signed out or signed in as the owner)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        login = await run_in_threadpool(current_login, Request(scope))
        member = None if login is None else account_scope.scope_for(login.user_id, is_owner=login.is_owner)
        with account_scope.scoped(member):
            await self.app(scope, receive, send)


def require_dev(request: Request) -> AuthSessionRecord:
    """The developer gate. Needs the panel enabled (else 404), a valid session
    (else 401) and the owner account (a member gets 404)."""
    if not request.app.state.settings.dev_panel_enabled:
        # 404 rather than 403 keeps the route's existence private.
        raise _not_found()
    login = require_owner(request)
    if not login.is_owner:
        raise _not_found()
    return login
