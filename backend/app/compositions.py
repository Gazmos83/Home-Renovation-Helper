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
    apartment_wall_labels,
    parse_composition,
    place_items,
    room_geometry,
)
from app.blender.custom_build import derive as custom_derive
from app.blender.shell_contract import normalise_shell
from app.blender.spec_contract import SpecValidationError
from app.guidelines.rules import Rule, evaluate, partition, refusal_text


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


def _refuse_spec(error: SpecValidationError) -> CompositionRefused:
    message = str(error)
    match = _UNKNOWN.match(message)
    if match:
        where = match["where"]
        prefix = "" if where == "composition" else f"{where}."
        return CompositionRefused(message, unknown_field=f"{prefix}{match['name']}")
    return CompositionRefused(message)


def _rooms_in_scope(session, scope: str, name: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The scope's rooms by name (house-file shape) and, for an apartment, its shell document."""
    if scope == "room":
        room = house_file.room_by_name(session, name)
        if room is None:
            known = [r.name for r in house_file.rooms(session)]
            listed = f"the rooms are: {', '.join(known)}" if known else "no rooms are recorded yet"
            raise CompositionRefused(
                f"there is no room {name!r} in the house file; {listed}. Intake records a room from its measurements or a plan"
            )
        return {room.name: house_file.describe_room(room)}, None
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


def _where(placement: dict[str, Any]) -> str:
    if "wall" in placement:
        return f"against wall {placement['wall']} at {placement['offset_mm']:g} mm"
    return f"at ({placement['x_mm']:g}, {placement['y_mm']:g}) mm turned {placement['rotation_deg']:g}°"


def _changes(previous: dict[str, Any] | None, document: dict[str, Any]) -> list[str]:
    if previous is None:
        return [f"placed: {item['id']}" for item in document["items"]]
    before = {item["id"]: item for item in previous.get("items", [])}
    after = {item["id"]: item for item in document["items"]}
    lines = [f"added: {i}" for i in after if i not in before]
    lines += [f"removed: {i}" for i in before if i not in after]
    lines += [f"moved: {i}" for i in after if i in before and before[i].get("placement") != after[i]["placement"]]
    lines += [
        f"changed: {i}" for i in after
        if i in before and before[i].get("placement") == after[i]["placement"] and before[i] != after[i]
    ]
    return lines


def propose(
    session, *, render_root: Path, room: str | None, apartment: str | None, items: list[dict[str, Any]],
    max_items: int, rules,
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
    try:
        parsed = parse_composition(document, max_items=max_items)
    except SpecValidationError as error:
        raise _refuse_spec(error) from None
    rooms, shell = _rooms_in_scope(session, scope, name)
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
        stored, subjects = place_items(parsed, rooms=geometry, piece_sizes=sizes, scope_room=canonical)
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
    count = f"{len(stored['items'])} item(s)" if stored["items"] else "the room only, no items"
    lines = [f"{'Room' if scope == 'room' else 'Apartment'} {canonical or name}: {count}"]
    for item in stored["items"]:
        size = sizes_by_id[item["id"]]
        label = f"{item['package_id']} v{item['version']}" if item["type"] == "piece" else item["name"]
        lines.append(
            f"- {item['id']} ({item['type']}, {label}): {size['w']:g} × {size['d']:g} × {size['h']:g} mm, "
            f"{_where(item['placement'])}" + (f", in {item['room']}" if "room" in item else "")
        )
    if warnings:
        lines.append(f"Design-rule warnings: {warnings}")
    if latest is not None:
        lines.append(f"Compared with version {latest}: " + ("; ".join(changes) or "no change"))
    return Proposal(scope, canonical or name, stored, "\n".join(lines), warnings, changes, latest)


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
