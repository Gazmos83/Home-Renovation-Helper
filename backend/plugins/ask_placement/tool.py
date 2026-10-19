"""`ask_placement` (Designer): where the bound piece goes in the conversation's room (view-piece-in-room).

The questions are written here, never by the model: which wall (each with its length) and
how far from the wall's left end, seen facing it. The answers are turned into the wall
index and offset the room fit takes, the fit runs, and a placement that fits is stored with
the version, and the Designer then proposes the room with the piece at that place
(place-piece-from-owner-words) with no document passed between tools.
"""

from __future__ import annotations

import math
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent import house_file
from app.agent.prompts import neutralise
from app.agent.tools.base import (
    AgentTool,
    Questions,
    ToolContext,
    ToolOutput,
    parse_args,
)
from app.agent.tools.shared import read_input, version_folder
from app.blender.custom_build import derive as custom_derive
from app.blender.room_contract import normalise_room_shell
from app.blender.spec_contract import SpecValidationError
from app.engineering.chat import HANG
from plugins.room_fit.tool import _room_for_fit, fit

WALL_QUESTION = "Where would you like to place the piece? Check out the Room layout."
DISTANCE_QUESTION = "How far from the left end of that wall should the piece start? (seen facing the wall)"
# Asked only for a piece hung on the wall (conversation-continuity).
GAP_QUESTION = "How far below the ceiling should the top of the piece be? (0 for flush with the ceiling)"
MAX_WALL_CHOICES = 8
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


class AskPlacementArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hung: bool = Field(
        default=False,
        description="true when the owner wants the piece hung on the wall; the app then also asks how high",
    )
    # Values the owner already stated (place-piece-from-owner-words); each is kept only when
    # its number is in the owner's latest message, and only the missing ones are asked.
    wall: int | None = Field(default=None, ge=1, description="the wall number, only as the owner wrote it")
    distance_mm: float | None = Field(
        default=None, ge=0, description="the distance the owner wrote, in mm, from the left end or from from_wall"
    )
    from_wall: int | None = Field(
        default=None,
        ge=1,
        description="the wall the owner measured the distance from (\"0 mm from wall 3\"); omit when from the left end",
    )
    gap_mm: float | None = Field(
        default=None, ge=0, description="for a hung piece: how far below the ceiling its top is, as the owner wrote it"
    )


def wall_lengths(corners: list[list[float]]) -> list[float]:
    """Each wall's length in the room contract's order (counter-clockwise corners, wall i
    from corner i to corner i + 1), so the numbers match the fit and the room view."""
    walls = []
    count = len(corners)
    for index in range(count):
        (ax, ay), (bx, by) = corners[index], corners[(index + 1) % count]
        walls.append(math.hypot(bx - ax, by - ay))
    return walls


def offset_from_left(length_mm: float, left_mm: float, width_mm: float) -> float:
    """The offset along the wall (from its start corner) of a piece starting `left_mm` from
    the wall's left end seen from inside the room. Corners run counter-clockwise, so the
    wall's end corner is on the left of someone facing it."""
    return length_mm - left_mm - width_mm


def _setting(ctx: ToolContext) -> tuple[str, list[float], int, float, bool] | str:
    """`(room name, wall lengths, version, piece width, marked wall-mounted)` or a plain refusal."""
    if ctx.thread_id is None or not ctx.package_id:
        return "This conversation has no piece to place yet."
    with ctx.deps.session() as session:
        room, _apartment = house_file.thread_scope(session, ctx.thread_id)
        room_name = room.name if room is not None else None
        plan = _room_for_fit(session, ctx.deps.render_root, room_name) if room_name else None
    if room_name is None or plan is None:
        return "This conversation has no room yet; ask the owner which room the piece is for."
    try:
        normalised, _openings = normalise_room_shell({"corners": plan.corners_mm, "height_mm": plan.height_mm})
    except SpecValidationError:
        return f"The outline of {room_name} cannot be read; Intake can measure the room again."
    folder, number, problem = version_folder(ctx.deps, ctx.package_id, None)
    if folder is None or number is None:
        return problem
    stored = read_input(folder)
    if stored is None:
        return f"Version {number} of the piece cannot be read."
    modules = stored.get("modules") or []
    wall_mounted = bool(modules) and all(module.get("mounting") == "wall" for module in modules)
    return room_name, wall_lengths(normalised["corners"]), number, float(custom_derive.overall(stored)["w"]), wall_mounted


def _hung(args: AskPlacementArgs, ctx: ToolContext, wall_mounted: bool) -> AskPlacementArgs:
    """`hung` as the owner's words or the piece decide it: a piece marked wall-mounted is hung,
    and otherwise the model's `hung` is kept only when the owner's latest message says so."""
    return args.model_copy(update={"hung": wall_mounted or (args.hung and bool(HANG.search(ctx.last_message)))})


def _numbers(text: str) -> set[float]:
    return {float(found.replace(",", ".")) for found in _NUMBER.findall(text)}


def _stated(
    args: AskPlacementArgs, ctx: ToolContext, walls: list[float], width: float
) -> tuple[int | None, float | None, float | None, str]:
    """The wall, the distance from its left end and the ceiling gap the owner already wrote,
    each `None` when it is missing or its number is not in the owner's latest message, and a
    plain note when a distance was measured from a wall that does not touch the chosen one."""
    written = _numbers(ctx.last_message)
    wall = args.wall if args.wall is not None and args.wall in written and args.wall <= len(walls) else None
    left = args.distance_mm if args.distance_mm is not None and args.distance_mm in written else None
    note = ""
    if left is not None and args.from_wall is not None:
        after, before = (wall % len(walls)) + 1 if wall else None, ((wall - 2) % len(walls)) + 1 if wall else None
        if wall is None or args.from_wall not in written or args.from_wall == wall:
            left = None
        elif args.from_wall == after:
            pass  # the next wall meets this one at its left end
        elif args.from_wall == before:
            left = walls[wall - 1] - left - width
        else:
            note = f"The distance has to be measured from a wall next to wall {wall} (wall {after} or wall {before})."
            left = None
    gap = args.gap_mm if args.hung and args.gap_mm is not None and args.gap_mm in written else None
    return wall, left, gap, note


def _missing(args: AskPlacementArgs, wall: int | None, left: float | None, gap: float | None) -> list[str]:
    """Which questions are still to ask, in the order they are shown."""
    keys = []
    if wall is None:
        keys.append("wall")
    if left is None:
        keys.append("distance")
    if args.hung and gap is None:
        keys.append("gap")
    return keys


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Questions | str | None:
    args, problem = parse_args(AskPlacementArgs, arguments)
    if problem or args is None:
        return problem
    setting = _setting(ctx)
    if isinstance(setting, str):
        return setting
    _room, walls, _version, width, wall_mounted = setting
    args = _hung(args, ctx, wall_mounted)
    wall, left, gap, note = _stated(args, ctx, walls, width)
    missing = _missing(args, wall, left, gap)
    if not missing:
        return None
    choices = [f"Wall {n} ({length:.0f} mm)" for n, length in enumerate(walls, start=1)][:MAX_WALL_CHOICES]
    distance = f"{note} {DISTANCE_QUESTION}" if note else DISTANCE_QUESTION
    asked = {
        "wall": {"text": WALL_QUESTION, "unit": None, "choices": choices},
        "distance": {"text": distance, "unit": "mm", "choices": []},
        "gap": {"text": GAP_QUESTION, "unit": "mm", "choices": []},
    }
    return Questions(questions=[asked[key] for key in missing], layout="room")


def _number(text: str) -> float | None:
    found = _NUMBER.search(text)
    return float(found.group(0).replace(",", ".")) if found else None


def run(arguments: dict[str, Any], ctx: ToolContext) -> str | ToolOutput:
    args, problem = parse_args(AskPlacementArgs, arguments)
    if problem or args is None:
        return problem
    answer = ctx.answer or {}
    declined = answer.get("declined")
    if isinstance(declined, str) and declined.strip():
        return (
            "The owner did not answer where to place the piece and wrote instead: "
            f'"{neutralise(declined.strip())}". Continue from what they wrote.'
        )
    setting = _setting(ctx)
    if isinstance(setting, str):
        return setting
    room_name, walls, version, width, wall_mounted = setting
    args = _hung(args, ctx, wall_mounted)
    stated_wall, left, gap, _note = _stated(args, ctx, walls, width)
    # The answers come in the order the missing questions were shown.
    given = dict(zip(_missing(args, stated_wall, left, gap), (str(v) for v in (answer.get("answers") or []))))
    wall_number = float(stated_wall) if stated_wall is not None else _number(given.get("wall", ""))
    if wall_number is None or not wall_number.is_integer() or not 1 <= wall_number <= len(walls):
        return f"The wall could not be read; {room_name} has walls 1 to {len(walls)}. Call ask_placement again."
    if left is None:
        left = _number(given.get("distance", ""))
    if left is None:
        return "The distance from the left end could not be read. Call ask_placement again."
    if args.hung and gap is None:
        gap = _number(given.get("gap", ""))
        if gap is None:
            return "The distance below the ceiling could not be read. Call ask_placement again with hung true."
    wall = int(wall_number)
    length = walls[wall - 1]
    if left < 0:
        return (
            f"It does not fit there: the piece is {-left:.0f} mm too wide for wall {wall} ({length:.0f} mm) at "
            "that distance from the wall's right end. Tell the owner and call ask_placement again."
        )
    if left + width > length:
        return (
            f"It does not fit there: the piece is {left + width - length:.0f} mm too wide for wall {wall} "
            f"({length:.0f} mm) when it starts {left:g} mm from the left end. Tell the owner and call "
            "ask_placement again."
        )
    result = fit(
        ctx, room_name, ctx.package_id or "", version, wall - 1,
        offset_from_left(length, left, width), left_mm=left, ceiling_gap_mm=gap,
    )
    if isinstance(result, str):
        return (
            f"It does not fit on wall {wall} at {left:g} mm from the left end: {result}. Tell the owner in "
            "plain words, numbering walls from 1, and call ask_placement again."
        )
    note = f" Design-rule warnings: {result.warnings}." if result.warnings else ""
    hung = (
        f", hung with its top {gap:g} mm below the ceiling and its underside at {result.mount_height_mm:g} mm"
        if result.mount_height_mm is not None else ""
    )
    return ToolOutput(
        f"Placement saved for {room_name}: wall {wall}, {left:g} mm from the left end{hung}.{note} "
        "Now call compose_room with with_saved_place true to propose the room with the piece in it.",
        update={"placement_ready": True},
    )


ask_placement = AgentTool(
    name="ask_placement",
    description=(
        "Ask the owner where the conversation's piece goes in the conversation's room: the "
        "questions (which wall, how far from its left end) are written by the app. Pass the values "
        "the owner's latest message already states (wall, distance_mm and, for \"N mm from wall M\", "
        "from_wall M): those are not asked again. The answers are checked against the room and a "
        "place that fits is saved for the room. Pass hung true for a piece hung on the wall: the "
        "app then also asks how far below the ceiling its top is (gap_mm when stated)."
    ),
    schema=AskPlacementArgs,
    run=run,
    preview=preview,
)
