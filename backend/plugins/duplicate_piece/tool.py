"""`duplicate_piece` (Designer): a version of an existing piece becomes a new piece (duplicate-piece).

Gated. The copy is checked by `app.packages.duplicate` exactly as the Pieces page checks it,
previewed, and made only on the owner's yes. The design is read from the version folder by
code, never retyped by the model. The conversation the tool ran in keeps its own binding; the
copy gets its own conversation, which the reply names.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent import notices
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    parse_args,
)
from app.agent.tools.shared import NOT_APPROVED, builds_unavailable
from app.blender.custom_build import derive as custom_derive
from app.guidelines.rules import piece_outcome
from app.packages import duplicate


class DuplicatePieceArgs(BaseModel):
    source_package_id: str = Field(description="the id of the piece to copy, e.g. 'sideboard-1200'")
    version: int | None = Field(default=None, description="the version to copy; the latest when omitted")
    name: str = Field(description="the copy's name, as the owner gave it")
    package_id: str | None = Field(
        default=None, description="the copy's id; derived from the name when omitted"
    )


def _checked(arguments: dict[str, Any], ctx: ToolContext) -> tuple[duplicate.Plan | None, str]:
    args, problem = parse_args(DuplicatePieceArgs, arguments)
    if args is None:
        return None, problem
    with ctx.deps.session() as session:
        try:
            return duplicate.plan(
                session, ctx.deps.render_root, args.source_package_id, args.version, args.name, args.package_id
            ), ""
        except duplicate.DuplicateRefused as error:
            return None, str(error)


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    checked, problem = _checked(arguments, ctx)
    if checked is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    overall = custom_derive.overall(checked.spec)
    summary = (
        f"Duplicate {checked.source_id} version {checked.version} as a new piece "
        f"{checked.name!r} ({checked.package_id}): "
        f"{overall['w']} × {overall['h']} × {overall['d']} mm (w × h × d). "
        "It gets its own conversation; the original is not changed."
    )
    _refusal, warnings = piece_outcome(ctx.deps.design_rules, checked.spec)
    if warnings:
        summary += f"\nDesign-rule warnings: {warnings}"
    proposal = {
        "source_package_id": checked.source_id,
        "version": checked.version,
        "name": checked.name,
        "package_id": checked.package_id,
        "overall": overall,
    }
    return Confirmation(subject="duplicate_piece", summary=summary, proposal=proposal)


def run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    checked, problem = _checked(arguments, ctx)
    if checked is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    with ctx.deps.session() as session:
        created = duplicate.create(
            session,
            ctx.deps.render_root,
            checked,
            lambda thread_id, version: notices.follow_build(
                ctx.deps, thread_id, ctx.deps.start_build(checked.package_id, version), checked.package_id, version
            ),
            slot=ctx.slot,
            model=ctx.model,
        )
    return ToolOutput(
        text=(
            f"Duplicated {checked.source_id} version {checked.version} as {checked.name!r} "
            f"({checked.package_id}); its build has started. It has its own conversation: "
            f"/studio/workspace/{created['thread_id']}. This conversation stays about its own piece."
        )
    )


duplicate_piece = AgentTool(
    name="duplicate_piece",
    description=(
        "Make a new piece from one version (the latest by default) of an existing piece, under a "
        "new name the owner gives. The design is copied by code; the owner is shown a summary and "
        "answers yes or no; nothing is created before yes. The copy gets its own conversation."
    ),
    schema=DuplicatePieceArgs,
    run=run,
    preview=preview,
)
