"""`revise_package` (Designer): the next version of a piece from stated changes.

Gated. The changes are applied to a copy of the latest version's document,
validated and previewed as change lines; on yes the next version is recorded as
revised from the latest and built. The earlier version is never touched.

`rebuild_piece` (Designer, piece-versions-and-chat-delete): the next version with
the latest version's design unchanged, so a build picks up what the generator now
makes. Its own tool and card, so an empty revision still cannot create a version.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.agent import decisions_note, house_file, measurements, notices
from app.agent.divider_questions import fix_shelf_question, position_question
from app.agent.revise import ReviseError, derived_changes, fit_decision, revise_spec
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
    latest_version,
    read_input,
    refuse_other_piece,
    validated_custom_build,
    version_limit_line,
    version_limit_refusal,
    visible_package_id,
)
from app.blender import storage
from app.blender.custom_build.derive import (
    DeriveError,
    check_adjustable_shelf_depths,
    slat_handle_warnings,
)
from app.blender.schemas import PackageChanges, describe_validation_error
from app.db.models import Piece
from app.guidelines.hardware_inputs import freeze_inputs
from app.guidelines.rules import piece_outcome
from app.packages import service

logger = logging.getLogger(__name__)


class RequestedMeasure(BaseModel):
    """One length the owner asked for, tied to the field it sets."""

    quote: str = Field(description="the owner's own words giving the length, e.g. '80 cm wide' or '5 cm wider'")
    target: str = Field(
        description="the module id, 'envelope', a wall shelf id, or 'none' for a length not about the piece"
    )
    field: str = Field(
        description="the field the length sets, e.g. width, height, depth, length, side_folds; empty for 'none'"
    )
    value_mm: float = Field(description="the field's new value in mm; a relative length is added to the latest version's value")


class ReviseArgs(BaseModel):
    """What the tool parses: the changes are checked by the tool itself, so an
    unknown field can be refused by name and recorded. A missing `requested` is an
    empty list, which the measurement check refuses whenever the owner gave a length."""

    package_id: str
    changes: dict[str, Any]
    requested: list[RequestedMeasure] = Field(default_factory=list)


class RevisePackageSchema(BaseModel):
    """What the model is shown."""

    package_id: str = Field(description="the piece's package id")
    changes: PackageChanges = Field(
        description="only what changes; name each module by its id"
    )
    requested: list[RequestedMeasure] = Field(
        description=(
            "every length with a unit (mm, cm, m) the owner wrote since the piece's last version, one entry "
            "each, and one entry with field `side_folds` (value_mm 0 when it gives no length) for each side "
            "fold the owner asked to set, change or clear; an empty list only when the owner gave none"
        )
    )


def _revised(
    arguments: dict[str, Any], ctx: ToolContext
) -> tuple[str | None, int | None, dict[str, Any] | None, list[str], str]:
    package_id, latest, spec, lines, _effects, problem = _revised_with_effects(arguments, ctx)
    return package_id, latest, spec, lines, problem


def _revised_with_effects(
    arguments: dict[str, Any], ctx: ToolContext
) -> tuple[str | None, int | None, dict[str, Any] | None, list[str], list[str], str]:
    """`_revised` plus the cut-list and hardware lines the revision changes."""
    args, problem = parse_args(ReviseArgs, arguments)
    if args is None:
        return None, None, None, [], [], problem
    package_id, problem = visible_package_id(ctx.deps, args.package_id)
    if package_id is None:
        return None, None, None, [], [], problem
    other = refuse_other_piece(ctx, package_id)
    if other:
        return None, None, None, [], [], other
    latest = latest_version(ctx.deps, package_id)
    if latest is None:
        return None, None, None, [], [], f"there is no piece {package_id!r}"
    document = read_input(storage.version_dir(ctx.deps.render_root, package_id, latest))
    if document is None:
        return None, None, None, [], [], f"version {latest} of {package_id!r} has no readable document"
    try:
        changes = PackageChanges.model_validate(args.changes)
    except ValidationError as error:
        message = describe_validation_error(error)
        fields = unknown_fields(error)
        if fields:
            record_unknown_fields(ctx, fields, package_id)
            return None, None, None, [], [], extension_refusal(message, fields)
        return None, None, None, [], [], f"invalid changes: {message}"
    try:
        revised, lines = revise_spec(document, changes)
    except ReviseError as error:
        return None, None, None, [], [], str(error)
    if not lines:
        return None, None, None, [], [], (
            f"nothing would change: every requested value equals version {latest}; "
            "to build the same design again as a new version, use rebuild_piece"
        )
    requested = [measurements.Requested(r.quote, r.target, r.field, r.value_mm) for r in args.requested]
    owner_texts = measurements.owner_texts_since_version(ctx.history, package_id)
    # A side fold changes only when the owner asked for it (auto-fit-protruding-shelves).
    refusals = measurements.fold_refusals(requested, owner_texts, document, revised)
    if refusals:
        return None, None, None, [], [], "the fold change was not asked for: " + "; ".join(refusals)
    # The owner's lengths must land in the changes, checked before any confirmation.
    refusals = measurements.check(requested, owner_texts, document, revised)
    if refusals:
        return None, None, None, [], [], "the requested measurements do not hold: " + "; ".join(refusals)
    question = fix_shelf_question(revised)
    if question:
        return None, None, None, [], [], question
    spec, problem = validated_custom_build(ctx, revised, package_id)
    if spec is None:
        return None, None, None, [], [], problem
    question = position_question(document, spec, ctx.deps.design_rules)
    if question:
        return None, None, None, [], [], question
    with ctx.deps.session() as session:
        pin_inputs = freeze_inputs(session, ctx.deps.design_rules, spec)
    try:
        check_adjustable_shelf_depths(spec, pin_inputs)
    except DeriveError as error:
        return None, None, None, [], [], str(error)
    return package_id, latest, spec, lines, derived_changes(document, spec), ""


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    # Change lines only in the confirmation; cut list / hardware diffs belong in the
    # inspector after the build (revision-confirm-highlight-cuts).
    package_id, latest, spec, lines, _effects, problem = _revised_with_effects(arguments, ctx)
    if package_id is None or spec is None or latest is None:
        return problem
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    limited = version_limit_refusal(ctx.deps, package_id)
    if limited:
        return limited
    refusal, warnings = piece_outcome(ctx.deps.design_rules, spec)
    if refusal:
        return refusal
    summary = f"Revise {package_id} (from version {latest}):\n" + "\n".join(lines)
    if warnings:
        summary += f"\nDesign-rule warnings: {warnings}"
    slat_warnings = slat_handle_warnings(spec)
    if slat_warnings:
        summary += f"\nSlat-handle warnings: {'; '.join(slat_warnings)}"
    heads_up = version_limit_line(ctx.deps, package_id)
    if heads_up:
        summary += f"\n{heads_up}"
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
    limited = version_limit_refusal(ctx.deps, package_id)
    if limited:
        return limited

    version = record_next(ctx, package_id, latest, spec, lines)
    record_fit_decision(ctx, package_id, lines)
    return ToolOutput(
        text=(
            f"Created {package_id} version {version} (revised from {latest}): "
            + "; ".join(lines)
            + ". The build has started."
        ),
        update={"package_id": package_id},
    )


def record_fit_decision(ctx: ToolContext, package_id: str, lines: list[str]) -> None:
    """Append the fit to the conversation's decisions note once the owner has confirmed the revision.

    A row that cannot be written is logged: the version already exists and is not undone.
    """
    row = fit_decision(lines)
    if row is None or ctx.thread_id is None:
        return
    with ctx.deps.session() as session:
        text, _through = house_file.read_summary(session, ctx.thread_id, package_id)
        refusal = decisions_note.store_note(
            session, ctx.thread_id, package_id, decisions_note.append_row(text or "", *row)
        )
        if refusal is not None:
            session.rollback()
            logger.warning("the protruding-shelf fit was not added to the decisions note: %s", refusal)
            return
        session.commit()


def record_next(
    ctx: ToolContext, package_id: str, latest: int, spec: dict[str, Any], lines: list[str]
) -> int:
    """Create and record the next version revised from `latest`, bind the thread, start the build."""
    with ctx.deps.session() as session:
        inputs = freeze_inputs(session, ctx.deps.design_rules, spec)
    # The build starts only once the version is recorded (see below).
    version = service.create_version(ctx.deps.render_root, package_id, spec, lambda _version: None, inputs=inputs)[
        "version"
    ]
    try:
        with ctx.deps.session() as session:
            if session.get(Piece, package_id) is None:
                # A package made directly through the routes: record it now.
                house_file.record_piece(session, package_id, spec["name"])
            house_file.record_version(
                session, package_id, version, revised_from=latest, changes=lines,
                slot=ctx.slot, model=ctx.model,
            )
            if ctx.thread_id is not None:
                house_file.touch_thread(session, ctx.thread_id, package_id=package_id)
            session.commit()
    except Exception:
        # A version with no record could be neither seen nor deleted from the app.
        storage.remove_version(ctx.deps.render_root, package_id, version)
        raise
    # No notice of its own: the build notice is the version's one notice (studio-navigation-tidy).
    notices.follow_build(ctx.deps, ctx.thread_id, ctx.deps.start_build(package_id, version), package_id, version)
    return version


class RebuildArgs(BaseModel):
    package_id: str = Field(description="the piece's package id")


def _rebuilt(arguments: dict[str, Any], ctx: ToolContext) -> tuple[tuple[str, int, dict[str, Any]] | None, str]:
    """`(package_id, latest, design)` ready to rebuild, or a refusal."""
    args, problem = parse_args(RebuildArgs, arguments)
    if args is None:
        return None, problem
    package_id, problem = visible_package_id(ctx.deps, args.package_id)
    if package_id is None:
        return None, problem
    other = refuse_other_piece(ctx, package_id)
    if other:
        return None, other
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
    limited = version_limit_refusal(ctx.deps, package_id)
    if limited:
        return limited
    # Not `latest + 1`: a deleted version's number is never given out again.
    following = storage.next_version(ctx.deps.render_root, package_id)
    summary = (
        f"Rebuild {package_id} as version {following}, unchanged from version {latest}: "
        "the same design, built again with what the app now makes for every build."
    )
    heads_up = version_limit_line(ctx.deps, package_id)
    if heads_up:
        summary += f"\n{heads_up}"
    return Confirmation(
        subject="rebuild",
        summary=summary,
        proposal={"package_id": package_id, "revised_from": latest, "version": following},
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
    limited = version_limit_refusal(ctx.deps, package_id)
    if limited:
        return limited
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
        "material slots, per-module fields by module id including side_folds for a carcass-side "
        "bend, modules and extra parts to add or remove, part overrides). A 26° bend from 1100 mm "
        "on a named module is changes.modules.<id>.side_folds = [{side: left, from_mm: 1100, "
        "along: height, angle_deg: 26, towards: inside}]. The owner is shown the change lines "
        "and answers yes or no; the next version is created only on yes."
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
