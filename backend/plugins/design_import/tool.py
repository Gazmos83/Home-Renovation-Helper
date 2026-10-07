"""`import_design` (Designer): an attached design file becomes a new piece (design-import).

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
from app.agent.tools.shared import NOT_APPROVED, builds_unavailable
from app.design_import import parse_import
from app.guidelines.rules import piece_outcome
from plugins.create_piece.tool import checked_new_id, create_and_record, summarise


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


def _checked(arguments: dict[str, Any], ctx: ToolContext) -> tuple[tuple[str, dict[str, Any], str] | None, str]:
    """`(package_id, design, file name)` ready to create, or a refusal."""
    args, problem = parse_args(ImportDesignArgs, arguments)
    if args is None:
        return None, problem
    with ctx.deps.session() as session:
        upload = uploads.get_upload(session, args.upload_id)
        if upload is None or ctx.thread_id is None or upload.thread_id != ctx.thread_id:
            return None, f"there is no upload {args.upload_id} in this conversation"
        if upload.kind != "design":
            return None, f"upload {args.upload_id} is an image, not a design file"
        path = uploads.upload_path(ctx.deps.settings.upload_root, upload.thread_id, upload.id, upload.kind)
        name = upload.original_name
        thread = house_file.get_thread(session, ctx.thread_id)
        bound = thread.package_id if thread else None
    if bound:
        return None, (
            f"this conversation is already about {bound}; a design is imported as a new piece, "
            "so ask the owner to start a new conversation and attach the file there"
        )
    package_id, problem = checked_new_id(ctx, args.package_id)
    if package_id is None:
        return None, problem
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, f"the design file {args.upload_id} can no longer be read; ask the owner to attach it again"
    design, refusal = parse_import(document, ctx, package_id)
    if design is None:
        return None, _quoted(refusal, name, args.upload_id)
    return (package_id, design, name), ""


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    checked, problem = _checked(arguments, ctx)
    if checked is None:
        return problem
    package_id, design, name = checked
    unavailable = builds_unavailable(ctx.deps)
    if unavailable:
        return unavailable
    refusal, warnings = piece_outcome(ctx.deps.design_rules, design)
    if refusal:
        return refusal
    summary, proposal = summarise(package_id, design, warnings)
    return Confirmation(
        subject="import_design",
        summary=f"Import {name}\n{summary}",
        proposal={**proposal, "file": name},
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    if not ctx.approved:
        return NOT_APPROVED
    checked, problem = _checked(arguments, ctx)
    if checked is None:
        return problem
    package_id, design, name = checked
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
