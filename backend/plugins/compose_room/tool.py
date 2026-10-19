"""`compose_room` (Designer): a room composition proposed, confirmed and built (room-composition).

Gated. The composition is checked against the house file (the room or apartment),
each piece version's approval, the model library and every placement rule before
any pause; a refusal returns to the Designer with no pause. The owner's `yes`
writes the next version folder, records it and starts its headless build. Nothing
here renders, and the Designer never writes Blender Python.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app import compositions
from app.agent import house_file
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    parse_args,
    record_unknown_fields,
)
from app.agent.tools.shared import NOT_APPROVED, builds_unavailable, version_folder


class ComposeRoomArgs(BaseModel):
    room: str | None = Field(default=None, description="the house-file room to compose (the usual choice)")
    apartment: str | None = Field(default=None, description="an apartment, only when the owner asks for the whole flat")
    with_saved_place: bool = Field(
        default=False,
        description=(
            "true to propose the conversation's room as it is now with the conversation's piece added at "
            "the place the owner chose (or moved there); pass no items and no room then"
        ),
    )
    items: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "every item, each with a short id and a type: "
            "'piece' {package_id, version} (an approved version only); "
            "'stand-in' {name, width_mm, depth_mm, height_mm, colour '#rrggbb'} for bought furniture; "
            "'model' {model_id, name, and optionally width_mm, depth_mm, height_mm, else the library's size}. "
            "A rug or mat (a stand-in or model at most 30 mm tall) takes layer 'floor' and may then lie under "
            "other furniture and in front of a door. "
            "A pendant lamp or anything else hung from the ceiling takes layer 'ceiling': its height_mm runs from "
            "the ceiling down to its lowest point, cable included, and it may hang over furniture it clears. "
            "A lamp (a stand-in or model, not a rug) may take light {type 'point' for a bulb shining all round or "
            "'spot' for a downlight or reading lamp shining down, lumens 10 to 10000, kelvin 1800 to 6500}: "
            "typically 400 to 800 lm per bulb, 2700 K warm, 4000 K neutral; at most 16 lights in a room. "
            "An LED strip is 'led-strip' {name, length_mm 100 to 10000, lumens_per_m 50 to 3000, kelvin, "
            "mount_height_mm (its height above the floor), facing 'down' (under a shelf or wall cabinet; the default), "
            "'up' (a cove on top of a cabinet) or 'out'}, always with a wall placement {wall, offset_mm}; it may run "
            "behind or under furniture on that wall, but not across a door or window at its height, and it does not "
            "follow a piece that moves, so place it again when you move a piece on that wall. "
            "Any item may take hidden: true, which keeps it in the layout but leaves it out of the build and every "
            "render; to show it again, compose without the flag. "
            "Each has a placement: {wall, offset_mm} with its back on that wall, or "
            "{wall, offset_mm, mount_height_mm} for a piece hung on that wall with its underside at that height "
            "above the floor (keep the height of the piece's saved place), or "
            "{x_mm, y_mm, rotation_deg} for its centre; in an apartment each also names its room. "
            "A room may be composed with no items (the room only); an apartment needs at least one"
        )
    )
    floor: dict[str, Any] | None = Field(
        default=None,
        description=(
            "an optional finish over the whole floor, whatever its shape: {tile_width_mm, tile_length_mm "
            "(20 to 2500; width along plan x, length along plan y), tile_colour and grout_colour '#rrggbb', "
            "grout_width_mm (0 to 20; 0 for butted planks), pattern 'grid' (default) or 'staggered' (planks)}. "
            "For example 600 × 600 mm light grey tiles with 3 mm grout: {tile_width_mm: 600, tile_length_mm: 600, "
            "tile_colour: '#e8e4dc', grout_colour: '#9a958c', grout_width_mm: 3}. It belongs to this version: "
            "restate it on every composition of the room, or it is removed"
        ),
    )


def _saved_place(session, ctx: ToolContext) -> tuple[str, list[dict[str, Any]], dict[str, Any] | None] | str:
    """The conversation's room, its items with the bound piece at its saved place, and its floor;
    or a refusal (place-piece-from-owner-words)."""
    if ctx.thread_id is None or not ctx.package_id:
        return "this conversation has no piece to place"
    room, _apartment = house_file.thread_scope(session, ctx.thread_id)
    if room is None:
        return "this conversation has no room yet; ask the owner which room the piece is for"
    _folder, version, problem = version_folder(ctx.deps, ctx.package_id, None)
    if version is None:
        return problem
    if house_file.approved_version_of(session, ctx.package_id) != version:
        return (
            f"version {version} of the piece is not approved, and a room holds approved versions only. "
            "Call approve_version to ask the owner, then call compose_room with with_saved_place again"
        )
    items, floor = compositions.with_saved_place(session, ctx.deps.render_root, room.name, ctx.package_id, version)
    return room.name, items, floor


def _proposal(arguments: dict[str, Any], ctx: ToolContext) -> tuple[compositions.Proposal | None, str]:
    args, problem = parse_args(ComposeRoomArgs, arguments)
    if args is None:
        return None, problem
    if args.with_saved_place and (args.items is not None or args.room or args.apartment):
        return None, "pass either with_saved_place or a room with its items, not both"
    if not args.with_saved_place and args.items is None:
        return None, "items is required (an empty list composes the room alone)"
    settings = ctx.deps.settings
    try:
        with ctx.deps.session() as session:
            room, items, floor = args.room, args.items or [], args.floor
            if args.with_saved_place:
                saved = _saved_place(session, ctx)
                if isinstance(saved, str):
                    return None, saved
                room, items, floor = saved
            return compositions.propose(
                session, render_root=settings.render_root, room=room, apartment=args.apartment,
                items=items, max_items=settings.composition_max_items, rules=ctx.deps.design_rules,
                floor=floor, lighting=ctx.deps.lighting,
            ), ""
    except compositions.CompositionRefused as refused:
        if refused.unknown_field:
            record_unknown_fields(ctx, [refused.unknown_field], None)
            return None, (
                f"{refused.reason}. The composition schema does not define {refused.unknown_field}, so this "
                "cannot be expressed yet; the request has been recorded for the workshop. Tell the owner plainly."
            )
        return None, refused.reason


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    proposal, problem = _proposal(arguments, ctx)
    if proposal is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    return Confirmation(
        subject="compose_room",
        summary=proposal.summary,
        proposal={
            "scope": proposal.scope, "name": proposal.name, "items": len(proposal.document["items"]),
            "revised_from": proposal.latest, "changes": proposal.changes,
        },
        table=proposal.table,
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    proposal, problem = _proposal(arguments, ctx)
    if proposal is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    with ctx.deps.session() as session:
        version = compositions.create_version(
            session, ctx.deps.render_root, proposal,
            lambda slug, number: ctx.deps.start_build(slug, number, "room"),
        )
    return ToolOutput(
        text=(
            f"Created {proposal.name} version {version}; its build has started. The Builder can render it "
            "once it is built, and its status shows on the Rooms page."
        )
    )


compose_room = AgentTool(
    name="compose_room",
    description=(
        "Propose a room (or, when asked, a whole apartment) holding approved pieces, stand-ins for bought "
        "furniture and models from the owner's library, each placed against a wall or at a point. The app "
        "checks every placement and shows the owner a summary; nothing is created before yes. Never write "
        "Blender code."
    ),
    schema=ComposeRoomArgs,
    run=run,
    preview=preview,
)
