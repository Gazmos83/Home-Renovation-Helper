"""Developer panel: plugins globally enabled or disabled, and HTTPS invocations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.gate import require_dev
from app.db.models import PluginInvocation
from app.plugins.enablement import global_enabled, set_global_enabled

router = APIRouter(prefix="/admin/plugins", tags=["admin"], dependencies=[Depends(require_dev)])


class PluginEnabledIn(BaseModel):
    enabled: bool


@router.get("")
def list_plugins(request: Request) -> list[dict]:
    plugins = request.app.state.plugins
    with Session(request.app.state.engine) as session:
        return [
            {
                "name": plugin.name,
                "description": plugin.manifest.description,
                "kind": plugin.kind,
                "role": plugin.role,
                "tools": list(plugin.manifest.tools),
                "enabled_by_default": plugin.enabled_by_default,
                "toggleable": plugin.toggleable,
                "enabled": global_enabled(session, plugins, plugin.name),
            }
            for plugin in plugins.by_name.values()
        ]


@router.put("/{name}")
def set_plugin(name: str, body: PluginEnabledIn, request: Request) -> dict:
    plugins = request.app.state.plugins
    if name not in plugins.by_name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    with Session(request.app.state.engine) as session:
        set_global_enabled(session, name, body.enabled)
        session.commit()
        enabled = global_enabled(session, plugins, name)
    return {"name": name, "enabled": enabled}


@router.get("/{name}/invocations")
def list_invocations(name: str, request: Request) -> list[dict]:
    plugins = request.app.state.plugins
    if name not in plugins.by_name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    with Session(request.app.state.engine) as session:
        rows = session.scalars(
            select(PluginInvocation)
            .where(PluginInvocation.plugin == name)
            .order_by(PluginInvocation.created_at.desc())
            .limit(50)
        ).all()
    return [
        {
            "outcome": row.outcome,
            "duration_ms": row.duration_ms,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
