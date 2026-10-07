"""`record_brief` (Intake): the owner's confirmed numbers into the house file.

Gated: the owner is shown the room, the piece's purpose, heights, style and
budget, and answers yes or no. Only `yes` writes the room, the preferences and
the thread's brief; nothing else writes rooms or style (agent-loop design).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
from app.blender.shell_contract import polygon_area_m2


class OpeningArg(BaseModel):
    wall: int = Field(description="wall index, counted from 0 along the corners")
    type: Literal["door", "window"]
    offset_mm: float
    width_mm: float
    height_mm: float
    sill_mm: float = 0


class RecordBriefArgs(BaseModel):
    room_name: str | None = Field(
        default=None,
        description="the room's name, e.g. 'Hall'; leave out when the owner has not named a room",
    )
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
    """The room to store (or `None` to keep the stored one, or none), or a refusal."""
    name = (args.room_name or "").strip()
    if not name:
        given = (
            args.corners_mm is not None
            or args.ceiling_height_mm is not None
            or args.openings is not None
            or args.wall_thickness_mm is not None
        )
        if given:
            return None, "a room needs a name; ask the owner what the room is called"
        return None, ""
    with ctx.deps.session() as session:
        stored = house_file.room_by_name(session, name)
        if args.corners_mm is None and args.ceiling_height_mm is None and args.openings is None:
            if stored is None:
                return None, (
                    f"the room {name!r} is not in the house file; give its corner points "
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
                house_file.validate_room(name, corners, height, openings, thickness),
                "",
            )
        except HouseFileError as error:
            return None, f"the room cannot be stored: {error}"


def _brief(args: RecordBriefArgs) -> dict[str, Any]:
    brief = {
        "room": (args.room_name or "").strip() or None,
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


def preview_brief(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
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
    elif (args.room_name or "").strip():
        lines.append(f"Room {args.room_name.strip()}: as already in the house file")
    else:
        lines.append("Room: not given yet")
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


def run_brief(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
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
        "Propose the owner's confirmed numbers: what the piece is for, heights, style and budget, "
        "and the room when the owner gives one (its name, and its corner points and ceiling "
        "height if it is not in the house file yet); a brief without a room is complete. The owner is shown a summary and answers yes or no; nothing is saved "
        "before yes. Use only figures the owner gave."
    ),
    schema=RecordBriefArgs,
    run=run_brief,
    preview=preview_brief,
)




class PlanRoom(BaseModel):
    name: str
    corners_mm: list[list[float]] = Field(
        description="the room's interior outline as [x, y] corners in mm, in the plan's one frame"
    )
    ceiling_height_mm: float | None = Field(default=None, description="only when it differs from the apartment's")
    openings: list[OpeningArg] | None = None
    printed_area_m2: float | None = Field(default=None, description="the area the plan prints for this room, if any")


class RecordPlanArgs(BaseModel):
    apartment_name: str
    ceiling_height_mm: float = Field(description="the ceiling height read from the plan or stated by the owner")
    wall_thickness_mm: float | None = None
    rooms: list[PlanRoom] = Field(min_length=1)
    scale_note: str = Field(description="how the scale was read (a dimension line, a printed area, a known door width)")
    assumptions: list[str] = Field(default_factory=list, description="every figure that was assumed, not read")


def _room_dicts(args: RecordPlanArgs) -> list[dict[str, Any]]:
    return [
        {
            "name": room.name,
            "corners_mm": room.corners_mm,
            "height_mm": room.ceiling_height_mm,
            "openings": [o.model_dump() for o in room.openings] if room.openings is not None else [],
        }
        for room in args.rooms
    ]


def _validated(args: RecordPlanArgs, ctx: ToolContext):
    """The normalised apartment, or a refusal that names the room or the overlap."""
    rooms = _room_dicts(args)
    printed = {r.name.strip(): r.printed_area_m2 for r in args.rooms if r.printed_area_m2}
    try:
        context = house_file.validate_apartment(
            args.apartment_name, args.ceiling_height_mm, args.wall_thickness_mm, rooms, printed
        )
        # The same check against rooms already stored in this apartment; nothing is kept.
        with Session(ctx.deps.engine) as session:
            house_file.upsert_apartment(
                session, args.apartment_name, args.ceiling_height_mm, args.wall_thickness_mm, rooms
            )
            session.rollback()
    except HouseFileError as error:
        return None, f"the plan cannot be stored: {error}"
    return context, ""


def preview_plan(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    args, problem = parse_args(RecordPlanArgs, arguments)
    if args is None:
        return problem
    context, refusal = _validated(args, ctx)
    if refusal:
        return refusal
    shared = sum(1 for w in context.walls if w.shared)
    headline = (
        f"Apartment {context.name}: ceiling {context.ceiling_height_mm:g} mm, "
        f"walls {context.wall_thickness_mm:g} mm, {len(context.rooms)} room(s), {shared} shared wall(s)"
    )
    lines = [headline]
    for room in context.rooms:
        xs = [c[0] for c in room.corners]
        ys = [c[1] for c in room.corners]
        lines.append(
            f"- {room.name}: {max(xs) - min(xs):g} × {max(ys) - min(ys):g} mm, "
            f"{polygon_area_m2(room.corners):.2f} m², {len(room.openings)} opening(s)"
        )
    lines.append(f"Scale: {args.scale_note}")
    for assumption in args.assumptions:
        lines.append(f"Assumed: {assumption}")
    for warning in context.warnings:
        lines.append(f"Check: {warning}")
    return Confirmation(
        subject="plan",
        summary="\n".join(lines),
        proposal={
            "apartment": context.name,
            "ceiling_height_mm": context.ceiling_height_mm,
            "wall_thickness_mm": context.wall_thickness_mm,
            "rooms": [
                {"name": r.name, "area_m2": round(polygon_area_m2(r.corners), 2), "openings": len(r.openings)}
                for r in context.rooms
            ],
            "scale_note": args.scale_note,
            "assumptions": args.assumptions,
            "warnings": list(context.warnings),
        },
    )


def run_plan(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    args, problem = parse_args(RecordPlanArgs, arguments)
    if args is None:
        return problem
    _context, refusal = _validated(args, ctx)
    if refusal:
        return refusal
    with ctx.deps.session() as session:
        house_file.upsert_apartment(
            session,
            args.apartment_name,
            args.ceiling_height_mm,
            args.wall_thickness_mm,
            _room_dicts(args),
            notes="; ".join(args.assumptions),
        )
        session.commit()
    return ToolOutput(
        text=f"The plan is saved: apartment {args.apartment_name.strip()} with {len(args.rooms)} room(s)."
    )


record_plan = AgentTool(
    name="record_plan",
    description=(
        "Propose a whole apartment read from a blueprint: its name, ceiling height, and every room's "
        "outline (in one plan frame, mm) and openings, with how the scale was read and what was "
        "assumed. The owner is shown a summary with each room's area and any plausibility warning and "
        "answers yes or no; nothing is saved before yes. For a single room use record_brief."
    ),
    schema=RecordPlanArgs,
    run=run_plan,
    preview=preview_plan,
)
