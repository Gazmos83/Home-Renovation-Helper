"""`import_design` (Designer): an attached design file becomes a new piece (design-import).
`import_design_version`: it becomes an existing piece's next version instead
(piece-versions-and-chat-delete).

Gated. The file is read by code from the conversation's own upload, never retyped by
the model; it is parsed as a bare custom-build document or a `package_import`
wrapper and then checked exactly as `create_piece` checks a design. On yes, version 1
is recorded with the change line "imported from <file name>", the conversation is
bound to the piece and the build starts. A refusal that quotes the document is
returned inside the untrusted-content delimiters: the file came from another chat.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agent import house_file, uploads
from app.agent.prompts import Passage, wrap_passage
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
    latest_version,
)
from app.blender.hardware_catalog import default_catalog
from app.blender.import_corrections import correct, rule_lines
from app.design_import import parse_import
from app.guidelines.hardware_inputs import freeze_inputs
from app.guidelines.rules import piece_outcome
from plugins.create_piece.tool import (
    checked_new_id,
    create_and_record,
    piece_room,
    summarise,
)
from plugins.revise_package.tool import record_next


class ImportDesignArgs(BaseModel):
    upload_id: UUID = Field(description="the upload id of the attached design file, as the owner's message names it")
    package_id: str = Field(
        description="a short id for the new piece: lowercase letters, digits and hyphens, e.g. 'wall-unit'"
    )


def _quoted(refusal: str, name: str, upload_id: UUID) -> str:
    passage = Passage(
        content=refusal,
        url=f"upload:{upload_id}",
        scraped_at=datetime.now(UTC).isoformat(),
        title=f"design file {name}",
    )
    return (
        "The design file was refused. The problems below are quoted from checking the file; "
        "give them to the owner to correct in the other chat.\n"
        + wrap_passage(passage, datetime.now(UTC).isoformat())
    )


def _read_upload(upload_id: UUID, ctx: ToolContext) -> tuple[tuple[Any, str, str | None] | None, str]:
    """`(document, file name, the conversation's bound piece)` of this conversation's
    design upload, or a refusal."""
    with ctx.deps.session() as session:
        upload = uploads.get_upload(session, upload_id)
        if upload is None or ctx.thread_id is None or upload.thread_id != ctx.thread_id:
            return None, f"there is no upload {upload_id} in this conversation"
        if upload.kind != "design":
            return None, f"upload {upload_id} is an image, not a design file"
        path = uploads.upload_path(ctx.deps.settings.upload_root, upload.thread_id, upload.id, upload.kind)
        name = upload.original_name
        thread = house_file.get_thread(session, ctx.thread_id)
        bound = thread.package_id if thread else None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, f"the design file {upload_id} can no longer be read; ask the owner to attach it again"
    return (document, name, bound), ""


def _corrected(design: dict[str, Any], ctx: ToolContext) -> tuple[dict[str, Any], list[str]]:
    """The design with its hand-written hardware corrected against the rules in force, and the
    correction lines the preview lists (hardware-catalog)."""
    with ctx.deps.session() as session:
        inputs = freeze_inputs(session, ctx.deps.design_rules, design)
    found = correct(design, rule_lines(design, inputs), default_catalog())
    return found.design, found.lines()


def _with_corrections(summary: str, corrections: list[str]) -> str:
    if not corrections:
        return summary
    return summary + "\nHardware corrections:\n" + "\n".join(f"- {line}" for line in corrections)


def _checked(
    arguments: dict[str, Any], ctx: ToolContext
) -> tuple[tuple[str, dict[str, Any], str, list[str]] | None, str]:
    """`(package_id, corrected design, file name, hardware corrections)` ready to create, or a refusal."""
    args, problem = parse_args(ImportDesignArgs, arguments)
    if args is None:
        return None, problem
    read, problem = _read_upload(args.upload_id, ctx)
    if read is None:
        return None, problem
    document, name, bound = read
    if bound:
        return None, (
            f"this conversation is already about {bound}; the file can be imported as {bound}'s next "
            "version with import_design_version, or as a new piece in a new conversation"
        )
    _room, problem = piece_room(ctx)
    if problem:
        return None, problem
    package_id, problem = checked_new_id(ctx, args.package_id)
    if package_id is None:
        taken, _ = checked_package_id(args.package_id)
        if taken is not None and "already in use" in problem:
            return None, (
                f"the package id {taken!r} is already in use; the file can be imported as "
                f"{taken}'s next version with import_design_version, or choose another id"
            )
        return None, problem
    design, refusal = parse_import(document, ctx, package_id)
    if design is None:
        return None, _quoted(refusal, name, args.upload_id)
    design, corrections = _corrected(design, ctx)
    return (package_id, design, name, corrections), ""


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    checked, problem = _checked(arguments, ctx)
    if checked is None:
        return problem
    package_id, design, name, corrections = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, warnings = piece_outcome(ctx.deps.design_rules, design)
    if refusal:
        return refusal
    summary, proposal = summarise(package_id, design, warnings)
    return Confirmation(
        subject="import_design",
        summary=_with_corrections(f"Import {name}\n{summary}", corrections),
        proposal={**proposal, "file": name},
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    checked, problem = _checked(arguments, ctx)
    if checked is None:
        return problem
    package_id, design, name, _corrections = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, _warnings = piece_outcome(ctx.deps.design_rules, design)
    if refusal:
        return refusal
    version = create_and_record(ctx, package_id, design, changes=[f"imported from {name}"])
    return ToolOutput(
        text=(
            f"Imported the design as {package_id} version {version}; the build has started. "
            "It can be viewed, discussed and revised like any piece."
        ),
        update={"package_id": package_id},
    )


import_design = AgentTool(
    name="import_design",
    description=(
        "Import the design file the owner attached (named in their message with its upload id) as a "
        "new piece. The file is read and checked by the app; the owner is shown a summary and answers "
        "yes or no; nothing is created before yes. Only in a conversation that has no piece yet."
    ),
    schema=ImportDesignArgs,
    run=run,
    preview=preview,
)


# --- the next version of an existing piece ----------------------------------------------------


class ImportVersionArgs(BaseModel):
    upload_id: UUID = Field(description="the upload id of the attached design file, as the owner's message names it")
    package_id: str = Field(description="the package id of the existing piece the file is the next version of")


def _checked_version(
    arguments: dict[str, Any], ctx: ToolContext
) -> tuple[tuple[str, int, dict[str, Any], str, list[str]] | None, str]:
    """`(package_id, latest version, corrected design, file name, hardware corrections)` ready to record,
    or a refusal."""
    args, problem = parse_args(ImportVersionArgs, arguments)
    if args is None:
        return None, problem
    package_id, problem = checked_package_id(args.package_id)
    if package_id is None:
        return None, problem
    latest = latest_version(ctx.deps, package_id)
    if latest is None:
        return None, f"there is no piece {package_id!r}; import the file as a new piece instead"
    read, problem = _read_upload(args.upload_id, ctx)
    if read is None:
        return None, problem
    document, name, bound = read
    if bound and bound != package_id:
        return None, (
            f"this conversation is about {bound}, not {package_id}; import the file as {package_id}'s "
            "next version in a conversation about it, or in a new conversation"
        )
    design, refusal = parse_import(document, ctx, package_id)
    if design is None:
        return None, _quoted(refusal, name, args.upload_id)
    design, corrections = _corrected(design, ctx)
    return (package_id, latest, design, name, corrections), ""


def version_preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    checked, problem = _checked_version(arguments, ctx)
    if checked is None:
        return problem
    package_id, latest, design, name, corrections = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, warnings = piece_outcome(ctx.deps.design_rules, design)
    if refusal:
        return refusal
    summary, proposal = summarise(package_id, design, warnings)
    summary = summary.replace("New piece", "Design", 1)
    return Confirmation(
        subject="import_version",
        summary=_with_corrections(
            f"Import {name} as {package_id} version {latest + 1}, replacing version {latest}'s design\n{summary}",
            corrections,
        ),
        proposal={**proposal, "file": name, "revised_from": latest, "version": latest + 1},
    )


def version_run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    checked, problem = _checked_version(arguments, ctx)
    if checked is None:
        return problem
    package_id, latest, design, name, _corrections = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, _warnings = piece_outcome(ctx.deps.design_rules, design)
    if refusal:
        return refusal
    line = f"imported from {name}, replacing version {latest}"
    version = record_next(ctx, package_id, latest, design, [line])
    return ToolOutput(
        text=f"Created {package_id} version {version} ({line}). The build has started.",
        update={"package_id": package_id},
    )


import_design_version = AgentTool(
    name="import_design_version",
    description=(
        "Import the design file the owner attached (named in their message with its upload id) as the "
        "next version of an existing piece. The file is read and checked by the app; the owner is shown "
        "a summary and answers yes or no; nothing is created before yes."
    ),
    schema=ImportVersionArgs,
    run=version_run,
    preview=version_preview,
)
