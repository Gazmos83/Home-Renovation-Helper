"""The import template for another AI chat (design-import). Owner-gated."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.gate import require_owner
from app.design_import import load_template

router = APIRouter(prefix="/design-import", tags=["design-import"], dependencies=[Depends(require_owner)])


@router.get("/template")
def download_template() -> JSONResponse:
    """The shipped template with its guide, as a file to give another chat."""
    return JSONResponse(
        load_template(),
        headers={"Content-Disposition": 'attachment; filename="import-template.json"'},
    )
