"""`approve_version` (Designer): the conversation's latest built version is approved on the
owner's yes (place-piece-from-owner-words).

Gated. The piece and its version come from the conversation, never from an argument, and the
approval is the piece inspector's own (`app.packages.approval`). A room holds approved versions
only, so this is offered when the owner places an unapproved version in the room.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.agent import house_file
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    parse_args,
)
from app.agent.tools.shared import NOT_APPROVED, version_folder
from app.db.models import Piece
from app.packages import approval


class ApproveVersionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _target(arguments: dict[str, Any], ctx: ToolContext) -> tuple[Any, int, str] | str:
    """`(folder, version, piece name)` of the conversation's latest version, or a refusal."""
    _args, problem = parse_args(ApproveVersionArgs, arguments)
    if problem:
        return problem
    if not ctx.package_id:
        return "This conversation has no piece to approve."
    folder, version, problem = version_folder(ctx.deps, ctx.package_id, None)
    if folder is None or version is None:
        return problem
    with ctx.deps.session() as session:
        piece = session.get(Piece, ctx.package_id)
        row = house_file.version_row(session, ctx.package_id, version)
        if row is not None and row.approved_at is not None:
            return f"Version {version} is already approved."
        return folder, version, piece.name if piece is not None and piece.name else ctx.package_id


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    target = _target(arguments, ctx)
    if isinstance(target, str):
        return target
    _folder, version, name = target
    return Confirmation(
        subject="approve_version",
        summary=f"Approve version {version} of {name}?",
        proposal={"package_id": ctx.package_id, "version": version},
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    target = _target(arguments, ctx)
    if isinstance(target, str):
        return target
    folder, version, name = target
    with ctx.deps.session() as session:
        try:
            approval.approve_built_version(session, folder, ctx.package_id or "", version)
        except approval.ApprovalRefused as error:
            return f"Not approved: {error}."
        session.commit()
    return ToolOutput(f"Version {version} of {name} is approved.")


approve_version = AgentTool(
    name="approve_version",
    description=(
        "Ask the owner to approve the conversation's latest built piece version. A room holds approved "
        "versions only: call this when compose_room says the version is not approved, then compose again."
    ),
    schema=ApproveVersionArgs,
    run=run,
    preview=preview,
)
