"""`record_brief` (Intake): the owner's confirmed numbers into the house file.

Gated: the owner is shown the room, the piece's purpose, heights, style and
budget, and answers yes or no. Only `yes` writes the room, the preferences and
the thread's brief; nothing else writes rooms or style (agent-loop design).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent import house_file
from app.agent.house_file import HouseFileError
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    parse_args,
)
from app.agent.tools.shared import NOT_APPROVED


class OpeningArg(BaseModel):
    wall: int = Field(description="wall index, counted from 0 along the corners")
    type: Literal["door", "window"]
    offset_mm: float
    width_mm: float
    height_mm: float
    sill_mm: float = 0


class RecordBriefArgs(BaseModel):
    room_name: str = Field(description="the room's name, e.g. 'Hall'")
    corners_mm: list[list[float]] | None = Field(
        default=None,
        description="the room outline as [x, y] corners in mm; leave out for a room already in the house file",
    )
    ceiling_height_mm: float | None = Field(
        default=None, description="ceiling height in mm; leave out for a room already in the house file"
    )
    wall_thickness_mm: float | None = None
    openings: list[OpeningArg] | None = None
    purpose: str = Field(description="what the piece is for and where it goes")
    max_piece_height_mm: float | None = None
    style: str | None = None
    budget_eur: float | None = None


def _resolve(args: RecordBriefArgs, ctx: ToolContext) -> tuple[dict[str, Any] | None, str]:
    """The room to store (or `None` to keep the stored one), or a refusal."""
    with ctx.deps.session() as session:
        stored = house_file.room_by_name(session, args.room_name)
        if args.corners_mm is None and args.ceiling_height_mm is None and args.openings is None:
            if stored is None:
                return None, (
                    f"the room {args.room_name!r} is not in the house file; give its corner points "
                    "and ceiling height"
                )
            return None, ""
        corners = args.corners_mm if args.corners_mm is not None else (stored.corners_mm if stored else None)
        height = args.ceiling_height_mm if args.ceiling_height_mm is not None else (
            stored.height_mm if stored else None
        )
        if corners is None or height is None:
            return None, "a room needs its corner points and its ceiling height; ask the owner for them"
        openings = (
            [o.model_dump() for o in args.openings]
            if args.openings is not None
            else (stored.openings if stored else [])
        )
        thickness = args.wall_thickness_mm or (stored.wall_thickness_mm if stored else None)
        try:
            return (
                house_file.validate_room(args.room_name, corners, height, openings, thickness),
                "",
            )
        except HouseFileError as error:
            return None, f"the room cannot be stored: {error}"


def _brief(args: RecordBriefArgs) -> dict[str, Any]:
    brief = {
        "room": args.room_name.strip(),
        "purpose": args.purpose,
        "max_piece_height_mm": args.max_piece_height_mm,
        "style": args.style,
        "budget_eur": args.budget_eur,
    }
    return {key: value for key, value in brief.items() if value is not None}


def _size(corners: list[list[float]]) -> str:
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return f"{max(xs) - min(xs):g} × {max(ys) - min(ys):g} mm"


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    args, problem = parse_args(RecordBriefArgs, arguments)
    if args is None:
        return problem
    room, refusal = _resolve(args, ctx)
    if refusal:
        return refusal
    lines = []
    if room is not None:
        lines.append(
            f"Room {room['name']}: {_size(room['corners_mm'])}, ceiling {room['height_mm']:g} mm, "
            f"{len(room['openings'])} opening(s)"
        )
    else:
        lines.append(f"Room {args.room_name.strip()}: as already in the house file")
    lines.append(f"Piece: {args.purpose}")
    if args.max_piece_height_mm is not None:
        lines.append(f"Highest the piece may be: {args.max_piece_height_mm:g} mm")
    if args.style:
        lines.append(f"Style: {args.style}")
    if args.budget_eur is not None:
        lines.append(f"Budget: {args.budget_eur:g} EUR")
    return Confirmation(
        subject="brief",
        summary="\n".join(lines),
        proposal={"room": room, "brief": _brief(args)},
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    args, problem = parse_args(RecordBriefArgs, arguments)
    if args is None:
        return problem
    room, refusal = _resolve(args, ctx)
    if refusal:
        return refusal
    with ctx.deps.session() as session:
        if room is not None:
            house_file.upsert_room(
                session,
                room["name"],
                room["corners_mm"],
                room["height_mm"],
                room["openings"],
                room["wall_thickness_mm"],
            )
        if args.style:
            house_file.set_preference(session, "style", args.style)
        if args.budget_eur is not None:
            house_file.set_preference(session, "budget_eur", f"{args.budget_eur:g}")
        session.commit()
    brief = _brief(args)
    return ToolOutput(
        text="The brief is confirmed and saved. The next step is designing the piece.",
        update={"brief": brief},
    )


record_brief = AgentTool(
    name="record_brief",
    description=(
        "Propose the owner's confirmed numbers: the room (its name, and its corner points and "
        "ceiling height if it is not in the house file yet), what the piece is for, heights, "
        "style and budget. The owner is shown a summary and answers yes or no; nothing is saved "
        "before yes. Use only figures the owner gave."
    ),
    schema=RecordBriefArgs,
    run=run,
    preview=preview,
)
