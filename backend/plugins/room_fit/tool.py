"""`room_fit` (Designer): a placement checked against the room's plan.

Uses the approved (else latest) composition version's corners and openings when
that document has a room plan — the same source as the inspector dimensions —
and falls back to the house-file room otherwise. Builds a room-scene document,
runs the room contract, and returns either the refusal or the placement. A
placement that fits is stored with the version (view-piece-in-room), so a render
in that room reads it; no model copies the document between tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, Field

from app import compositions
from app.agent import house_file, measurements
from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.agent.tools.shared import read_input, version_folder
from app.blender.custom_build import derive as custom_derive
from app.blender.room_contract import normalise_room_scene
from app.blender.spec_contract import SpecValidationError
from app.guidelines.rules import evaluate, partition, refusal_text, warnings_note
from app.packages.placements import write_placement


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
    mount_height_mm: float | None = Field(
        default=None,
        description=(
            "for a piece hung on the wall: the height of its underside above the floor, in mm, as the "
            "owner wrote it. Leave out for a piece standing on the floor"
        ),
    )
    ceiling_gap_mm: float | None = Field(
        default=None,
        description=(
            "for a piece hung on the wall: how far below the ceiling its top is, in mm, as the owner "
            "wrote it (0 for flush). Give this or mount_height_mm, not both"
        ),
    )


def room_document(room: Any, wall: int, offset_mm: float, mount_height_mm: float | None = None) -> dict[str, Any]:
    placement: dict[str, Any] = {"wall": wall, "offset_mm": offset_mm}
    if mount_height_mm is not None:
        placement["mount_height_mm"] = mount_height_mm
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
        "placement": placement,
        "furnishings": [],
        "output": {"kind": "still"},
    }


def opening_in_the_way(
    room: Any, wall: int, offset_mm: float, overall: dict[str, int], mount_height_mm: float = 0.0
) -> str | None:
    """A refusal naming the opening the piece would block, or `None`.

    A door is blocked by any piece in front of it; a window only when the piece
    is taller than its sill. A hung piece blocks only an opening it hangs below the
    top of (conversation-continuity). The room contract checks the wall, the ceiling
    and the footprint; this is the rule for openings.
    """
    start, end = offset_mm, offset_mm + overall["w"]
    top = mount_height_mm + overall["h"]
    for index, opening in enumerate(room.openings or []):
        if opening["wall"] != wall:
            continue
        o_start, o_end = opening["offset_mm"], opening["offset_mm"] + opening["width_mm"]
        if o_end <= start or o_start >= end:
            continue
        sill = 0.0 if opening["type"] == "door" else opening.get("sill_mm", 0)
        if mount_height_mm >= sill + opening["height_mm"]:
            continue
        if opening["type"] == "door" or sill < top:
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


@dataclass(frozen=True)
class Fit:
    """A placement that fits: what was stored, and the design-rule warnings."""

    package_id: str
    version: int
    room: str
    wall: int
    offset_mm: float
    placement: dict[str, Any]
    scene: dict[str, Any]
    warnings: str
    mount_height_mm: float | None = None


def fit(
    ctx: ToolContext,
    room_name: str,
    package_id: str,
    version: int | None,
    wall: int,
    offset_mm: float,
    *,
    left_mm: float | None = None,
    store: bool = True,
    mount_height_mm: float | None = None,
    ceiling_gap_mm: float | None = None,
) -> Fit | str:
    """Check the placement; on success store it with the version (unless `store` is false).
    A hung piece takes its underside height, or its top's gap below the ceiling. A refusal is
    returned as text."""
    with ctx.deps.session() as session:
        room = _room_for_fit(session, ctx.deps.render_root, room_name)
        if room is None:
            names = [r.name for r in house_file.rooms(session)]
            known = f"its rooms are: {', '.join(names)}" if names else "no rooms are recorded yet"
            return (
                f"there is no room {room_name!r} in the house file; {known}. "
                "Intake records a room from its measurements or a plan"
            )
        fit_room = room

    folder, number, problem = version_folder(ctx.deps, package_id, version)
    if folder is None or number is None:
        return problem
    stored = read_input(folder)
    if stored is None:
        return f"version {number} of {package_id!r} has no readable document"
    overall = custom_derive.overall(stored)
    if ceiling_gap_mm is not None:
        mount_height_mm = float(fit_room.height_mm) - overall["h"] - ceiling_gap_mm
        if mount_height_mm < 0:
            return (
                f"it does not fit: the piece is {overall['h']:g} mm tall, so its top cannot be "
                f"{ceiling_gap_mm:g} mm below the {float(fit_room.height_mm):g} mm ceiling"
            )
    document = room_document(fit_room, wall, offset_mm, mount_height_mm)
    blocked = opening_in_the_way(fit_room, wall, offset_mm, overall, mount_height_mm or 0.0)
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
        **({"mount_height_mm": mount_height_mm} if mount_height_mm is not None else {}),
        "package_overall_mm": overall,
    }
    refusals, warnings = partition(evaluate(ctx.deps.design_rules, "placement", context))
    if refusals:
        return refusal_text(refusals)
    scene = context.input_document()
    if store:
        write_placement(
            folder,
            room_name,
            {
                "room": room_name,
                "wall": wall,
                "offset_mm": offset_mm,
                "left_mm": left_mm,
                **({"mount_height_mm": mount_height_mm} if mount_height_mm is not None else {}),
                "placement": placement,
                "scene": scene,
            },
        )
    return Fit(
        package_id=package_id,
        version=number,
        room=room_name,
        wall=wall,
        offset_mm=offset_mm,
        placement=placement,
        scene=scene,
        warnings=warnings_note(warnings) if warnings else "",
        mount_height_mm=mount_height_mm,
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(RoomFitArgs, arguments)
    if args is None:
        return problem
    if args.mount_height_mm is not None and args.ceiling_gap_mm is not None:
        return "give mount_height_mm or ceiling_gap_mm, not both"
    height = args.mount_height_mm if args.mount_height_mm is not None else args.ceiling_gap_mm
    if height is not None and not _owner_wrote(ctx, height):
        return (
            f"{height:g} mm is not a length the owner wrote in this conversation; ask the owner how high "
            "the piece hangs (ask_placement with hung true) and never work a height out yourself"
        )
    result = fit(
        ctx, args.room_name, args.package_id, args.version, args.wall, args.offset_mm,
        mount_height_mm=args.mount_height_mm, ceiling_gap_mm=args.ceiling_gap_mm,
    )
    if isinstance(result, str):
        return result
    note = f"\nDesign-rule warnings: {result.warnings}" if result.warnings else ""
    hung = (
        f", hung with its underside at {result.mount_height_mm:g} mm" if result.mount_height_mm is not None else ""
    )
    return (
        f"{args.package_id} version {result.version} fits in {args.room_name} on wall {args.wall} at "
        f"offset {args.offset_mm:g} mm{hung}. Placement saved for {args.room_name}; the Builder renders "
        f"it in the room with render_turntable in_room true.{note}"
    )


def _owner_wrote(ctx: ToolContext, value_mm: float) -> bool:
    """Whether the owner wrote this length (any unit) in the conversation, in a message or a form
    answer (conversation-continuity)."""
    texts = measurements.owner_texts(ctx.history)
    return any(abs(length.mm - value_mm) < 0.5 for text in texts for length in measurements.lengths(text))


room_fit = AgentTool(
    name="room_fit",
    description=(
        "Check whether a piece fits a room: give the room's name, the piece and version, a wall "
        "index and an offset along it. Uses the approved room composition's plan when one exists "
        "(the same walls and openings as the inspector), otherwise the house-file room. A "
        "placement that fits is saved for a render in that room; otherwise it says what is in the way."
    ),
    schema=RoomFitArgs,
    run=run,
)
