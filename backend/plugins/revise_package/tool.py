"""`revise_package` (Designer): the next version of a piece from stated changes.

Gated. The changes are applied to a copy of the latest version's document,
validated and previewed as change lines; on yes the next version is recorded as
revised from the latest and built. The earlier version is never touched.

`rebuild_piece` (Designer, piece-versions-and-chat-delete): the next version with
the latest version's design unchanged, so a build picks up what the generator now
makes. Its own tool and card, so an empty revision still cannot create a version.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.agent import house_file
from app.agent.revise import ReviseError, revise_spec
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    extension_refusal,
    parse_args,
    record_unknown_fields,
    unknown_fields,
)
from app.agent.tools.shared import (
    NOT_APPROVED,
    builds_unavailable,
    checked_package_id,
    latest_version,
    read_input,
    validated_custom_build,
)
from app.blender import storage
from app.blender.schemas import PackageChanges, describe_validation_error
from app.db.models import Piece
from app.guidelines.rules import piece_outcome
from app.packages import service


class ReviseArgs(BaseModel):
    """What the tool parses: the changes are checked by the tool itself, so an
    unknown field can be refused by name and recorded."""

    package_id: str
    changes: dict[str, Any]


class RevisePackageSchema(BaseModel):
    """What the model is shown."""

    package_id: str = Field(description="the piece's package id")
    changes: PackageChanges = Field(
        description="only what changes; name each module by its id"
    )


def _revised(
    arguments: dict[str, Any], ctx: ToolContext
) -> tuple[str | None, int | None, dict[str, Any] | None, list[str], str]:
    args, problem = parse_args(ReviseArgs, arguments)
    if args is None:
        return None, None, None, [], problem
    package_id, problem = checked_package_id(args.package_id)
    if package_id is None:
        return None, None, None, [], problem
    latest = latest_version(ctx.deps, package_id)
    if latest is None:
        return None, None, None, [], f"there is no piece {package_id!r}"
    document = read_input(storage.version_dir(ctx.deps.render_root, package_id, latest))
    if document is None:
        return None, None, None, [], f"version {latest} of {package_id!r} has no readable document"
    try:
        changes = PackageChanges.model_validate(args.changes)
    except ValidationError as error:
        message = describe_validation_error(error)
        fields = unknown_fields(error)
        if fields:
            record_unknown_fields(ctx, fields, package_id)
            return None, None, None, [], extension_refusal(message, fields)
        return None, None, None, [], f"invalid changes: {message}"
    try:
        revised, lines = revise_spec(document, changes)
    except ReviseError as error:
        return None, None, None, [], str(error)
    spec, problem = validated_custom_build(ctx, revised, package_id)
    if spec is None:
        return None, None, None, [], problem
    return package_id, latest, spec, lines, ""


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    package_id, latest, spec, lines, problem = _revised(arguments, ctx)
    if package_id is None or spec is None or latest is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, warnings = piece_outcome(ctx.deps.design_rules, spec)
    if refusal:
        return refusal
    summary = f"Revise {package_id} (from version {latest}):\n" + "\n".join(lines)
    if warnings:
        summary += f"\nDesign-rule warnings: {warnings}"
    return Confirmation(
        subject="revise",
        summary=summary,
        proposal={"package_id": package_id, "revised_from": latest, "changes": lines},
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    package_id, latest, spec, lines, problem = _revised(arguments, ctx)
    if package_id is None or spec is None or latest is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, _warnings = piece_outcome(ctx.deps.design_rules, spec)
    if refusal:
        return refusal

    version = record_next(ctx, package_id, latest, spec, lines)
    return ToolOutput(
        text=(
            f"Created {package_id} version {version} (revised from {latest}): "
            + "; ".join(lines)
            + ". The build has started."
        ),
        update={"package_id": package_id},
    )


def record_next(
    ctx: ToolContext, package_id: str, latest: int, spec: dict[str, Any], lines: list[str]
) -> int:
    """Create and record the next version revised from `latest`, bind the thread, start the build."""
    created = service.create_version(
        ctx.deps.render_root,
        package_id,
        spec,
        lambda version: ctx.deps.start_build(package_id, version),
    )
    with ctx.deps.session() as session:
        if session.get(Piece, package_id) is None:
            # A package made directly through the routes: record it now.
            house_file.record_piece(session, package_id, spec["name"])
        house_file.record_version(
            session, package_id, created["version"], revised_from=latest, changes=lines
        )
        if ctx.thread_id is not None:
            house_file.touch_thread(session, ctx.thread_id, package_id=package_id)
        session.commit()
    return created["version"]


class RebuildArgs(BaseModel):
    package_id: str = Field(description="the piece's package id")


def _rebuilt(arguments: dict[str, Any], ctx: ToolContext) -> tuple[tuple[str, int, dict[str, Any]] | None, str]:
    """`(package_id, latest, design)` ready to rebuild, or a refusal."""
    args, problem = parse_args(RebuildArgs, arguments)
    if args is None:
        return None, problem
    package_id, problem = checked_package_id(args.package_id)
    if package_id is None:
        return None, problem
    latest = latest_version(ctx.deps, package_id)
    if latest is None:
        return None, f"there is no piece {package_id!r}"
    document = read_input(storage.version_dir(ctx.deps.render_root, package_id, latest))
    if document is None:
        return None, f"version {latest} of {package_id!r} has no readable document"
    spec, problem = validated_custom_build(ctx, document, package_id)
    if spec is None:
        return None, problem
    refusal, _warnings = piece_outcome(ctx.deps.design_rules, spec)
    if refusal:
        return None, refusal
    return (package_id, latest, spec), ""


def rebuild_preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    checked, problem = _rebuilt(arguments, ctx)
    if checked is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    package_id, latest, _spec = checked
    return Confirmation(
        subject="rebuild",
        summary=(
            f"Rebuild {package_id} as version {latest + 1}, unchanged from version {latest}: "
            "the same design, built again with what the app now makes for every build."
        ),
        proposal={"package_id": package_id, "revised_from": latest, "version": latest + 1},
    )


def rebuild_run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    checked, problem = _rebuilt(arguments, ctx)
    if checked is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    package_id, latest, spec = checked
    line = f"rebuilt unchanged from version {latest}"
    version = record_next(ctx, package_id, latest, spec, [line])
    return ToolOutput(
        text=f"Created {package_id} version {version} ({line}). The build has started.",
        update={"package_id": package_id},
    )


revise_package = AgentTool(
    name="revise_package",
    description=(
        "Revise a piece that exists: give its package id and only the changes (name, envelope, "
        "material slots, per-module fields by module id, modules and extra parts to add or "
        "remove, part overrides). The owner is shown the change lines and answers yes or no; "
        "the next version is created only on yes."
    ),
    schema=RevisePackageSchema,
    run=run,
    preview=preview,
)


rebuild_piece = AgentTool(
    name="rebuild_piece",
    description=(
        "Make the next version of a piece with its latest design unchanged, built again — for when the "
        "owner wants a new version without changes (for example to get what the app now adds to every "
        "build). The owner is shown what will be made and answers yes or no; nothing is created before yes."
    ),
    schema=RebuildArgs,
    run=rebuild_run,
    preview=rebuild_preview,
)
