"""`room_fit` (Designer): a placement checked against the room's plan.

Uses the approved (else latest) composition version's corners and openings when
that document has a room plan — the same source as the inspector dimensions —
and falls back to the house-file room otherwise. Builds a room-scene document,
runs the room contract, and returns either the refusal or the placement and the
document a room render uses.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, Field

from app import compositions
from app.agent import house_file
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.agent.tools.shared import read_input, version_folder
from app.blender.custom_build import derive as custom_derive
from app.blender.room_contract import normalise_room_scene
from app.blender.spec_contract import SpecValidationError
from app.guidelines.rules import evaluate, partition, refusal_text, warnings_note


class RoomFitArgs(BaseModel):
    room_name: str
    package_id: str
    version: int | None = Field(default=None, description="a version number; the latest when left out")
    wall: int = Field(
        description=(
            "wall index along the room's corners, counted from 0. The house-note label "
            "'wall 1' is index 0, 'wall 2' is index 1, and so on"
        )
    )
    offset_mm: float = Field(description="distance along the wall from its start, in mm")


def room_document(room: Any, wall: int, offset_mm: float) -> dict[str, Any]:
    return {
        "kind": "room_scene",
        "schema_version": 1,
        "units": "mm",
        "room": {
            "corners": room.corners_mm,
            "height_mm": room.height_mm,
            "wall_thickness_mm": room.wall_thickness_mm,
        },
        "openings": room.openings,
        "placement": {"wall": wall, "offset_mm": offset_mm},
        "furnishings": [],
        "output": {"kind": "still"},
    }


def opening_in_the_way(room: Any, wall: int, offset_mm: float, overall: dict[str, int]) -> str | None:
    """A refusal naming the opening the piece would block, or `None`.

    A door is blocked by any piece in front of it; a window only when the piece
    is taller than its sill. The room contract checks the wall, the ceiling and
    the footprint; this is the rule for openings.
    """
    start, end = offset_mm, offset_mm + overall["w"]
    for index, opening in enumerate(room.openings or []):
        if opening["wall"] != wall:
            continue
        o_start, o_end = opening["offset_mm"], opening["offset_mm"] + opening["width_mm"]
        if o_end <= start or o_start >= end:
            continue
        if opening["type"] == "door" or opening.get("sill_mm", 0) < overall["h"]:
            return (
                f"it does not fit: it would block the {opening['type']} on wall {wall} "
                f"(opening {index}, {o_start:g} to {o_end:g} mm along the wall)"
            )
    return None


def _room_for_fit(session, root, room_name: str) -> Any | None:
    """Composition plan when present, else the house-file room, else `None`."""
    plan = compositions.placement_room(session, root, room_name)
    if plan is not None:
        return SimpleNamespace(
            name=plan["name"],
            corners_mm=plan["corners_mm"],
            height_mm=plan["height_mm"],
            wall_thickness_mm=plan["wall_thickness_mm"],
            openings=plan["openings"],
        )
    return house_file.room_by_name(session, room_name)


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(RoomFitArgs, arguments)
    if args is None:
        return problem
    with ctx.deps.session() as session:
        room = _room_for_fit(session, ctx.deps.render_root, args.room_name)
        if room is None:
            names = [r.name for r in house_file.rooms(session)]
            known = f"its rooms are: {', '.join(names)}" if names else "no rooms are recorded yet"
            return (
                f"there is no room {args.room_name!r} in the house file; {known}. "
                "Intake records a room from its measurements or a plan"
            )
        document = room_document(room, args.wall, args.offset_mm)
        fit_room = room

    folder, number, problem = version_folder(ctx.deps, args.package_id, args.version)
    if folder is None:
        return problem
    stored = read_input(folder)
    if stored is None:
        return f"version {number} of {args.package_id!r} has no readable document"
    overall = custom_derive.overall(stored)
    blocked = opening_in_the_way(fit_room, args.wall, args.offset_mm, overall)
    if blocked:
        return blocked
    try:
        context = normalise_room_scene(
            document, package_overall={key: float(value) for key, value in overall.items()}
        )
    except SpecValidationError as error:
        return f"it does not fit: {error}"
    placement = {
        "wall": context.placement["wall"],
        "offset_mm": context.placement["offset_mm"],
        "package_overall_mm": overall,
    }
    refusals, warnings = partition(evaluate(ctx.deps.design_rules, "placement", context))
    if refusals:
        return refusal_text(refusals)
    note = f"Design-rule warnings: {warnings_note(warnings)}\n" if warnings else ""
    return (
        f"{args.package_id} version {number} fits in {args.room_name} on wall {args.wall} at "
        f"offset {args.offset_mm:g} mm.\n"
        f"{note}"
        f"Placement: {json.dumps(placement)}\n"
        f"Room document (pass it as `room` to render_turntable): {json.dumps(context.input_document())}"
    )


room_fit = AgentTool(
    name="room_fit",
    description=(
        "Check whether a piece fits a room: give the room's name, the piece and version, a wall "
        "index and an offset along it. Uses the approved room composition's plan when one exists "
        "(the same walls and openings as the inspector), otherwise the house-file room. Returns "
        "the placement and the room document, or says what is in the way."
    ),
    schema=RoomFitArgs,
    run=run,
)
