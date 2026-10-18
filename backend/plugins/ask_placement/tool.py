"""`ask_placement` (Designer): where the bound piece goes in the conversation's room (view-piece-in-room).

The questions are written here, never by the model: which wall (each with its length) and
how far from the wall's left end, seen facing it. The answers are turned into the wall
index and offset the room fit takes, the fit runs, and a placement that fits is stored with
the version, so the Builder renders it in the room with no document passed between tools.
"""

from __future__ import annotations

import math
import re
from typing import Any

from pydantic import BaseModel, ConfigDict

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
from plugins.room_fit.tool import _room_for_fit, fit

WALL_QUESTION = "Where would you like to place the piece? Check out the Room layout."
DISTANCE_QUESTION = "How far from the left end of that wall should the piece start? (seen facing the wall)"
MAX_WALL_CHOICES = 8
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


class AskPlacementArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


def _setting(ctx: ToolContext) -> tuple[str, list[float], int, float] | str:
    """`(room name, wall lengths, version, piece width)` or a plain refusal."""
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
    return room_name, wall_lengths(normalised["corners"]), number, float(custom_derive.overall(stored)["w"])


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Questions | str:
    _args, problem = parse_args(AskPlacementArgs, arguments)
    if problem:
        return problem
    setting = _setting(ctx)
    if isinstance(setting, str):
        return setting
    _room, walls, _version, _width = setting
    choices = [f"Wall {n} ({length:.0f} mm)" for n, length in enumerate(walls, start=1)][:MAX_WALL_CHOICES]
    return Questions(
        questions=[
            {"text": WALL_QUESTION, "unit": None, "choices": choices},
            {"text": DISTANCE_QUESTION, "unit": "mm", "choices": []},
        ],
        layout="room",
    )


def _number(text: str) -> float | None:
    found = _NUMBER.search(text)
    return float(found.group(0).replace(",", ".")) if found else None


def run(arguments: dict[str, Any], ctx: ToolContext) -> str | ToolOutput:
    _args, problem = parse_args(AskPlacementArgs, arguments)
    if problem:
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
    room_name, walls, version, width = setting
    given = [str(value) for value in (answer.get("answers") or [])]
    wall_number = _number(given[0]) if given else None
    left = _number(given[1]) if len(given) > 1 else None
    if wall_number is None or not wall_number.is_integer() or not 1 <= wall_number <= len(walls):
        return f"The wall could not be read; {room_name} has walls 1 to {len(walls)}. Call ask_placement again."
    if left is None:
        return "The distance from the left end could not be read. Call ask_placement again."
    wall = int(wall_number)
    length = walls[wall - 1]
    if left + width > length:
        return (
            f"It does not fit there: the piece is {left + width - length:.0f} mm too wide for wall {wall} "
            f"({length:.0f} mm) when it starts {left:g} mm from the left end. Tell the owner and call "
            "ask_placement again."
        )
    result = fit(
        ctx, room_name, ctx.package_id or "", version, wall - 1,
        offset_from_left(length, left, width), left_mm=left,
    )
    if isinstance(result, str):
        return (
            f"It does not fit on wall {wall} at {left:g} mm from the left end: {result}. Tell the owner in "
            "plain words, numbering walls from 1, and call ask_placement again."
        )
    note = f" Design-rule warnings: {result.warnings}." if result.warnings else ""
    return ToolOutput(
        f"Placement saved for {room_name}: wall {wall}, {left:g} mm from the left end.{note}",
        update={"placement_saved": True},
    )


ask_placement = AgentTool(
    name="ask_placement",
    description=(
        "Ask the owner where the conversation's piece goes in the conversation's room: the "
        "questions (which wall, how far from its left end) are written by the app. The answers "
        "are checked against the room and a place that fits is saved for a render in the room. "
        "Takes no arguments."
    ),
    schema=AskPlacementArgs,
    run=run,
    preview=preview,
)
