"""`record_version_verdict` (Designer): the owner's verdict on a piece version (version-verdict).

The tool proposes the verdict it read from the owner's words and records it only
after the owner answers yes. The package is the conversation's bound piece, never
an argument the model supplied; the version defaults to the piece's latest
recorded version. A verdict needs no render, so a blockout version can be judged.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.tools.base import AgentTool, Confirmation, ToolContext, parse_args
from app.agent.tools.shared import NOT_APPROVED
from app.db.models import PieceVersion
from app.feedback import verdicts
from app.feedback.verdicts import VerdictRefused

WORDS = {"matches": "Matches what you confirmed", "mismatch": "Doesn't match"}


class VerdictArgs(BaseModel):
    verdict: str = Field(
        description="'matches' when the owner says the version is what they confirmed, 'mismatch' when it is not"
    )
    note: str | None = Field(
        default=None,
        description="the owner's own words about what does not match; required for 'mismatch'",
    )
    version: int | None = Field(default=None, description="a version number; the latest version when left out")


def _checked(arguments: dict[str, Any], ctx: ToolContext) -> tuple[VerdictArgs, int, str | None] | str:
    """The arguments, the version and the cleaned note, or a refusal."""
    args, problem = parse_args(VerdictArgs, arguments)
    if args is None:
        return problem
    if not ctx.package_id:
        return "there is no piece bound to this conversation; ask the owner which piece they mean"
    if args.verdict not in verdicts.VERDICTS:
        return "the verdict must be 'matches' or 'mismatch'"
    try:
        note = verdicts.clean_note(args.note, args.verdict)
    except VerdictRefused as error:
        return error.reason
    with Session(ctx.deps.engine) as session:
        if args.version is None:
            version = session.scalar(
                select(func.max(PieceVersion.version)).where(PieceVersion.package_id == ctx.package_id)
            )
            if version is None:
                return f"{ctx.package_id} has no version to judge yet"
        else:
            version = args.version
            if session.get(PieceVersion, (ctx.package_id, version)) is None:
                return f"{ctx.package_id} has no version {version}"
    return args, version, note


def preview(arguments: dict[str, Any], ctx: ToolContext):
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    args, version, note = checked
    said = f" — {note}" if note else ""
    return Confirmation(
        subject="version_verdict",
        summary=f'Record "{WORDS[args.verdict]}{said}" on {ctx.package_id} version {version}?',
        proposal={"package_id": ctx.package_id, "version": version, "verdict": args.verdict, "note": note},
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.approved:
        return NOT_APPROVED
    checked = _checked(arguments, ctx)
    if isinstance(checked, str):
        return checked
    args, version, note = checked
    try:
        with Session(ctx.deps.engine) as session:
            given = verdicts.give(
                session, package_id=ctx.package_id, version=version, verdict=args.verdict, note=note
            )
    except VerdictRefused as error:
        return error.reason
    tracing = ctx.deps.tracing
    if tracing is not None:
        tracing.record_verdict(
            verdict=given.verdict, note=given.note, slot=given.slot, model=given.model,
            package_id=given.package_id, version=given.version,
        )
    open_text = " It stays open until the owner marks it resolved." if given.status == "open" else ""
    return f'Recorded "{WORDS[given.verdict]}" on {given.package_id} version {given.version}.{open_text}'


record_version_verdict = AgentTool(
    name="record_version_verdict",
    description=(
        "Record the owner's verdict on a version of the bound piece: 'matches' when they say it is "
        "what they confirmed, 'mismatch' with their note when it is not. Use it only when the owner "
        "says a version is right or wrong. It shows what will be recorded and waits for the owner's yes."
    ),
    schema=VerdictArgs,
    run=run,
    preview=preview,
)
