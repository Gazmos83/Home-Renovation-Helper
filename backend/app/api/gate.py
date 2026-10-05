"""The two gates every later route depends on (owner-auth).

`require_owner` admits a request only with a valid, unexpired, unrevoked session
cookie and resolves the owner from that cookie alone — never from a request
body, header or model output. `require_dev` is stricter: it additionally needs
the developer panel enabled by configuration, and answers 404 when it is not, so
the homeowner surface shows no sign of the `/admin` routes.

Never add a third gate or duplicate the logic: these two are what every gated
route depends on by name.
"""

from __future__ import annotations

import logging
from typing import Final

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.session import COOKIE_NAME
from app.auth.sessions import AuthSessionRecord, find_auth_session

logger = logging.getLogger("app")

# What the caller is told. Deliberately fixed, so a refusal maps out nothing.
REFUSAL: Final = "sign-in is required"


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
    fixed 401 message otherwise, resolving the owner from the cookie alone."""
    login = current_login(request)
    if login is None:
        raise _refused()
    return login


def require_dev(request: Request) -> AuthSessionRecord:
    """The developer gate. Needs the panel enabled (else 404) and a valid owner
    session (else 401)."""
    if not request.app.state.settings.dev_panel_enabled:
        # 404 rather than 403 keeps the route's existence private.
        raise _not_found()
    return require_owner(request)
