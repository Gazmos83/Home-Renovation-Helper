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
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    parse_args,
    record_unknown_fields,
)
from app.agent.tools.shared import NOT_APPROVED, builds_unavailable


class ComposeRoomArgs(BaseModel):
    room: str | None = Field(default=None, description="the house-file room to compose (the usual choice)")
    apartment: str | None = Field(default=None, description="an apartment, only when the owner asks for the whole flat")
    items: list[dict[str, Any]] = Field(
        description=(
            "every item, each with a short id and a type: "
            "'piece' {package_id, version} (an approved version only); "
            "'stand-in' {name, width_mm, depth_mm, height_mm, colour '#rrggbb'} for bought furniture; "
            "'model' {model_id, name, and optionally width_mm, depth_mm, height_mm, else the library's size}. "
            "Each has a placement: {wall, offset_mm} with its back on that wall, or "
            "{x_mm, y_mm, rotation_deg} for its centre; in an apartment each also names its room. "
            "A room may be composed with no items (the room only); an apartment needs at least one"
        )
    )


def _proposal(arguments: dict[str, Any], ctx: ToolContext) -> tuple[compositions.Proposal | None, str]:
    args, problem = parse_args(ComposeRoomArgs, arguments)
    if args is None:
        return None, problem
    settings = ctx.deps.settings
    try:
        with ctx.deps.session() as session:
            return compositions.propose(
                session, render_root=settings.render_root, room=args.room, apartment=args.apartment,
                items=args.items, max_items=settings.composition_max_items, rules=ctx.deps.design_rules,
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
