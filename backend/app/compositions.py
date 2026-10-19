"""Room compositions on disk (room-composition): reading stored documents.

A composition version folder holds the normalised document as `input.json`;
it is the source of truth for that version and never changes after it is made.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.agent import house_file
from app.assets import models as library
from app.blender import storage
from app.blender.composition_contract import (
    KIND,
    SCHEMA_VERSION,
    UNITS,
    ItemSubject,
    _wall_pose,
    apartment_wall_labels,
    floor_summary,
    parse_composition,
    place_items,
    room_geometry,
)
from app.blender.custom_build import derive as custom_derive
from app.blender.lighting import DEFAULT_LIGHTING, Lighting
from app.blender.room_contract import Point, _rotated_footprint, polygon_distance
from app.blender.shell_contract import normalise_shell
from app.blender.spec_contract import SpecValidationError
from app.guidelines.rules import Rule, evaluate, partition, refusal_text
from app.packages.placements import read_placement


def read_document(folder: Path) -> dict[str, Any] | None:
    try:
        return json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def scope_name(document: dict[str, Any]) -> str:
    scope = document.get("scope") or {}
    return str(scope.get("room") or scope.get("apartment") or "")


def _point(p: Any) -> list[float]:
    return [round(float(p[0]), 1), round(float(p[1]), 1)]


def _centre(corners: Any) -> list[float]:
    return [round(sum(float(c[0]) for c in corners) / len(corners), 1),
            round(sum(float(c[1]) for c in corners) / len(corners), 1)]


def room_dimensions(document: dict[str, Any]) -> dict[str, Any] | None:
    """A version's wall lengths and ceiling heights, from its stored document only
    (project-room-inspection), or `None` when the document holds no room plan.

    Each unique wall once, labelled as in the surface map, with its plan end points and
    length; each room's ceiling height with a plan point inside it (the corners' mean).
    """
    resolved = document.get("resolved") or {}
    try:
        if "apartment" in (document.get("scope") or {}):
            shell = normalise_shell(resolved["shell"])
            labels = apartment_wall_labels(shell.walls)
            walls = [
                {"label": labels[w.id], "from": _point(w.a), "to": _point(w.b), "length_mm": round(w.length_mm)}
                for w in shell.walls
            ]
            ceilings = [
                {"room": r.name, "height_mm": round(r.height_mm), "at": _centre(r.corners)} for r in shell.rooms
            ]
        else:
            wanted = scope_name(document)
            rooms = resolved.get("rooms") or []
            room = next((r for r in rooms if r.get("name") == wanted), None)
            if room is None:
                return None
            corners = room["corners"]
            walls = []
            for index, a in enumerate(corners):
                b = corners[(index + 1) % len(corners)]
                walls.append({
                    "label": f"wall {index + 1}", "from": _point(a), "to": _point(b),
                    "length_mm": round(math.dist((float(a[0]), float(a[1])), (float(b[0]), float(b[1])))),
                })
            ceilings = [{"room": room["name"], "height_mm": round(float(room["height_mm"])), "at": _centre(corners)}]
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError, SpecValidationError):
        return None
    return {"walls": walls, "ceilings": ceilings}


def _scope_document(
    session: Session, root: Path, *, scope: str, name: str, version: int | None = None
) -> tuple[dict[str, Any], int, bool] | None:
    """The stored document for a composition version, its number, and whether it is approved.

    With `version` omitted, uses the approved version when one is approved, else the latest.
    """
    composition = house_file.composition_by_scope(session, scope, name)
    if composition is None:
        return None
    versions = house_file.composition_version_rows(session, composition)
    if not versions:
        return None
    approved = house_file.approved_composition_version_of(session, composition.id)
    if version is None:
        number = approved if approved is not None else versions[-1].version
    else:
        if house_file.composition_version_row(session, composition.id, version) is None:
            return None
        number = version
    document = read_document(storage.composition_version_dir(root, composition.slug, number))
    if document is None:
        return None
    return document, number, approved is not None and approved == number


def dimensions_of_scope(
    session: Session, root: Path, *, scope: str, name: str, version: int | None = None
) -> dict[str, Any] | None:
    """Wall lengths and ceilings for a composition version of this scope, or `None`.

    With `version` omitted, uses the approved version when one is approved, else the latest.
    The returned dict has `version`, `approved`, `walls` and `ceilings` (the same walls and
    ceilings the inspector's dimensions route returns).
    """
    loaded = _scope_document(session, root, scope=scope, name=name, version=version)
    if loaded is None:
        return None
    document, number, is_approved = loaded
    found = room_dimensions(document)
    if found is None:
        return None
    return {
        "version": number,
        "approved": is_approved,
        "walls": found["walls"],
        "ceilings": found["ceilings"],
    }


class GapRefused(ValueError):
    """An item's gaps cannot be measured; the message says why in plain words."""


def _mm(value: float) -> int:
    return math.floor(value + 0.5)


def _key(text: Any) -> str:
    return re.sub(r"[\s_-]+", " ", str(text or "")).strip().casefold()


def _find_item(document: dict[str, Any], placed: list[dict[str, Any]], item: str) -> dict[str, Any]:
    """The placed item named by its id, its name or its package id (case and spacing ignored)."""
    names = {raw.get("id"): (raw.get("name"), raw.get("package_id")) for raw in document.get("items") or []}
    wanted = _key(item)
    matches = [p for p in placed if wanted in {_key(p["id"]), *(_key(n) for n in names.get(p["id"], ()) if n)}]
    if not matches:
        raise GapRefused(f"there is no item {item!r} in this room version")
    if len(matches) > 1:
        raise GapRefused(f"{item!r} names more than one item ({', '.join(p['id'] for p in matches)}); name one by its id")
    return matches[0]


def _shape(placed: dict[str, Any]) -> tuple[tuple[Point, ...], float, float]:
    """An item's plan footprint and its height range (underside, top)."""
    size = placed["size_mm"]
    footprint = _rotated_footprint(
        float(placed["centre_mm"][0]), float(placed["centre_mm"][1]),
        float(size["w"]), float(size["d"]), float(placed["rotation_deg"]),
    )
    base = float(placed.get("base_mm", 0.0))
    return footprint, base, base + float(size["h"])


def gaps_of(document: dict[str, Any], item: str) -> dict[str, Any]:
    """Clear distances in whole mm for one item of a room version, from its stored document
    only (measure-gaps): to every wall, to every other item and to the ceiling."""
    if "apartment" in (document.get("scope") or {}):
        raise GapRefused("gaps can be measured in a single room's version, not yet in an apartment's")
    resolved = document.get("resolved") or {}
    room = next((r for r in resolved.get("rooms") or [] if r.get("name") == scope_name(document)), None)
    if room is None:
        raise GapRefused("this room version has no room plan to measure against")
    placed = [p for p in resolved.get("items") or [] if "size_mm" in p and "strip" not in p]
    target = _find_item(document, placed, item)
    footprint, base, top = _shape(target)
    corners = [(float(x), float(y)) for x, y in room["corners"]]
    walls = [
        {"label": f"wall {i + 1}", "gap_mm": _mm(polygon_distance(footprint, (a, corners[(i + 1) % len(corners)])))}
        for i, a in enumerate(corners)
    ]
    names = {raw.get("id"): raw.get("name") or raw.get("package_id") for raw in document.get("items") or []}
    others = []
    for other in placed:
        if other is target or other.get("hidden") or other.get("room") != target.get("room"):
            continue
        other_footprint, other_base, other_top = _shape(other)
        plan = polygon_distance(footprint, other_footprint)
        vertical = plan == 0 and (other_base >= top or base >= other_top)
        gap = max(other_base - top, base - other_top) if vertical else plan
        others.append({"id": other["id"], "name": names.get(other["id"]) or other["id"], "gap_mm": _mm(gap), "vertical": vertical})
    return {
        "item": target["id"],
        "name": names.get(target["id"]) or target["id"],
        "walls": walls,
        "items": others,
        "ceiling_mm": _mm(float(room["height_mm"]) - top),
        "underside_mm": _mm(base) if base > 0 else None,
    }


def end_wall_gaps(room: Any, placement: dict[str, Any], size: tuple[float, float, float]) -> tuple[int, int, int, int] | None:
    """For a piece saved on a wall of a house-file room: (the wall at its left end, its gap,
    the wall at its right end, its gap), walls numbered from 1; `None` when it cannot be read.
    Corners run counter-clockwise, so wall i's left end, seen facing it, meets wall i+1."""
    try:
        geometry = room_geometry("room", {
            "corners_mm": room.corners_mm, "height_mm": room.height_mm, "wall_thickness_mm": room.wall_thickness_mm,
        })
        index = int(placement["wall"])
        _footprint, centre, rotation, _outward = _wall_pose("piece", geometry, index, float(placement["offset_mm"]), size)
    except (KeyError, TypeError, ValueError, SpecValidationError):
        return None
    document = {
        "scope": {"room": "room"}, "items": [{"id": "piece"}],
        "resolved": {
            "rooms": [{"name": "room", "corners": [list(c) for c in geometry.corners], "height_mm": geometry.height_mm}],
            "items": [{"id": "piece", "room": "room", "size_mm": {"w": size[0], "d": size[1], "h": size[2]},
                       "centre_mm": list(centre), "rotation_deg": rotation}],
        },
    }
    walls = gaps_of(document, "piece")["walls"]
    left, right = (index + 1) % len(walls), (index - 1) % len(walls)
    return left + 1, walls[left]["gap_mm"], right + 1, walls[right]["gap_mm"]


def gaps_of_scope(
    session: Session, root: Path, *, name: str, version: int, item: str
) -> dict[str, Any]:
    """`gaps_of` for a room's composition version, or `GapRefused` when it cannot be read."""
    loaded = _scope_document(session, root, scope="room", name=name, version=version)
    if loaded is None:
        raise GapRefused(f"{name} has no room version {version}")
    return {"version": loaded[1], **gaps_of(loaded[0], item)}


def placement_room(
    session: Session, root: Path, room_name: str, *, version: int | None = None
) -> dict[str, Any] | None:
    """A house-file-shaped room plan from the room's composition version, or `None`.

    Uses the approved version when one is approved, else the latest (or `version` when given).
    Shape: `name`, `corners_mm`, `height_mm`, `wall_thickness_mm`, `openings` — what
    `room_fit` and `room_geometry` expect. `None` when there is no composition or no room plan.
    """
    loaded = _scope_document(session, root, scope="room", name=room_name, version=version)
    if loaded is None:
        return None
    document, _number, _approved = loaded
    wanted = scope_name(document) or room_name
    rooms = (document.get("resolved") or {}).get("rooms") or []
    room = next((entry for entry in rooms if entry.get("name") == wanted), None)
    if room is None:
        return None
    try:
        corners = room["corners"]
        return {
            "name": str(room.get("name") or wanted),
            "corners_mm": [[float(p[0]), float(p[1])] for p in corners],
            "height_mm": float(room["height_mm"]),
            "wall_thickness_mm": float(room.get("wall_thickness_mm") or 100),
            "openings": list(room.get("openings") or []),
        }
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def placing_model(session: Session, root: Path, model_id: UUID) -> list[str]:
    """Every composition version that places the library model, as "<scope> v<N>"."""
    wanted = str(model_id)
    found = []
    for slug, numbers in storage.list_compositions(root):
        for number in numbers:
            document = read_document(storage.composition_version_dir(root, slug, number))
            if document is None:
                continue
            if any(i.get("type") == "model" and str(i.get("model_id")) == wanted for i in document.get("items", [])):
                found.append(f"{scope_name(document) or slug} v{number}")
    return found


def pieces_in_use(root: Path, package_id: str, version: int) -> list[str]:
    """Every composition version that places the piece version, as "<scope> version <N>"."""
    found = []
    for slug, numbers in storage.list_compositions(root):
        for number in numbers:
            document = read_document(storage.composition_version_dir(root, slug, number))
            if document is None:
                continue
            if any(
                i.get("type") == "piece" and i.get("package_id") == package_id and i.get("version") == version
                for i in document.get("items", [])
            ):
                found.append(f"{scope_name(document) or slug} version {number}")
    return found


def rule_outcome(rules: tuple[Rule, ...], subjects: list[tuple[str, ItemSubject]]) -> tuple[str | None, str]:
    """(a refusal naming the item and the rule, or `None`; the warnings, each naming its item)."""
    refusals: list[str] = []
    warnings: list[str] = []
    for item_id, subject in subjects:
        refused, warned = partition(evaluate(rules, "placement", subject))
        if refused:
            refusals.append(f"item {item_id}: {refusal_text(refused)}")
        warnings += [f"item {item_id}: {finding.text()}" for finding in warned]
    return ("; ".join(refusals) or None), "; ".join(warnings)


# --- proposing a composition (compose_room) ----------------------------------------------

_UNKNOWN: re.Pattern[str] = re.compile(r"^unknown (?P<where>.+?) field: (?P<name>\S+)$")


class CompositionRefused(Exception):
    """A proposal refused before any pause; the message is safe to show and names the problem."""

    def __init__(self, reason: str, unknown_field: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.unknown_field = unknown_field


@dataclass
class Proposal:
    scope: str
    name: str
    document: dict[str, Any]
    summary: str
    warnings: str
    changes: list[str] = field(default_factory=list)
    latest: int | None = None
    # The calculations shown with the confirmation, one row per item (confirmation-summaries).
    table: dict[str, Any] | None = None


def _refuse_spec(error: SpecValidationError) -> CompositionRefused:
    message = str(error)
    match = _UNKNOWN.match(message)
    if match:
        where = match["where"]
        prefix = "" if where == "composition" else f"{where}."
        return CompositionRefused(message, unknown_field=f"{prefix}{match['name']}")
    return CompositionRefused(message)


def _rooms_in_scope(
    session, scope: str, name: str, *, render_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The scope's rooms by name (house-file shape) and, for an apartment, its shell document.

    For a single room, prefers the approved (else latest) composition version's plan when
    `render_root` is set and that document has a room plan.
    """
    if scope == "room":
        room = house_file.room_by_name(session, name)
        if room is None:
            known = [r.name for r in house_file.rooms(session)]
            listed = f"the rooms are: {', '.join(known)}" if known else "no rooms are recorded yet"
            raise CompositionRefused(
                f"there is no room {name!r} in the house file; {listed}. Intake records a room from its measurements or a plan"
            )
        described = house_file.describe_room(room)
        if render_root is not None:
            plan = placement_room(session, render_root, room.name)
            if plan is not None:
                described = {
                    **described,
                    "corners_mm": plan["corners_mm"],
                    "height_mm": plan["height_mm"],
                    "wall_thickness_mm": plan["wall_thickness_mm"],
                    "openings": plan["openings"],
                }
        return {room.name: described}, None
    apartment = house_file.find_apartment(session, name)
    if apartment is None:
        known = [a.name for a in house_file.apartments(session)]
        listed = f"the apartments are: {', '.join(known)}" if known else "no apartments are recorded yet"
        raise CompositionRefused(f"there is no apartment {name!r} in the house file; {listed}")
    rooms = {r.name: house_file.describe_room(r) for r in house_file.rooms_of(session, apartment)}
    try:
        shell = house_file.apartment_shell_document(session, apartment)
    except house_file.HouseFileError as error:
        raise CompositionRefused(f"the apartment {apartment.name!r} cannot be built: {error}") from None
    return rooms, shell


def _piece_size(root: Path, session, item: dict[str, Any]) -> tuple[float, float, float]:
    package_id, version = item["package_id"], item["version"]
    approved = house_file.approved_version_of(session, package_id)
    if approved != version:
        named = f"version {approved} is approved" if approved else "no version of it is approved"
        raise CompositionRefused(
            f"{package_id} version {version} is not approved ({named}); the owner approves a built "
            "version on the Pieces page or the project panel first"
        )
    try:
        design = json.loads((storage.version_dir(root, package_id, version) / storage.INPUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, storage.InvalidPackageId):
        raise CompositionRefused(f"{package_id} version {version} cannot be read") from None
    overall = custom_derive.overall(design)
    return float(overall["w"]), float(overall["d"]), float(overall["h"])


def _model(session, item: dict[str, Any]):
    try:
        model = library.get_model(session, UUID(str(item.get("model_id"))))
    except ValueError:
        model = None
    if model is None:
        raise CompositionRefused(f"item {item.get('id')}: there is no model {item.get('model_id')!r} in the library")
    if model.state == "checking":
        raise CompositionRefused(f"item {item.get('id')}: the model {model.name!r} is not ready yet; it is still being checked")
    if model.state != "ready":
        raise CompositionRefused(f"item {item.get('id')}: the model {model.name!r} was refused: {model.reason}")
    return model


def _on_wall(placement: dict[str, Any], walls: tuple[Any, ...], width: float) -> str:
    """A wall placement as the owner gives it: walls numbered from 1 as the room view labels them,
    and the distance from the wall's left end seen facing it (place-piece-from-owner-words)."""
    left = walls[placement["wall"]].length_mm - placement["offset_mm"] - width
    return f"wall {placement['wall'] + 1}, {round(left, 1):g} mm from the left end"


def _where(placement: dict[str, Any], walls: tuple[Any, ...], width: float) -> str:
    if "wall" in placement:
        hung = f", hung at {placement['mount_height_mm']:g} mm" if "mount_height_mm" in placement else ""
        return f"against {_on_wall(placement, walls, width)}{hung}"
    return f"at ({placement['x_mm']:g}, {placement['y_mm']:g}) mm turned {placement['rotation_deg']:g}°"


def _changes(previous: dict[str, Any] | None, document: dict[str, Any]) -> list[str]:
    if previous is None:
        placed = [f"placed: {item['id']}" for item in document["items"]]
        return placed + ([f"floor: {floor_summary(document['floor'])}"] if document.get("floor") else [])
    before = {item["id"]: item for item in previous.get("items", [])}
    after = {item["id"]: item for item in document["items"]}
    lines = [f"added: {i}" for i in after if i not in before]
    lines += [f"removed: {i}" for i in before if i not in after]
    lines += [f"moved: {i}" for i in after if i in before and before[i].get("placement") != after[i]["placement"]]
    same_place = [i for i in after if i in before and before[i].get("placement") == after[i]["placement"]]

    def without_flag(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "hidden"}

    # Only the hidden flag changed: say which way (hidden-room-items).
    flag_only = [
        i for i in same_place
        if bool(before[i].get("hidden")) != bool(after[i].get("hidden")) and without_flag(before[i]) == without_flag(after[i])
    ]
    lines += [f"{'hidden' if after[i].get('hidden') else 'shown'}: {i}" for i in flag_only]
    lines += [f"changed: {i}" for i in same_place if i not in flag_only and before[i] != after[i]]
    # The floor finish is part of the version (room-floor-finish).
    if document.get("floor") and document.get("floor") != previous.get("floor"):
        lines.append(f"floor: {floor_summary(document['floor'])}")
    elif previous.get("floor") and not document.get("floor"):
        lines.append("floor finish removed")
    return lines


def with_saved_place(
    session, root: Path, room_name: str, package_id: str, version: int
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """The items and floor of the room's latest composition, with the piece version added at its
    stored placement, or moved there when the piece is already in the room
    (place-piece-from-owner-words). The model copies no item list on this path."""
    stored = read_placement(storage.version_dir(root, package_id, version), room_name)
    if stored is None:
        raise CompositionRefused(
            f"the piece has no place in {room_name} yet; ask the owner where it goes with ask_placement"
        )
    document = None
    composition = house_file.composition_by_scope(session, "room", room_name)
    if composition is not None:
        rows = house_file.composition_version_rows(session, composition)
        if rows:
            document = read_document(storage.composition_version_dir(root, composition.slug, rows[-1].version))
    kept = list((document or {}).get("items") or [])
    previous = next((i for i in kept if i.get("type") == "piece" and i.get("package_id") == package_id), None)
    items = [i for i in kept if i is not previous]
    placement = {"wall": stored["wall"], "offset_mm": stored["offset_mm"]}
    if stored.get("mount_height_mm") is not None:
        placement["mount_height_mm"] = stored["mount_height_mm"]
    items.append({
        "id": previous["id"] if previous else package_id, "type": "piece",
        "package_id": package_id, "version": version, "placement": placement,
    })
    return items, (document or {}).get("floor")


def propose(
    session, *, render_root: Path, room: str | None, apartment: str | None, items: list[dict[str, Any]],
    max_items: int, rules, floor: dict[str, Any] | None = None, lighting: Lighting = DEFAULT_LIGHTING,
) -> Proposal:
    """Validate a composition against the house file, the library and the rules; nothing is written."""
    if bool(room) == bool(apartment):
        raise CompositionRefused("name exactly one scope: a room, or an apartment")
    scope, name = ("room", room) if room else ("apartment", apartment)
    filled = []
    for raw in items:
        item = dict(raw)
        if item.get("type") == "model" and not all(k in item for k in ("width_mm", "depth_mm", "height_mm")):
            model = _model(session, item)
            for key, value in (("width_mm", model.width_mm), ("depth_mm", model.depth_mm), ("height_mm", model.height_mm)):
                item.setdefault(key, value)
            item.setdefault("name", model.name)
        filled.append(item)
    document = {"kind": KIND, "schema_version": SCHEMA_VERSION, "units": UNITS, "scope": {scope: name}, "items": filled}
    if floor is not None:
        document["floor"] = floor
    try:
        parsed = parse_composition(document, max_items=max_items)
    except SpecValidationError as error:
        raise _refuse_spec(error) from None
    rooms, shell = _rooms_in_scope(session, scope, name, render_root=render_root)
    canonical = next(iter(rooms)) if scope == "room" else None
    if canonical is not None:
        parsed["scope"] = {"room": canonical}
    sizes = {item["id"]: _piece_size(render_root, session, item) for item in parsed["items"] if item["type"] == "piece"}
    sources = {}
    for item in parsed["items"]:
        if item["type"] == "model":
            model = _model(session, item)
            sources[item["id"]] = {"kind": model.kind, "entry": model.entry}
    try:
        geometry = {room_name: room_geometry(room_name, data) for room_name, data in rooms.items()}
        stored, subjects = place_items(
            parsed, rooms=geometry, piece_sizes=sizes, scope_room=canonical, lighting=lighting,
        )
    except SpecValidationError as error:
        raise _refuse_spec(error) from None
    refusal, warnings = rule_outcome(rules, subjects)
    if refusal:
        raise CompositionRefused(refusal)
    for placed in stored["resolved"]["items"]:
        if placed["id"] in sources:
            placed["source"] = sources[placed["id"]]
    if shell is not None:
        stored["resolved"]["shell"] = shell

    existing = house_file.composition_by_scope(session, scope, canonical or name)
    latest = None
    previous = None
    if existing is not None:
        versions = house_file.composition_version_rows(session, existing)
        if versions:
            latest = versions[-1].version
            previous = read_document(storage.composition_version_dir(render_root, existing.slug, latest))
    changes = _changes(previous, stored)

    sizes_by_id = {p["id"]: p["size_mm"] for p in stored["resolved"]["items"]}
    resolved_by_id = {p["id"]: p for p in stored["resolved"]["items"]}
    hangs = any("base_mm" in p for p in stored["resolved"]["items"])
    columns = ["Item", "Kind", "Size (mm)", "Placement", "Centre (mm)", "Rotation"] + (["Hangs at (mm)"] if hangs else [])
    rows: list[list[str]] = []
    count = f"{len(stored['items'])} item(s)" if stored["items"] else "the room only, no items"
    lines = [f"{'Room' if scope == 'room' else 'Apartment'} {canonical or name}: {count}"]
    for item in stored["items"]:
        size = sizes_by_id[item["id"]]
        walls = geometry[item.get("room") or canonical].walls
        label = f"{item['package_id']} v{item['version']}" if item["type"] == "piece" else item["name"]
        lines.append(
            f"- {item['id']} ({item['type']}, {label}): {size['w']:g} × {size['d']:g} × {size['h']:g} mm, "
            f"{_where(item['placement'], walls, size['w'])}" + (f", in {item['room']}" if "room" in item else "")
            + (", hidden" if item.get("hidden") else "")
        )
        placed = resolved_by_id[item["id"]]
        placement = item["placement"]
        row = [
            label,
            item["type"],
            f"{size['w']:g} × {size['d']:g} × {size['h']:g}",
            _on_wall(placement, walls, size["w"]) if "wall" in placement
            else f"free, {placement['rotation_deg']:g}°",
            f"{placed['centre_mm'][0]:g}, {placed['centre_mm'][1]:g}",
            f"{placed['rotation_deg']:g}°",
        ]
        if hangs:
            row.append(f"{placed['base_mm']:g}" if "base_mm" in placed else "")
        rows.append(row)
    if stored.get("floor"):
        lines.append(f"Floor: {floor_summary(stored['floor'])}")
    if warnings:
        lines.append(f"Design-rule warnings: {warnings}")
    if latest is not None:
        lines.append(f"Compared with version {latest}: " + ("; ".join(changes) or "no change"))
    return Proposal(
        scope, canonical or name, stored, "\n".join(lines), warnings, changes, latest,
        table={"columns": columns, "rows": rows},
    )


def create_version(session, render_root: Path, proposal: Proposal, start) -> int:
    """Write the next version folder, record it and hand it to `start`; commits."""
    composition = house_file.record_composition(session, proposal.scope, proposal.name)
    version = storage.next_composition_version(render_root, composition.slug)
    folder = storage.composition_version_dir(render_root, composition.slug, version)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps(proposal.document, indent=2), encoding="utf-8")
    from app.blender import runner

    runner.mark_build_queued(folder)
    house_file.record_composition_version(session, composition, version, proposal.latest, proposal.changes)
    session.commit()
    start(composition.slug, version)
    return version
