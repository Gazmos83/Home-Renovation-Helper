"""Where variants live: `variants/<variant-id>/` inside a version folder (restyle-variants).

Files only, no table. A variant holds `still.png` and `scene.json`; a version holds at
most `MAX_VARIANTS` and a further one replaces the oldest. Nothing here touches the
version's own `still.png`, `frames/`, `viewer.html`, `spec.json` or `model.blend`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

VARIANTS_DIRNAME: Final = "variants"
MAX_VARIANTS: Final = 12
VARIANT_ID_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_BASE_LENGTH: Final = 40


def variants_dir(version_folder: Path) -> Path:
    return version_folder / VARIANTS_DIRNAME


def variant_dir(version_folder: Path, variant_id: str) -> Path:
    if not VARIANT_ID_PATTERN.match(variant_id):
        raise ValueError(f"{variant_id!r} is not a variant id")
    return variants_dir(version_folder) / variant_id


def _created(folder: Path) -> str:
    try:
        return str(json.loads((folder / "scene.json").read_text(encoding="utf-8")).get("created_at", ""))
    except (OSError, ValueError):
        return ""


def list_variants(version_folder: Path) -> list[dict[str, Any]]:
    """Each published variant, oldest first, from its `scene.json`."""
    root = variants_dir(version_folder)
    if not root.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for folder in root.iterdir():
        if folder.name.startswith(".") or not (folder / "still.png").is_file():
            continue
        try:
            record = json.loads((folder / "scene.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        found.append({"id": folder.name, "created_at": record.get("created_at", ""), **record})
    return sorted(found, key=lambda item: (item["created_at"], item["id"]))


def allocate_ids(version_folder: Path, base_ids: list[str], tier: str) -> list[str]:
    """One unused id per base id: `<base>-<tier>`, then `-2`, `-3` when it is taken.

    Built from preset ids and the tier only, never from text a model wrote.
    """
    taken = {item["id"] for item in list_variants(version_folder)}
    allocated: list[str] = []
    for base in base_ids:
        stem = re.sub(r"[^a-z0-9-]", "-", f"{base[:_BASE_LENGTH]}-{tier}".lower()).strip("-")
        candidate, counter = stem, 1
        while candidate in taken:
            counter += 1
            candidate = f"{stem}-{counter}"
        taken.add(candidate)
        allocated.append(candidate)
    return allocated


def make_room(version_folder: Path, incoming: int = 1) -> list[str]:
    """Remove the oldest variants so `incoming` more fit under the cap. Returns the ids removed."""
    existing = list_variants(version_folder)
    excess = len(existing) + incoming - MAX_VARIANTS
    removed: list[str] = []
    for item in existing[: max(0, excess)]:
        shutil.rmtree(variants_dir(version_folder) / item["id"], ignore_errors=True)
        removed.append(item["id"])
    return removed


def stage_path(version_folder: Path, variant_id: str) -> Path:
    return variants_dir(version_folder) / f".{variant_id}.staging"


def publish(version_folder: Path, variant_id: str, stage: Path, record: dict[str, Any]) -> Path:
    """Publish a verified staging folder as `variants/<id>/` in one rename, with its record."""
    produced: dict[str, Any] = {}
    try:
        produced = json.loads((stage / "scene.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    document = {**produced, **record, "created_at": datetime.now(UTC).isoformat()}
    (stage / "scene.json").write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    target = variant_dir(version_folder, variant_id)
    if target.exists():
        shutil.rmtree(target)
    os.replace(stage, target)
    return target


def sweep_stale(version_folder: Path) -> None:
    root = variants_dir(version_folder)
    if root.is_dir():
        for leftover in root.glob(".*.staging"):
            shutil.rmtree(leftover, ignore_errors=True)
        for leftover in root.glob(".*.restyle.json"):
            leftover.unlink(missing_ok=True)
