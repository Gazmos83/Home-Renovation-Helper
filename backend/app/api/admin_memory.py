"""Developer panel: memory settings — compression, what is saved, what a conversation sees
(conversation-memory-settings)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from app.agent.memory_settings import (
    DEFAULTS,
    FIXED_RULES,
    MemorySettings,
    read_memory_settings,
    reset_memory_setting,
    write_memory_settings,
)
from app.api.gate import require_dev

router = APIRouter(prefix="/admin/memory", tags=["admin"], dependencies=[Depends(require_dev)])


def _out(settings: MemorySettings) -> dict[str, Any]:
    return {"settings": settings.model_dump(), "defaults": DEFAULTS.model_dump(), "fixed_rules": list(FIXED_RULES)}


@router.get("")
def read_settings(request: Request) -> dict[str, Any]:
    return _out(read_memory_settings(request.app.state.engine))


@router.put("")
def write_settings(body: dict[str, Any], request: Request) -> dict[str, Any]:
    unknown = sorted(set(body) - set(MemorySettings.model_fields))
    if unknown:
        raise HTTPException(
            422, detail={"failure_class": "invalid_setting", "field": unknown[0], "reason": "unknown setting"}
        )
    try:
        return _out(write_memory_settings(request.app.state.engine, body))
    except ValidationError as error:
        first = error.errors()[0]
        field = str(first["loc"][0]) if first.get("loc") else "settings"
        raise HTTPException(
            422, detail={"failure_class": "invalid_setting", "field": field, "reason": first["msg"]}
        ) from None


@router.delete("/{field}")
def reset_setting(field: str, request: Request) -> dict[str, Any]:
    try:
        return _out(reset_memory_setting(request.app.state.engine, field))
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found") from None
