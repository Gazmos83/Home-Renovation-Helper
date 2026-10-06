"""`create_piece` (Designer): a validated custom-build document becomes a piece.

Gated. The document is validated against the schema before anything else (an
unknown field is refused by name and recorded as a generator-extension request);
a valid one is previewed and waits for the owner's yes. On yes the piece and
version 1 are recorded and the build starts.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent import house_file
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    parse_args,
)
from app.agent.tools.shared import (
    NOT_APPROVED,
    builds_unavailable,
    checked_package_id,
    validated_custom_build,
)
from app.blender import storage
from app.blender.custom_build import derive as custom_derive
from app.db.models import Piece
from app.guidelines.rules import piece_outcome
from app.packages import service


class CreatePieceArgs(BaseModel):
    package_id: str = Field(
        description="a short id: lowercase letters, digits and hyphens, e.g. 'hall-bench'"
    )
    spec: dict[str, Any] = Field(description="the complete custom_build document")


def _taken(ctx: ToolContext, package_id: str) -> bool:
    if storage.versions(ctx.deps.render_root, package_id):
        return True
    with ctx.deps.session() as session:
        return session.get(Piece, package_id) is not None


def _checked(arguments: dict[str, Any], ctx: ToolContext) -> tuple[str | None, dict[str, Any] | None, str]:
    args, problem = parse_args(CreatePieceArgs, arguments)
    if args is None:
        return None, None, problem
    package_id, problem = checked_package_id(args.package_id)
    if package_id is None:
        return None, None, problem
    if _taken(ctx, package_id):
        return None, None, (
            f"the package id {package_id!r} is already in use; choose another id, "
            "or revise that piece instead"
        )
    spec, problem = validated_custom_build(ctx, args.spec, package_id)
    if spec is None:
        return None, None, problem
    return package_id, spec, ""


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    package_id, spec, problem = _checked(arguments, ctx)
    if package_id is None or spec is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, warnings = piece_outcome(ctx.deps.design_rules, spec)
    if refusal:
        return refusal
    parts, hardware, _assembly = custom_derive.derive(spec)
    overall = custom_derive.overall(spec)
    modules = len(spec["modules"])
    summary = (
        f"New piece {spec['name']!r} as {package_id}: "
        f"{overall['w']} × {overall['h']} × {overall['d']} mm (w × h × d), "
        f"{modules} module(s), {len(parts)} cut-list rows, {len(hardware)} hardware lines"
    )
    if warnings:
        summary += f"\nDesign-rule warnings: {warnings}"
    return Confirmation(
        subject="create_piece",
        summary=summary,
        proposal={
            "package_id": package_id,
            "name": spec["name"],
            "overall": overall,
            "modules": modules,
            "cut_list_rows": len(parts),
            "hardware_lines": len(hardware),
        },
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    package_id, spec, problem = _checked(arguments, ctx)
    if package_id is None or spec is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, _warnings = piece_outcome(ctx.deps.design_rules, spec)
    if refusal:
        return refusal

    created = service.create_version(
        ctx.deps.render_root,
        package_id,
        spec,
        lambda version: ctx.deps.start_build(package_id, version),
    )
    with ctx.deps.session() as session:
        room = house_file.room_by_name(session, str(ctx.brief.get("room") or ""))
        house_file.record_piece(
            session, package_id, spec["name"], brief=dict(ctx.brief), room_id=room.id if room else None
        )
        house_file.record_version(session, package_id, created["version"])
        if ctx.thread_id is not None:
            house_file.touch_thread(session, ctx.thread_id, package_id=package_id)
        session.commit()
    return ToolOutput(
        text=(
            f"Created {package_id} version {created['version']}; the build has started. "
            "It can be built and viewed by the Builder next."
        ),
        update={"package_id": package_id},
    )


create_piece = AgentTool(
    name="create_piece",
    description=(
        "Create a new piece from a complete custom_build document (start from the shipped "
        "template and change only what the brief supports). The owner is shown a summary and "
        "answers yes or no; nothing is created before yes. A field the schema does not define "
        "is refused by name and recorded as a request."
    ),
    schema=CreatePieceArgs,
    run=run,
    preview=preview,
)
