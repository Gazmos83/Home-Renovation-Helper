"""Per-thread plugin toggles (homeowner-chat). Owner-gated.

A change applies from the thread's next turn. Non-toggleable and globally
disabled plugins cannot be switched. The body never carries a model or token.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent import house_file
from app.api.gate import require_owner
from app.auth.sessions import AuthSessionRecord
from app.plugins.enablement import (
    EnablementRefused,
    list_thread_toggles,
    set_thread_enabled,
)
from app.plugins.loader import Plugins

router = APIRouter(prefix="/chat/threads", tags=["chat"], dependencies=[Depends(require_owner)])


class ToolToggleIn(BaseModel):
    enabled: bool


class ToolToggleOut(BaseModel):
    plugin: str
    description: str
    enabled: bool
    toggleable: bool


def _plugins(request: Request) -> Plugins:
    return request.app.state.plugins


def _load_thread(request: Request, thread_id: UUID):
    with Session(request.app.state.engine) as session:
        thread = house_file.get_thread(session, thread_id)
        if thread is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        session.expunge(thread)
        return thread


@router.get("/{thread_id}/tools")
def list_tools(
    thread_id: UUID,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> list[ToolToggleOut]:
    _load_thread(request, thread_id)
    with Session(request.app.state.engine) as session:
        rows = list_thread_toggles(session, _plugins(request), thread_id)
    return [
        ToolToggleOut(
            plugin=row.plugin,
            description=row.description,
            enabled=row.enabled,
            toggleable=row.toggleable,
        )
        for row in rows
        if row.globally_enabled
    ]


@router.put("/{thread_id}/tools/{plugin}")
def set_tool(
    thread_id: UUID,
    plugin: str,
    body: ToolToggleIn,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> ToolToggleOut:
    _load_thread(request, thread_id)
    plugins = _plugins(request)
    with Session(request.app.state.engine) as session:
        try:
            set_thread_enabled(session, plugins, thread_id, plugin, body.enabled)
        except EnablementRefused as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"failure_class": error.code, "reason": error.reason, "plugin": error.plugin},
            ) from None
        session.commit()
        rows = {row.plugin: row for row in list_thread_toggles(session, plugins, thread_id)}
    row = rows[plugin]
    return ToolToggleOut(
        plugin=row.plugin,
        description=row.description,
        enabled=row.enabled,
        toggleable=row.toggleable,
    )
