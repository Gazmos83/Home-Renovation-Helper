"""Developer panel: the owner adds and removes member accounts (owner-auth).

A member signs in like the owner and uses the Studio with its own house file,
but never reaches these `/admin` routes: `require_dev` admits only the owner.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.gate import require_dev
from app.api.session import get_db_session
from app.auth.accounts import (
    AccountExists,
    OwnerAccount,
    UserRecord,
    create_member,
    delete_member,
    get_owner,
    list_accounts,
)
from app.auth.passwords import WeakPassword

logger = logging.getLogger("app")

router = APIRouter(prefix="/admin/users", tags=["admin"], dependencies=[Depends(require_dev)])


class MemberIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


def _out(record: UserRecord, owner_id: UUID | None) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "email": record.email,
        "created_at": record.created_at.isoformat(),
        "is_owner": record.id == owner_id,
    }


@router.get("")
def list_users(db_session: Annotated[Session, Depends(get_db_session)]) -> list[dict[str, Any]]:
    owner = get_owner(db_session)
    owner_id = owner.id if owner else None
    return [_out(record, owner_id) for record in list_accounts(db_session)]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_member(body: MemberIn, db_session: Annotated[Session, Depends(get_db_session)]) -> dict[str, Any]:
    try:
        record = create_member(db_session, body.email, body.password)
    except AccountExists as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from None
    except WeakPassword as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    db_session.commit()
    logger.info("member added", extra={"context": {"user_id": str(record.id)}})
    return _out(record, None)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: UUID, db_session: Annotated[Session, Depends(get_db_session)]) -> Response:
    try:
        removed = delete_member(db_session, user_id)
        db_session.commit()
    except OwnerAccount as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from None
    except IntegrityError:
        db_session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="the account still has pieces, rooms or conversations; delete those first",
        ) from None
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    logger.info("member removed", extra={"context": {"user_id": str(user_id)}})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
