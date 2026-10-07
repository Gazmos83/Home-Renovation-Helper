"""Evidence for a render review, assembled by code (render-reviewer).

`collect` chooses the screenshot, the front, side and top views when the build
made them, an even spread of turntable frames or the still, and a room still or
two room frames. Spec facts are numbers from the
stored document. A version with nothing to look at is refused.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.blender import storage
from app.blender.custom_build import derive as custom_derive

logger = logging.getLogger("app")

ASPECTS = Literal["brief", "proportion", "material", "placement", "construction", "render"]
SOURCES = Literal["brief", "spec", "rule"]
SEVERITIES = Literal["minor", "major"]

MAX_IMAGES = 10
# The build's straight-on views and the dimension lines each shows (piece-inspector).
VIEWS = (
    ("front.png", "front view (width and height)"),
    ("side.png", "side view (depth and height)"),
    ("top.png", "top view (width and depth)"),
)
MAX_ITEMS = 20


class ReviewRefused(ValueError):
    """The version has nothing a review can look at."""


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aspect: ASPECTS
    expected: str = Field(min_length=1, max_length=500)
    expected_source: SOURCES
    rule_id: str | None = Field(default=None, max_length=64)
    observed: str = Field(min_length=1, max_length=500)
    image: int = Field(ge=1)
    severity: SEVERITIES
    suggestion: str | None = Field(default=None, max_length=500)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Item] = Field(max_length=MAX_ITEMS)


def review_schema(image_count: int) -> type[Review]:
    """A Review whose items must cite an image that was actually sent."""

    class BoundItem(Item):
        image: int = Field(ge=1, le=max(image_count, 1))

    class BoundReview(Review):
        items: list[BoundItem] = Field(max_length=MAX_ITEMS)  # type: ignore[assignment]

    return BoundReview


@dataclass(frozen=True)
class EvidenceImage:
    label: str
    path: Path
    relative: str


@dataclass
class Evidence:
    images: list[EvidenceImage] = field(default_factory=list)
    facts: str = ""
    brief: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    renders: list[str] = field(default_factory=list)


def _png(folder: Path, relative: str) -> Path | None:
    path = folder / relative
    return path if path.is_file() else None


def _frame_count(frames_dir: Path) -> int:
    if not frames_dir.is_dir():
        return 0
    count = 0
    while (frames_dir / f"frame_{count:03d}.png").is_file():
        count += 1
    return count


def _spread(n: int) -> list[int]:
    if n <= 0:
        return []
    if n <= 4:
        return list(range(n))
    return [round(k * n / 4) % n for k in range(4)]


def _spec_facts(document: dict[str, Any]) -> str:
    overall = custom_derive.overall(document)
    lines = [
        f"Overall: {overall['w']} × {overall['h']} × {overall['d']} mm (w × h × d).",
    ]
    try:
        parts, hardware, _assembly = custom_derive.derive(document)
        lines.append(f"Cut-list rows: {len(parts)}; hardware lines: {len(hardware)}.")
    except (KeyError, TypeError, ValueError):
        logger.debug("review facts: cut list not derived", exc_info=True)
    materials = document.get("materials") or {}
    if materials:
        named = ", ".join(
            f"{slot}: {(entry or {}).get('material') or slot}" for slot, entry in materials.items()
        )
        lines.append(f"Materials: {named}.")
    fronts: dict[str, int] = {}
    for module in document.get("modules") or []:
        size = f"{module.get('width')} × {module.get('height')} × {module.get('depth')} mm"
        shelves = module.get("shelves")
        shelf_bit = f", {shelves} shelf/shelves" if shelves else ""
        lines.append(f"Module {module.get('id')}: {size}{shelf_bit}.")
        for front in module.get("fronts") or []:
            kind = front.get("type") or "front"
            fronts[kind] = fronts.get(kind, 0) + 1
    if fronts:
        lines.append(
            "Fronts: " + ", ".join(f"{count} {kind}" for kind, count in sorted(fronts.items())) + "."
        )
    return "\n".join(lines)


def _document(folder: Path) -> dict[str, Any] | None:
    for name in ("spec.json", storage.INPUT_FILE):
        path = folder / name
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return None


def _design_warnings(document: dict[str, Any] | None) -> list[str]:
    if not document:
        return []
    try:
        from app.guidelines.checks import warnings_for  # type: ignore[import-not-found]
    except ImportError:
        return []
    try:
        return list(warnings_for(document))
    except Exception:  # noqa: BLE001 - missing rules must not fail a review
        return []


def collect(root: Path, package_id: str, version: int) -> Evidence:
    """The labelled images, spec facts and brief-side text for one version."""
    folder = storage.version_dir(root, package_id, version)
    if not folder.is_dir():
        raise ReviewRefused(
            f"package {package_id!r} has no version {version}, so it cannot be reviewed; "
            "build or render it first"
        )
    evidence = Evidence()
    screenshot = _png(folder, "screenshot.png")
    if screenshot is not None:
        evidence.images.append(
            EvidenceImage("screenshot", screenshot, "screenshot.png")
        )
    for name, label in VIEWS:
        view = _png(folder, name)
        if view is not None:
            evidence.images.append(EvidenceImage(label, view, name))

    frames_dir = folder / "frames"
    n = _frame_count(frames_dir)
    still = _png(folder, "still.png")
    if n:
        for index in _spread(n):
            relative = f"frames/frame_{index:03d}.png"
            path = folder / relative
            if path.is_file() and len(evidence.images) < MAX_IMAGES:
                evidence.images.append(
                    EvidenceImage(f"turntable frame {index} of {n}", path, relative)
                )
    elif still is not None and len(evidence.images) < MAX_IMAGES:
        evidence.images.append(EvidenceImage("still", still, "still.png"))

    room_still = _png(folder, "room/still.png")
    room_n = _frame_count(folder / "room" / "frames")
    if room_still is not None and len(evidence.images) < MAX_IMAGES:
        evidence.images.append(EvidenceImage("room still", room_still, "room/still.png"))
    elif room_n and len(evidence.images) < MAX_IMAGES:
        first = 0
        opposite = (room_n // 2) % room_n
        for index in (first, opposite):
            relative = f"room/frames/frame_{index:03d}.png"
            path = folder / relative
            if path.is_file() and len(evidence.images) < MAX_IMAGES:
                evidence.images.append(
                    EvidenceImage(f"room frame {index} of {room_n}", path, relative)
                )

    if not evidence.images:
        raise ReviewRefused(
            f"{package_id} version {version} has no screenshot or render, so it cannot be "
            "reviewed; build or render it first"
        )

    evidence.renders = [image.relative for image in evidence.images]
    document = _document(folder)
    if document:
        try:
            evidence.facts = _spec_facts(document)
        except Exception:  # noqa: BLE001 - a bad document still lets the images through
            evidence.facts = ""
        evidence.warnings = _design_warnings(document)
    return evidence
