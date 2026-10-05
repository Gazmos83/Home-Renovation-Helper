"""`room_fit` (Designer): a placement checked against a house-file room.

Builds a room-scene document from the stored room, the piece version's overall
size, a wall and an offset, runs the room contract over it, and returns either
the refusal (naming the wall and the excess) or the placement and the document
a room render uses.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.agent import house_file
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.agent.tools.shared import read_input, version_folder
from app.blender.custom_build import derive as custom_derive
from app.blender.room_contract import normalise_room_scene
from app.blender.spec_contract import SpecValidationError


class RoomFitArgs(BaseModel):
    room_name: str
    package_id: str
    version: int | None = Field(default=None, description="a version number; the latest when left out")
    wall: int = Field(description="wall index, counted from 0 along the room's corners")
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
    for index, opening in enumerate(room.openings):
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


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(RoomFitArgs, arguments)
    if args is None:
        return problem
    with ctx.deps.session() as session:
        room = house_file.room_by_name(session, args.room_name)
        if room is None:
            known = ", ".join(r.name for r in house_file.rooms(session)) or "none"
            return f"there is no room {args.room_name!r} in the house file; its rooms are: {known}"
        document = room_document(room, args.wall, args.offset_mm)

    folder, number, problem = version_folder(ctx.deps, args.package_id, args.version)
    if folder is None:
        return problem
    stored = read_input(folder)
    if stored is None:
        return f"version {number} of {args.package_id!r} has no readable document"
    overall = custom_derive.overall(stored)
    with ctx.deps.session() as session:
        stored_room = house_file.room_by_name(session, args.room_name)
        blocked = opening_in_the_way(stored_room, args.wall, args.offset_mm, overall)
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
    return (
        f"{args.package_id} version {number} fits in {args.room_name} on wall {args.wall} at "
        f"offset {args.offset_mm:g} mm.\n"
        f"Placement: {json.dumps(placement)}\n"
        f"Room document (pass it as `room` to render_turntable): {json.dumps(context.input_document())}"
    )


room_fit = AgentTool(
    name="room_fit",
    description=(
        "Check whether a piece fits a room from the house file: give the room's name, the piece "
        "and version, a wall index and an offset along it. Returns the placement and the room "
        "document, or says what is in the way."
    ),
    schema=RoomFitArgs,
    run=run,
)
