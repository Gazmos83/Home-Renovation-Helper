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

from app.blender.custom_build.derive import (
    derive,
    handle_spec,
    module_bounds,
    signed_degrees,
    slat_spec,
)
from app.blender.schemas import CustomBuildSpec, PackageChanges
from app.blender.spec_contract import SpecValidationError


class ReviseError(ValueError):
    """A change names a module or part the document does not contain."""


DEFAULT_HINGE = "hinge-concealed-110"
# The interior fields a change clears with 0 or an empty list (shelf-spacing-and-dividers, carcass-side-folds).
_CLEARED_BY = {
    "shelf_spacing_mm": 0,
    "shelf_positions_mm": [],
    "divider_positions_mm": [],
    "divider_spans": [],
    "shelf_kinds": [],
    "shelf_depths_mm": [],
    "side_folds": [],
}
# Spacing and positions exclude each other: setting one drops the other.
_REPLACES = {"shelf_spacing_mm": "shelf_positions_mm", "shelf_positions_mm": "shelf_spacing_mm"}


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


def describe_handle(front: dict[str, Any]) -> str:
    """A front's handle in words, e.g. "bar 900 mm vertical, meeting edges, black"; "" without one."""
    handle = handle_spec(front) if front.get("handle") else None
    if handle is None:
        return ""
    words = f"bar {handle['length']} mm {handle['orientation']}" if handle["kind"] == "bar" else "knob"
    details = [words]
    if handle["edge"] is not None:
        details.append("meeting edges" if handle["edge"] == "meeting" else f"{handle['edge']} edge")
    details.append(handle["finish"])
    if front["handle"].get("key"):
        details.append(f"key {handle['key']}")
    return ", ".join(details)


def describe_slats(front: dict[str, Any]) -> str:
    """A door's slats in words, e.g. "8 vertical slats 30 mm on door 2"; "" without them (door-slats)."""
    slats = slat_spec(front)
    if slats is None:
        return ""
    words = f"{_plural(slats['count'], slats['orientation'] + ' slat')} {slats['width']} mm"
    if slats["margin_mm"]:
        words += f", {slats['margin_mm']} mm margin"
    stated = front["slats"].get("leaves")
    if stated:
        doors = "door" if len(stated) == 1 else "doors"
        words += ("," if slats["margin_mm"] else "") + f" on {doors} {', '.join(str(leaf) for leaf in stated)}"
    return words


def describe_leaf_materials(front: dict[str, Any], carcass: str | None = None) -> str:
    """The doors cut from their own slot, e.g. "door 2 black_paint"; a door in the carcass
    slot is not named; "" without any (door-leaf-materials)."""
    named = sorted((front.get("leaf_materials") or {}).items(), key=lambda item: int(item[0]))
    return ", ".join(f"door {door} {slot}" for door, slot in named if slot != carcass)


def describe_front(front: dict[str, Any], carcass: str | None = None) -> str:
    """One front in words: type, count, height when set, its opening, its handle, the doors
    with their own material and its slats when set."""
    kind = front.get("type")
    height = f" {front['height']} mm" if front.get("height") else ""
    handle = describe_handle(front)
    if kind == "flap":
        details = [f"{front.get('hinged')}-hinged"] + ([handle] if handle else [])
        return f"1 flap{height} ({', '.join(details)})"
    if kind == "door":
        details = [str(front.get("opening"))]
        hinge = front.get("hinge", DEFAULT_HINGE)
        if front.get("opening") == "hinge" and hinge != DEFAULT_HINGE:
            details.append(hinge)
        if handle:
            details.append(handle)
        materials = describe_leaf_materials(front, carcass)
        if materials:
            details.append(materials)
        slats = describe_slats(front)
        if slats:
            details.append(slats)
        return f"{_plural(front.get('count', 1), 'door')}{height} ({', '.join(details)})"
    return f"{_plural(front.get('count', 1), str(kind))}{height}" + (f" ({handle})" if handle else "")


def describe_fronts(fronts: list[dict[str, Any]] | None, carcass: str | None = None) -> str:
    """A module's fronts as written, in words, e.g. "1 door (hinge), 1 drawer 200 mm"."""
    return ", ".join(describe_front(front, carcass) for front in fronts or []) or "none"


def _layout_words(fronts: list[dict[str, Any]] | None) -> str:
    entries = list(fronts or [])
    if len(entries) == 1:
        only = entries[0]
        kind = str(only.get("type"))
        count = int(only.get("count", 1))
        arranged = " side by side" if count > 1 else ""
        return f"1 entry of {_plural(count, kind)}{arranged}"
    each = "; ".join(_plural(int(front.get("count", 1)), str(front.get("type"))) for front in entries)
    return f"{len(entries)} entries stacked top to bottom ({each})" if entries else "no fronts"


def front_layout_change(module_id: str, before: list[dict[str, Any]] | None, after: list[dict[str, Any]] | None) -> str | None:
    """A line for the revise confirmation when the module's front layout changes: the number
    of entries, or an entry's type or door count, between two layouts that both have fronts;
    materials, handles, slats and heights do not count. Written by code, so a pair turned into stacked entries is never silent
    (door-leaf-materials)."""
    if not before or not after:
        return None  # fronts added or removed: the fronts line already says so
    shape = [(front.get("type"), int(front.get("count", 1))) for front in before]
    if shape == [(front.get("type"), int(front.get("count", 1))) for front in after]:
        return None
    return f"{module_id}: front layout changes from {_layout_words(before)} to {_layout_words(after)}"


def describe_hardware(lines: list[dict[str, Any]] | None) -> str:
    """A module's hardware lines by id, item and quantity, e.g. 'handle "Bar handle" ×2'."""
    return ", ".join(f'{line["id"]} "{line["item"]}" ×{line["qty"]}' for line in lines or []) or "none"


def describe_folds(folds: list[dict[str, Any]] | None) -> str:
    """A module's side folds in words, e.g. 'left from 1100 mm along height, 26°, inside'."""
    if not folds:
        return "none"
    return "; ".join(
        f"{fold['side']} from {fold['from_mm']} mm along {fold['along']}, {fold['angle_deg']}°, {fold['towards']}"
        for fold in folds
    )


def describe_rails(rails: list[dict[str, Any]] | None) -> str:
    """A module's hanging rails in words, e.g. 'bay 1 at 1650 mm, chrome' (hardware-catalog)."""
    if not rails:
        return "none"
    words = []
    for rail in rails:
        text = f"bay {rail.get('bay', 1)} at {rail['z']} mm"
        if rail.get("inset_y_mm") is not None:
            text += f", {rail['inset_y_mm']} mm from the front"
        if rail.get("finish"):
            text += f", {rail['finish']}"
        words.append(text)
    return "; ".join(words)


def describe_spans(spans: list[dict[str, Any]] | None) -> str:
    """A module's divider spans in words, left to right, e.g. 'divider 1 from shelf 4 to the top'."""
    if not spans:
        return "full height"
    words = []
    for number, span in enumerate(spans, start=1):
        low = "the bottom" if span["from_board"] == "bottom" else f"shelf {span['from_board']}"
        high = "the top" if span["to_board"] == "top" else f"shelf {span['to_board']}"
        words.append(f"divider {number} from {low} to {high}")
    return "; ".join(words)


def describe_placements(placements: list[dict[str, Any]] | None) -> str:
    """An extra part's pieces in words, e.g. 'x0 y0 z900, length along x, width along y, tilt 30° towards z'."""
    if not placements:
        return "beside the build"
    words = []
    for placement in placements:
        piece = (
            f"x{placement['x']} y{placement['y']} z{placement['z']}, "
            f"length along {placement['length_along']}, width along {placement['width_along']}"
        )
        if placement.get("roll_deg") is not None:
            piece += f", roll {signed_degrees(placement['roll_deg'])}"
        tilt = placement.get("tilt")
        if tilt is not None:
            piece += f", tilt {signed_degrees(tilt['angle_deg'])} towards {tilt['towards']}"
        words.append(piece)
    return "; ".join(words)


def describe_end_cuts(cuts: dict[str, Any] | None) -> str:
    """An extra part's end cuts in words, e.g. '30° / −30° across width', or 'square'."""
    if not cuts or (cuts["start_deg"] == 0 and cuts["end_deg"] == 0):
        return "square"
    return f"{signed_degrees(cuts['start_deg'])} / {signed_degrees(cuts['end_deg'])} across {cuts['across']}"


def _apply_extra_part_change(part: dict[str, Any], change: dict[str, Any], lines: list[str]) -> None:
    if "placements" in change:
        placements = change["placements"]
        if placements and len(placements) != part["qty"]:
            raise ReviseError(
                f"extra part {part['id']!r} needs {part['qty']} placements, one per piece; "
                f"{len(placements)} were given"
            )
        if not _same(part.get("placements") or [], placements):
            lines.append(
                f"{part['id']}: placements {describe_placements(part.get('placements'))} → {describe_placements(placements)}"
            )
            if placements:
                part["placements"] = placements
            else:
                part.pop("placements", None)
    if "end_cuts" in change:
        before, after = describe_end_cuts(part.get("end_cuts")), describe_end_cuts(change["end_cuts"])
        if before != after:
            lines.append(f"{part['id']}: end cuts {before} → {after}")
            if after == "square":
                part.pop("end_cuts", None)
            else:
                part["end_cuts"] = change["end_cuts"]


def _unknown(kind: str, slug: str, present: set[str]) -> ReviseError:
    listed = ", ".join(sorted(present)) or "none"
    return ReviseError(f"{kind} {slug!r} is not in the package; its {kind}s are: {listed}")


def _apply_module_change(module: dict[str, Any], change: dict[str, Any], lines: list[str]) -> None:
    module_id = module["id"]
    for field, value in change.items():
        if field == "hinge":
            _set_hinge(module, value, lines)
            continue
        if field in _CLEARED_BY:
            _set_interior(module, field, value, change, lines)
            continue
        if field == "mounting":
            _set_mounting(module, value, lines)
            continue
        if field == "dividers" and not value and module.get("divider_positions_mm") and "divider_positions_mm" not in change:
            lines.append(f"{module_id}: divider_positions_mm {module.pop('divider_positions_mm')} → not set")
        if field == "dividers" and not value and module.get("divider_spans") and "divider_spans" not in change:
            lines.append(f"{module_id}: divider_spans {describe_spans(module.pop('divider_spans'))} → full height")
        before = module.get(field)
        if _same(before, value) or (field == "hanging_rails" and not value and not before):
            continue  # a value the module already has changes nothing
        if field == "hanging_rails":
            lines.append(f"{module_id}: hanging_rails {describe_rails(before)} → {describe_rails(value)}")
            if value:
                module[field] = value
            else:
                module.pop(field, None)
            continue
        if field == "fronts":
            carcass = module.get("carcass")
            lines.append(f"{module_id}: fronts {describe_fronts(before, carcass)} → {describe_fronts(value, carcass)}")
            layout = front_layout_change(module_id, before, value)
            if layout:
                lines.append(layout)
        elif field == "hardware":
            lines.append(f"{module_id}: hardware {describe_hardware(before)} → {describe_hardware(value)}")
        else:
            lines.append(f"{module_id}: {field} {before} → {value}")
        module[field] = value


def _set_mounting(module: dict[str, Any], value: str, lines: list[str]) -> None:
    before = module.get("mounting") or "not stated"
    after = "not stated" if value == "unset" else value
    if before == after:
        return  # a value the module already has changes nothing
    lines.append(f"{module['id']}: mounting {before} → {after}")
    if value == "unset":
        module.pop("mounting", None)
    else:
        module["mounting"] = value


def _set_interior(module: dict[str, Any], field: str, value: Any, change: dict[str, Any], lines: list[str]) -> None:
    module_id = module["id"]
    before = module.get(field)
    cleared = value == _CLEARED_BY[field]
    if (cleared and not before) or _same(before, value):
        return  # a value the module already has changes nothing
    if field == "divider_spans":
        now = "full height" if cleared else describe_spans(value)
        lines.append(f"{module_id}: divider_spans {describe_spans(before)} → {now}")
        if cleared:
            module.pop(field, None)
        else:
            module[field] = value
        return
    if field == "side_folds":
        was = describe_folds(before) if before else "not set"
        now = "not set" if cleared else describe_folds(value)
        lines.append(f"{module_id}: side_folds {was} → {now}")
        if cleared:
            module.pop(field, None)
        else:
            module[field] = value
        return
    was = before if before else "not set"
    if cleared:
        lines.append(f"{module_id}: {field} {was} → not set")
        module.pop(field, None)
        if field == "shelf_depths_mm" and module.get("shelf_depth_align") and "shelf_depth_align" not in change:
            lines.append(f"{module_id}: shelf_depth_align {module.pop('shelf_depth_align')} → not set")
        return
    lines.append(f"{module_id}: {field} {was} → {value}")
    module[field] = value
    if field == "shelf_depths_mm" and "shelf_depth_align" not in change and not module.get("shelf_depth_align"):
        module["shelf_depth_align"] = "back"
        lines.append(f"{module_id}: shelf_depth_align not set → back")
    other = _REPLACES.get(field)
    if other is not None and module.get(other) and other not in change:
        lines.append(f"{module_id}: {other} {module.pop(other)} → not set (replaced by {field})")


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


FIT_PREFIX = "fit: "


def _module_front_reach(spec: dict[str, Any], module: dict[str, Any]) -> int:
    """How far the module's solid, shelves included, reaches in front of the build's y = 0 plane."""
    materials = spec.get("materials") or {}
    carcass = materials.get(module.get("carcass"))
    if carcass is None:
        return 0  # an undefined slot is refused by the schema, not here
    back = materials.get(module.get("back")) if module.get("back") is not None else None
    try:
        _x, y0, _z, _w, _d, _h = module_bounds(module, carcass["thickness_mm"], back["thickness_mm"] if back else 0)
    except (ValueError, KeyError, TypeError):
        return 0  # an unreadable module is refused by the schema, not here
    return max(0, -(module.get("y", 0) + y0))


def fit_protruding_shelves(spec: dict[str, Any], lines: list[str]) -> None:
    """Move the build back by the largest overhang past y = 0 and grow the envelope depth by the same.

    Every module and wall shelf rises by the overhang, so the backs stay flush; nothing changes
    when no board reaches in front of the plane (auto-fit-protruding-shelves).
    """
    reaches = {module["id"]: _module_front_reach(spec, module) for module in spec.get("modules") or []}
    shift = max(reaches.values(), default=0)
    if shift <= 0:
        return
    causes = ", ".join(f"{slug} ({reach} mm)" for slug, reach in reaches.items() if reach == shift)
    lines.append(f"{FIT_PREFIX}{causes} reaches {shift} mm in front of the build; the build moves back {shift} mm")
    for module in spec.get("modules") or []:
        before = module.get("y", 0)
        module["y"] = before + shift
        lines.append(f"{FIT_PREFIX}{module['id']}: y {before} → {before + shift} mm")
    for shelf in spec.get("wall_shelves") or []:
        before = shelf.get("y", 0)
        shelf["y"] = before + shift
        lines.append(f"{FIT_PREFIX}{shelf['id']}: wall shelf y {before} → {before + shift} mm")
    for part in spec.get("extra_parts") or []:
        for placement in part.get("placements") or []:
            placement["y"] += shift
        if part.get("placements"):
            lines.append(f"{FIT_PREFIX}{part['id']}: extra part pieces move back {shift} mm")
    envelope = spec.get("envelope")
    if envelope is not None:
        lines.append(f"{FIT_PREFIX}envelope depth {envelope['depth']} → {envelope['depth'] + shift} mm")
        envelope["depth"] += shift


def fit_decision(lines: list[str]) -> tuple[str, str] | None:
    """The decisions-note row (topic, decision) for the fit lines among `lines`, or `None` without a fit."""
    fitted = [line[len(FIT_PREFIX) :] for line in lines if line.startswith(FIT_PREFIX)]
    if not fitted:
        return None
    return "Protruding shelf fit", "; ".join(fitted)


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
    for slug, change in (requested.get("extra_parts") or {}).items():
        if slug not in known_parts:
            raise _unknown("extra part", slug, known_parts)
        _apply_extra_part_change(next(part for part in parts if part["id"] == slug), change, lines)
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

    fit_protruding_shelves(spec, lines)
    return spec, lines


def derived_changes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """The cut-list rows and hardware lines a revision adds, removes or changes, derived from both documents.

    Shown in the confirmation after the change lines (partial-and-folded-dividers); an unreadable
    earlier document gives no lines rather than a guess.
    """
    try:
        old = CustomBuildSpec.model_validate(before).model_dump(mode="json")
        old_parts, old_hardware, _ = derive(old)
        new_parts, new_hardware, _ = derive(after)
    except (ValueError, SpecValidationError, KeyError, TypeError):
        return []
    lines = []
    was = {part["id"]: part for part in old_parts}
    now = {part["id"]: part for part in new_parts}
    for part_id in dict.fromkeys([*was, *now]):
        a, b = was.get(part_id), now.get(part_id)
        if a is None and b is not None:
            lines.append(f"Cut list: + {part_id} {b['l']} × {b['w']} mm ×{b['qty']}")
        elif b is None and a is not None:
            lines.append(f"Cut list: − {part_id} {a['l']} × {a['w']} mm ×{a['qty']}")
        elif a is not None and b is not None and (a["l"], a["w"], a["qty"]) != (b["l"], b["w"], b["qty"]):
            lines.append(
                f"Cut list: {part_id} {a['l']} × {a['w']} mm ×{a['qty']} → {b['l']} × {b['w']} mm ×{b['qty']}"
            )
    old_hw = {line["id"]: line for line in old_hardware}
    new_hw = {line["id"]: line for line in new_hardware}
    for line_id in dict.fromkeys([*old_hw, *new_hw]):
        a, b = old_hw.get(line_id), new_hw.get(line_id)
        item = (b or a or {}).get("item", line_id)
        old_qty = a["qty"] if a is not None else 0
        new_qty = b["qty"] if b is not None else 0
        if old_qty == new_qty:
            continue
        lines.append(f"Hardware: {item} {_quantity(old_qty)} → {_quantity(new_qty)}")
    return lines


def _quantity(qty: Any) -> str:
    return "no quantity" if qty == "" else str(qty)
