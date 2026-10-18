"""Owner-only recommended reading for an approved version, and local reading of its sources.

Nothing here calls a model or reaches graph state; the routes serve the owner's browser.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.tools.shared import read_input
from app.api.gate import require_owner
from app.api.packages import existing_version, refused
from app.engineering.reading import (
    ReadingRefused,
    read_blocks,
    reading_list,
    report_cited_versions,
)

router = APIRouter(prefix="/packages", tags=["reading"], dependencies=[Depends(require_owner)])


def _approved_spec(request: Request, session: Session, package_id: str, version: int) -> dict:
    folder = existing_version(request, package_id, version)
    row = house_file.version_row(session, package_id, version)
    if row is None or row.approved_at is None:
        raise refused(409, "not_approved", f"version {version} must be approved first to see recommended reading")
    document = read_input(folder)
    if document is None:
        raise refused(409, "no_spec", f"version {version} has no readable spec")
    return document


@router.get("/{package_id}/versions/{version}/reading")
def reading(package_id: str, version: int, request: Request):
    with Session(request.app.state.engine) as session:
        spec = _approved_spec(request, session, package_id, version)
        result = reading_list(session, spec, request.app.state.reading_rules)
    if not result["items"]:
        result["message"] = "This version has no wall-hung items"
    return result


@router.get("/{package_id}/versions/{version}/reading/sources/{version_id}/blocks")
def blocks(package_id: str, version: int, version_id: UUID, request: Request, page: int = Query(1, ge=1)):
    with Session(request.app.state.engine) as session:
        folder = existing_version(request, package_id, version)
        allowed = report_cited_versions(session, package_id, version)
        row = house_file.version_row(session, package_id, version)
        document = read_input(folder)
        if row is not None and row.approved_at is not None and document is not None:
            listed = reading_list(session, document, request.app.state.reading_rules)
            allowed |= {UUID(entry["version_id"]) for entry in listed["entries"]}
        try:
            return read_blocks(session, version_id, allowed, page)
        except ReadingRefused as error:
            raise refused(403, "not_readable_here", str(error)) from None
