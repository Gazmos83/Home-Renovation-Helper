"""How far a piece has come, read from the house file and the version folder.

One derivation for the Foreman's per-turn facts and for the Studio's project
panel, so the two never disagree. Nothing here names a model, a prompt, a token
count or a host path: images are package routes (CLAUDE.md §1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final
from uuid import UUID

from sqlalchemy.orm import Session

from app.agent import house_file
from app.blender import storage
from app.packages import service

STEPS: Final = ("brief", "piece", "built", "rendered", "reviewed", "detail", "final")

_MODEL_RENDERS: Final = ("still", "turntable", "room-still", "room-turntable")
_DETAIL_RENDERS: Final = ("detail-still", "detail-turntable")


def review_ready(root: Path, package_id: str | None, version: int | None) -> bool:
    """Whether the version has a screenshot or a render the Reviewer can look at."""
    if not package_id or version is None:
        return False
    try:
        folder = storage.version_dir(root, package_id, version)
    except (storage.InvalidPackageId, ValueError):
        return False
    return any(
        (folder / name).is_file()
        for name in ("screenshot.png", "still.png", "room/still.png")
    ) or (folder / "frames" / "frame_000.png").is_file()


def detail_ready(root: Path, package_id: str | None, version: int | None) -> bool:
    """Whether the bound piece's latest version has a successful build to detail."""
    if not package_id or version is None:
        return False
    try:
        folder = storage.version_dir(root, package_id, version)
    except (storage.InvalidPackageId, ValueError):
        return False
    state = storage.read_status(folder) or {}
    return state.get("status") == "succeeded" and (folder / "model.blend").is_file()


def _route(package_id: str, version: int, name: str) -> str:
    return f"/packages/{package_id}/versions/{version}/files/{name}"


def _composition_route(slug: str, version: int, name: str) -> str:
    return f"/compositions/{slug}/versions/{version}/files/{name}"


# The version dropdown lists the newest versions only; older ones are kept (project-room-inspection).
LISTED_COMPOSITION_VERSIONS: Final = 5


def composition_version_views(
    session: Session,
    root: Path,
    slug: str,
    numbers: list[int],
    *,
    approved_at: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """The newest listed versions of a composition, newest first, as the Studio shows them:
    status, picture, viewer, items, and the 3D routes when the version has `model.glb`."""
    when = approved_at or {}
    views = []
    for number in sorted(numbers, reverse=True)[:LISTED_COMPOSITION_VERSIONS]:
        folder = storage.composition_version_dir(root, slug, number)
        picture = next(
            (_composition_route(slug, number, name) for name in ("still.png", "screenshot.png") if (folder / name).is_file()),
            None,
        )
        try:
            document = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            document = {}
        modelled = (folder / "model.glb").is_file()
        views.append(
            {
                "version": number,
                "status": (storage.read_status(folder) or {}).get("status"),
                "picture": picture,
                "viewer": _composition_route(slug, number, "viewer.html") if (folder / "viewer.html").is_file() else None,
                "items": house_file.placed_items(session, document),
                "model": _composition_route(slug, number, "model.glb") if modelled else None,
                "surfaces": _composition_route(slug, number, "report.json") if modelled else None,
                "dimensions": f"/compositions/{slug}/versions/{number}/dimensions" if modelled else None,
                "approved_at": when.get(number),
            }
        )
    return views


def room_progress(session: Session, root: Path, thread_id: UUID) -> dict[str, Any] | None:
    """The conversation's confirmed room or apartment and its composition's 3D view
    (project-room-inspection), or `None` when neither is confirmed. `slug` is set once a
    composition exists; `model` and `surfaces` only when its latest version has `model.glb`."""
    room, apartment = house_file.thread_scope(session, thread_id)
    if room is not None:
        scope, name = "room", room.name
    elif apartment is not None:
        scope, name = "apartment", apartment.name
    else:
        return None
    found: dict[str, Any] = {
        "name": name, "scope": scope, "slug": None, "model": None, "surfaces": None,
        "versions": [], "approved_version": None,
    }
    composition = house_file.composition_by_scope(session, scope, name)
    if composition is None:
        return found
    found["slug"] = composition.slug
    rows = house_file.composition_version_rows(session, composition)
    numbers = [v.version for v in rows]
    approved_at = {v.version: v.approved_at.isoformat() for v in rows if v.approved_at is not None}
    found["approved_version"] = next((v.version for v in rows if v.approved_at is not None), None)
    found["versions"] = composition_version_views(
        session, root, composition.slug, numbers, approved_at=approved_at
    )
    if found["versions"]:
        found["model"] = found["versions"][0]["model"]
        found["surfaces"] = found["versions"][0]["surfaces"]
    return found


def _step(step: str, done: bool, detail: str | None = None) -> dict[str, Any]:
    return {"step": step, "done": done, "detail": detail}


def _next_step(steps: list[dict[str, Any]], build_status: str | None, has_piece: bool) -> str:
    done = {s["step"]: s["done"] for s in steps}
    if not has_piece and not done["brief"]:
        return "Describe the piece you want"
    if not has_piece:
        return "Ask for the piece to be designed"
    if not done["built"]:
        if build_status == "failed":
            return "The last build failed; ask for the piece to be revised"
        return "Wait for the build to finish"
    if not done["rendered"]:
        return "Ask for a draft render"
    if not done["reviewed"]:
        return "Ask for a review of the piece"
    if not done["detail"]:
        return "Ask for the photoreal detail pass"
    if not done["final"]:
        return "Ask for a final render"
    return "Every step is done; ask for a change any time"


def piece_progress(
    session: Session, root: Path, package_id: str | None, *, brief_confirmed: bool
) -> dict[str, Any]:
    """The progress of `package_id` (or of a thread with none) as plain data."""
    piece = None
    if package_id:
        piece = next(
            (p for p in house_file.pieces(session, root) if p["package_id"] == package_id), None
        )
    latest = piece["latest_version"] if piece else None
    has_piece = latest is not None

    build_status: str | None = piece["status"] if piece else None
    jobs: dict[str, Any] = {}
    folder: Path | None = None
    if has_piece and package_id:
        folder = storage.version_dir(root, package_id, latest)
        state = storage.read_status(folder) or {}
        build_status = state.get("status")
        jobs = state.get("renders") or {}

    built = build_status == "succeeded"
    rendering = any(j.get("status") in ("queued", "running") for j in jobs.values())
    done_model = {k: j for k, j in jobs.items() if k in _MODEL_RENDERS and j.get("status") == "succeeded"}
    rendered = bool(done_model) or bool(
        folder
        and ((folder / "still.png").is_file() or (folder / "frames" / "frame_000.png").is_file())
    )
    tiers = sorted({str(j["tier"]) for j in done_model.values() if j.get("tier")})

    reviews = house_file.reviews_for(session, package_id, latest) if has_piece and package_id else []
    open_items = (
        sum(1 for item in house_file.items_of(session, reviews[0].id) if item.status == "open")
        if reviews
        else 0
    )
    detailed = any((jobs.get(k) or {}).get("status") == "succeeded" for k in _DETAIL_RENDERS) or bool(
        folder and (storage.detail_dir(folder) / "still.png").is_file()
    )
    # The detail pass renders at `final` too, but it is its own step.
    final = any(j.get("tier") == "final" for j in done_model.values())

    steps = [
        _step("brief", brief_confirmed or bool(piece and piece["has_brief"])),
        _step("piece", has_piece, f"version {latest}" if has_piece else None),
        _step("built", built, build_status if has_piece else None),
        _step("rendered", rendered, ", ".join(tiers) or None),
        _step("reviewed", bool(reviews), f"{open_items} open" if reviews else None),
        _step("detail", detailed),
        _step("final", final),
    ]

    requests = [
        {"field": r.field, "request": r.request}
        for r in house_file.open_extension_requests(session)
        if package_id and r.package_id == package_id
    ]

    return {
        "package_id": package_id if piece else None,
        "name": piece["name"] if piece else None,
        "latest_version": latest,
        "approved_version": piece["approved_version"] if piece else None,
        # How many versions the piece holds, and the most it can (version-cleanup-and-inspection).
        "version_count": len(storage.versions(root, package_id)) if has_piece and package_id else 0,
        "max_versions": service.MAX_VERSIONS,
        "build_status": build_status if has_piece else None,
        "rendering": rendering,
        "steps": steps,
        "next_step": _next_step(steps, build_status, has_piece),
        "open_review_items": open_items,
        "open_requests": requests,
        "screenshot": _route(package_id, latest, "screenshot.png")
        if folder and package_id and (folder / "screenshot.png").is_file()
        else None,
        "still": _route(package_id, latest, "still.png")
        if folder and package_id and (folder / "still.png").is_file()
        else None,
        # Published means the viewer and its first frame are both there (as `describe_renders`).
        "viewer": _route(package_id, latest, "viewer.html")
        if folder
        and package_id
        and (folder / "viewer.html").is_file()
        and (folder / "frames" / "frame_000.png").is_file()
        else None,
    }
