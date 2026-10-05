"""Applying stated changes to a stored custom-build document (`revise_package`).

Ported from the predecessor's `revise_spec`, reduced to the pure part: it takes
a document and the changes and returns a revised copy with readable change
lines. It stores nothing and does not validate the result — the caller runs
`CustomBuildSpec` on it exactly as it would on any document, so an overlap or a
bad thickness is refused the same way whatever produced it.
"""

from __future__ import annotations

import json
from typing import Any

from app.blender.schemas import PackageChanges


class ReviseError(ValueError):
    """A change names a module or part the document does not contain."""


def _unknown(kind: str, slug: str, present: set[str]) -> ReviseError:
    listed = ", ".join(sorted(present)) or "none"
    return ReviseError(f"{kind} {slug!r} is not in the package; its {kind}s are: {listed}")


def _apply_module_change(module: dict[str, Any], change: dict[str, Any], lines: list[str]) -> None:
    module_id = module["id"]
    for field, value in change.items():
        before = module.get(field)
        if field in ("fronts", "hardware"):
            lines.append(f"{module_id}: {field} {len(before or [])} → {len(value)} entries")
        else:
            lines.append(f"{module_id}: {field} {before} → {value}")
        module[field] = value


def revise_spec(
    document: dict[str, Any], changes: PackageChanges
) -> tuple[dict[str, Any], list[str]]:
    """A copy of `document` with `changes` applied, and the change lines."""
    spec: dict[str, Any] = json.loads(json.dumps(document))
    lines: list[str] = []
    requested = changes.model_dump(mode="json", exclude_none=True)

    modules: list[dict[str, Any]] = list(spec.get("modules") or [])
    known = {module["id"] for module in modules}

    for slug in requested.get("remove_modules") or []:
        if slug not in known:
            raise _unknown("module", slug, known)
        modules = [module for module in modules if module["id"] != slug]
        known.discard(slug)
        lines.append(f"{slug}: module removed")
    for slug, change in (requested.get("modules") or {}).items():
        if slug not in known:
            raise _unknown("module", slug, known)
        module = next(module for module in modules if module["id"] == slug)
        _apply_module_change(module, change, lines)
    for module in requested.get("add_modules") or []:
        modules.append(module)
        lines.append(f"{module['id']}: module added ({module['width']}×{module['height']}×{module['depth']} mm)")
    spec["modules"] = modules

    parts: list[dict[str, Any]] = list(spec.get("extra_parts") or [])
    known_parts = {part["id"] for part in parts}
    for slug in requested.get("remove_extra_parts") or []:
        if slug not in known_parts:
            raise _unknown("extra part", slug, known_parts)
        parts = [part for part in parts if part["id"] != slug]
        known_parts.discard(slug)
        lines.append(f"{slug}: extra part removed")
    for part in requested.get("add_extra_parts") or []:
        parts.append(part)
        lines.append(f"{part['id']}: extra part added")
    if parts or "extra_parts" in spec:
        spec["extra_parts"] = parts

    if "name" in requested:
        lines.append(f"name: {spec.get('name')} → {requested['name']}")
        spec["name"] = requested["name"]
    if "envelope" in requested:
        envelope = requested["envelope"]
        lines.append(f"envelope: {envelope['width']}×{envelope['height']}×{envelope['depth']} mm")
        spec["envelope"] = envelope
    materials: dict[str, Any] = dict(spec.get("materials") or {})
    for slot, entry in (requested.get("materials") or {}).items():
        before = materials.get(slot)
        was = f"{before['material']} {before['thickness_mm']} mm" if before else "new slot"
        lines.append(f"materials.{slot}: {was} → {entry['material']} {entry['thickness_mm']} mm")
        materials[slot] = entry
    if materials or "materials" in spec:
        spec["materials"] = materials

    overrides: list[dict[str, Any]] = list(spec.get("part_overrides") or [])
    for override in requested.get("part_overrides") or []:
        replaced = any(existing["id"] == override["id"] for existing in overrides)
        overrides = [existing for existing in overrides if existing["id"] != override["id"]] + [override]
        lines.append(f"part_overrides.{override['id']}: {'replaced' if replaced else 'added'}")
    if overrides or "part_overrides" in spec:
        spec["part_overrides"] = overrides

    return spec, lines
