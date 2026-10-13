"""`read_room_version_dimensions` (Designer, Researcher): inspector figures for a version.

Read-only. The conversation's confirmed room (or apartment) comes from the thread;
the model may name only a version. Naming another room is refused. Nothing is written.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app import compositions
from app.agent import house_file
from app.agent.tools.base import AgentTool, ToolContext, parse_args


class ReadRoomVersionDimensionsArgs(BaseModel):
    version: int = Field(ge=1, description="the composition version whose wall lengths and ceiling heights to read")
    room: str | None = Field(
        default=None,
        description=(
            "optional; must be this conversation's confirmed room (or its apartment). "
            "A different room is refused; omit to use the confirmed scope"
        ),
    )


def _format(found: dict[str, Any], *, name: str) -> str:
    approval = "approved" if found["approved"] else "not approved"
    walls = ", ".join(f"{wall['label']}: {wall['length_mm']} mm" for wall in found["walls"])
    ceilings = found["ceilings"]
    if len(ceilings) == 1:
        height = f"ceiling {ceilings[0]['height_mm']} mm"
    else:
        height = ", ".join(f"{item['room']} ceiling: {item['height_mm']} mm" for item in ceilings)
    return (
        f"{name} composition version {found['version']} ({approval}): {walls}; {height}. "
        "These are the same figures the inspector's dimensions switch shows."
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(ReadRoomVersionDimensionsArgs, arguments)
    if args is None:
        return problem
    if ctx.thread_id is None:
        return "there is no conversation to read a room version for"
    named = (args.room or "").strip() or None
    with ctx.deps.session() as session:
        confirmed_room, apartment = house_file.thread_scope(session, ctx.thread_id)
        if confirmed_room is None and apartment is None:
            return "this conversation has no confirmed room; confirm a room before reading its dimensions"
        if apartment is not None:
            room_names = {r.name for r in house_file.rooms_of(session, apartment)}
            if named is not None and named != apartment.name and named not in room_names:
                return (
                    f"{named!r} is not this conversation's confirmed apartment "
                    f"({apartment.name}); only that apartment's dimensions can be read here"
                )
            found = compositions.dimensions_of_scope(
                session,
                ctx.deps.render_root,
                scope="apartment",
                name=apartment.name,
                version=args.version,
            )
            if found is None:
                return (
                    f"apartment {apartment.name!r} has no composition version {args.version}, "
                    "or that version has no room plan"
                )
            return _format(found, name=apartment.name)
        assert confirmed_room is not None
        if named is not None and named != confirmed_room.name:
            return (
                f"{named!r} is not this conversation's confirmed room "
                f"({confirmed_room.name}); only that room's dimensions can be read here"
            )
        found = compositions.dimensions_of_scope(
            session,
            ctx.deps.render_root,
            scope="room",
            name=confirmed_room.name,
            version=args.version,
        )
        if found is None:
            return (
                f"room {confirmed_room.name!r} has no composition version {args.version}, "
                "or that version has no room plan"
            )
        return _format(found, name=confirmed_room.name)


read_room_version_dimensions = AgentTool(
    name="read_room_version_dimensions",
    description=(
        "Read the wall lengths and ceiling heights of a composition version of this "
        "conversation's confirmed room (the same figures the inspector shows). "
        "Pass only the version number; the room comes from the conversation. "
        "Read-only; never changes a dimension."
    ),
    schema=ReadRoomVersionDimensionsArgs,
    run=run,
)
