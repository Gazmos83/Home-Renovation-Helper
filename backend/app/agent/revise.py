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


DEFAULT_HINGE = "hinge-concealed-110"


def _without_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_without_none(item) for item in value]
    return value


def _same(before: Any, after: Any) -> bool:
    """Whether a requested value equals the stored one; the request carries no `None` fields."""
    return _without_none(before) == _without_none(after)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def describe_front(front: dict[str, Any]) -> str:
    """One front in words: type, count, height when set, and its opening."""
    kind = front.get("type")
    height = f" {front['height']} mm" if front.get("height") else ""
    if kind == "flap":
        return f"1 flap{height} ({front.get('hinged')}-hinged)"
    if kind == "door":
        details = [str(front.get("opening"))]
        hinge = front.get("hinge", DEFAULT_HINGE)
        if front.get("opening") == "hinge" and hinge != DEFAULT_HINGE:
            details.append(hinge)
        return f"{_plural(front.get('count', 1), 'door')}{height} ({', '.join(details)})"
    return f"{_plural(front.get('count', 1), str(kind))}{height}"


def describe_fronts(fronts: list[dict[str, Any]] | None) -> str:
    """A module's fronts as written, in words, e.g. "1 door (hinge), 1 drawer 200 mm"."""
    return ", ".join(describe_front(front) for front in fronts or []) or "none"


def describe_hardware(lines: list[dict[str, Any]] | None) -> str:
    """A module's hardware lines by id, item and quantity, e.g. 'handle "Bar handle" ×2'."""
    return ", ".join(f'{line["id"]} "{line["item"]}" ×{line["qty"]}' for line in lines or []) or "none"


def _unknown(kind: str, slug: str, present: set[str]) -> ReviseError:
    listed = ", ".join(sorted(present)) or "none"
    return ReviseError(f"{kind} {slug!r} is not in the package; its {kind}s are: {listed}")


def _apply_module_change(module: dict[str, Any], change: dict[str, Any], lines: list[str]) -> None:
    module_id = module["id"]
    for field, value in change.items():
        if field == "hinge":
            _set_hinge(module, value, lines)
            continue
        before = module.get(field)
        if _same(before, value):
            continue  # a value the module already has changes nothing
        if field == "fronts":
            lines.append(f"{module_id}: fronts {describe_fronts(before)} → {describe_fronts(value)}")
        elif field == "hardware":
            lines.append(f"{module_id}: hardware {describe_hardware(before)} → {describe_hardware(value)}")
        else:
            lines.append(f"{module_id}: {field} {before} → {value}")
        module[field] = value


def _set_hinge(module: dict[str, Any], hinge: str, lines: list[str]) -> None:
    doors = [front for front in module.get("fronts") or [] if front.get("type") == "door" and front.get("opening") == "hinge"]
    if not doors:
        raise ReviseError(f"module {module['id']!r} has no hinged door to take hinge {hinge!r}")
    for door in doors:
        if door.get("hinge", DEFAULT_HINGE) == hinge:
            continue
        lines.append(f"{module['id']}: hinge {door.get('hinge', DEFAULT_HINGE)} → {hinge}")
        door["hinge"] = hinge


def _apply_shelf_change(shelf: dict[str, Any], change: dict[str, Any], lines: list[str]) -> None:
    for field, value in change.items():
        before = shelf.get(field)
        if _same(before, value) or (field == "bracket_positions_mm" and not before and not value):
            continue  # a value the shelf already has changes nothing
        if field == "bracket_positions_mm":
            was = before if before else "calculated"
            now = value if value else "calculated"
            lines.append(f"{shelf['id']}: bracket positions {was} → {now}")
            if value:
                shelf[field] = value
            else:
                shelf.pop(field, None)
            continue
        lines.append(f"{shelf['id']}: {field} {before} → {value}")
        shelf[field] = value


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

    shelves: list[dict[str, Any]] = list(spec.get("wall_shelves") or [])
    known_shelves = {shelf["id"] for shelf in shelves}
    for slug in requested.get("remove_wall_shelves") or []:
        if slug not in known_shelves:
            raise _unknown("wall shelf", slug, known_shelves)
        shelves = [shelf for shelf in shelves if shelf["id"] != slug]
        known_shelves.discard(slug)
        lines.append(f"{slug}: wall shelf removed")
    for slug, change in (requested.get("wall_shelves") or {}).items():
        if slug not in known_shelves:
            raise _unknown("wall shelf", slug, known_shelves)
        _apply_shelf_change(next(shelf for shelf in shelves if shelf["id"] == slug), change, lines)
    for shelf in requested.get("add_wall_shelves") or []:
        shelves.append(shelf)
        known_shelves.add(shelf["id"])
        lines.append(f"{shelf['id']}: wall shelf added ({shelf['length']}×{shelf['depth']} mm)")
    if shelves or "wall_shelves" in spec:
        spec["wall_shelves"] = shelves

    if "name" in requested and not _same(spec.get("name"), requested["name"]):
        lines.append(f"name: {spec.get('name')} → {requested['name']}")
        spec["name"] = requested["name"]
    if "envelope" in requested and not _same(spec.get("envelope"), requested["envelope"]):
        envelope = requested["envelope"]
        lines.append(f"envelope: {envelope['width']}×{envelope['height']}×{envelope['depth']} mm")
        spec["envelope"] = envelope
    materials: dict[str, Any] = dict(spec.get("materials") or {})
    for slot, entry in (requested.get("materials") or {}).items():
        before = materials.get(slot)
        if _same(before, entry):
            continue
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
