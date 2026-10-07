"""Render feedback routes (feedback-capture).

The owner's side lists a version's published renders and rates them. Nothing in
these responses names a model, a prompt or a slot: that origin stays in the
database (`render_runs`) for the developer's summary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Final

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.gate import require_dev, require_owner
from app.api.packages import existing_version, refused, render_root
from app.blender import storage
from app.feedback import ratings
from app.feedback.ratings import FeedbackRefused

router = APIRouter(
    prefix="/packages/{package_id}/versions/{version}/renders",
    tags=["feedback"],
    dependencies=[Depends(require_owner)],
)
admin_router = APIRouter(
    prefix="/admin/feedback", tags=["admin"], dependencies=[Depends(require_dev)]
)

# render key → (kind, folder inside the version, first-frame / still file, viewer)
_LAYOUT: Final[dict[str, tuple[str, str]]] = {
    "still": ("", "still"),
    "turntable": ("", "turntable"),
    "room-still": ("room", "still"),
    "room-turntable": ("room", "turntable"),
    "detail-still": ("detail", "still"),
    "detail-turntable": ("detail", "turntable"),
}
_LABELS: Final[dict[str, str]] = {
    "still": "Still",
    "turntable": "Turntable",
    "room-still": "Still in the room",
    "room-turntable": "Turntable in the room",
    "detail-still": "Detailed still",
    "detail-turntable": "Detailed turntable",
}


def _published(folder: Path, key: str) -> tuple[str | None, str | None]:
    """`(preview, viewer)` file routes of a published render, or `(None, None)`."""
    sub, kind = _LAYOUT[key]
    base = folder / sub if sub else folder
    prefix = f"{sub}/" if sub else ""
    if kind == "still":
        return (f"{prefix}still.png", None) if (base / "still.png").is_file() else (None, None)
    if (base / "frames" / "frame_000.png").is_file() and (base / "viewer.html").is_file():
        return f"{prefix}frames/0", f"{prefix}viewer.html"
    return None, None


def describe_renders(
    root: Path, session: Session, package_id: str, version: int
) -> list[dict[str, Any]]:
    folder = storage.version_dir(root, package_id, version)
    jobs = (storage.read_status(folder) or {}).get("renders") or {}
    items: list[dict[str, Any]] = []
    for key in storage.RENDER_KEYS:
        preview, viewer = _published(folder, key)
        if preview is None:
            continue
        found = ratings.current(session, package_id, version, key)
        rated = found[1] if found else None
        base = f"/packages/{package_id}/versions/{version}/files/"
        items.append(
            {
                "render": key,
                "label": _LABELS[key],
                "tier": (jobs.get(key) or {}).get("tier"),
                "preview": base + preview,
                "viewer": base + viewer if viewer else None,
                # A render made before ratings existed has no run to rate.
                "can_rate": found is not None,
                "rating": rated.rating if rated else None,
                "comment": rated.comment if rated else None,
            }
        )
    return items


def _item(request: Request, package_id: str, version: int, key: str) -> dict[str, Any]:
    with Session(request.app.state.engine) as session:
        for item in describe_renders(render_root(request), session, package_id, version):
            if item["render"] == key:
                return item
    raise HTTPException(404, detail="Not Found")


def _refusal(error: FeedbackRefused) -> HTTPException:
    return refused(error.status, error.failure_class, error.reason)


@router.get("")
def list_renders(package_id: str, version: int, request: Request) -> list[dict[str, Any]]:
    existing_version(request, package_id, version)
    with Session(request.app.state.engine) as session:
        return describe_renders(render_root(request), session, package_id, version)


@router.put("/{render}/feedback")
def rate_render(
    package_id: str,
    version: int,
    render: str,
    request: Request,
    body: Annotated[dict[str, Any], Body()],
) -> dict[str, Any]:
    existing_version(request, package_id, version)
    unknown = sorted(set(body) - {"rating", "comment"})
    if unknown:
        raise refused(422, "refused", f"unknown field {unknown[0]!r}; a rating takes rating and comment")
    try:
        with Session(request.app.state.engine) as session:
            rated = ratings.rate(
                session,
                package_id=package_id,
                version=version,
                render_key=render,
                rating=body.get("rating"),
                comment=body.get("comment"),
            )
    except FeedbackRefused as error:
        raise _refusal(error) from None
    tracing = getattr(request.app.state, "tracing", None)
    if tracing is not None:
        tracing.record_feedback(
            rating=rated.rating, comment=rated.comment, tier=rated.tier, trace_id=rated.trace_id,
            slot=rated.slot, model=rated.model, package_id=package_id, version=version,
            render_key=render,
        )
    return _item(request, package_id, version, render)


@router.delete("/{render}/feedback")
def clear_rating(package_id: str, version: int, render: str, request: Request) -> dict[str, Any]:
    existing_version(request, package_id, version)
    try:
        with Session(request.app.state.engine) as session:
            ratings.clear(session, package_id=package_id, version=version, render_key=render)
    except FeedbackRefused as error:
        raise _refusal(error) from None
    return _item(request, package_id, version, render)


@admin_router.get("")
def feedback_summary(request: Request, days: int = Query(default=30, ge=1, le=365)) -> list[dict]:
    with Session(request.app.state.engine) as session:
        return ratings.summary(session, days=days)


@admin_router.get("/comments")
def feedback_comments(
    request: Request,
    tier: str,
    slot: str = "",
    model: str = "",
) -> list[dict]:
    """An empty `slot` or `model` selects the renders no agent started."""
    with Session(request.app.state.engine) as session:
        return ratings.comments(session, slot=slot or None, model=model or None, tier=tier)
