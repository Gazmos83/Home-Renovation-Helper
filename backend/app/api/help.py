"""The Studio's help topics (help-center). Owner-gated; the Help page reads them."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.gate import require_owner

router = APIRouter(prefix="/help", tags=["help"], dependencies=[Depends(require_owner)])


@router.get("")
def read_help(request: Request) -> dict[str, Any]:
    """Every help topic in order, as `config/help.yaml` holds them."""
    return request.app.state.help.model_dump(exclude_none=True)
