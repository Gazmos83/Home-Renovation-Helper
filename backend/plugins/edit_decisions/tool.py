"""`edit_decisions` (Designer, chat-control-of-decisions): one row of the "decisions so far" note.

Gated. Used only when the owner's own message asks for a row to be added, changed or
deleted. The owner is shown the row as it is now and as it will be, and nothing is written
before "yes". The note is the conversation's own (its active build's, or the thread's),
taken from the session; the model names only a row, by its topic and, when two rows share
a topic, its position. The write is the panel's save. No spec, figure, price or house-file
record changes.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent import decisions_note, house_file
from app.agent.decisions_note import Row
from app.agent.tools.base import AgentTool, Confirmation, ToolContext, parse_args
from app.agent.tools.shared import NOT_APPROVED


class EditDecisionsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["add", "change", "delete"] = Field(
        description="add a new row, change an existing row, or delete an existing row"
    )
    topic: str = Field(
        min_length=1,
        max_length=200,
        description="the row's topic: for `add` the new row's topic, otherwise the existing row's topic as shown in the note",
    )
    position: int | None = Field(
        default=None,
        ge=1,
        description="only when two rows share the topic: which of them, counting from 1 in the order of the note",
    )
    decision: str | None = Field(
        default=None,
        max_length=2000,
        description="the decision text, for `add` and `change`",
    )
    new_topic: str | None = Field(
        default=None, min_length=1, max_length=200, description="a new topic for the row, for `change` only"
    )

    @model_validator(mode="after")
    def _needs(self) -> EditDecisionsArgs:
        if self.action in {"add", "change"} and not (self.decision or "").strip() and not (
            self.action == "change" and self.new_topic
        ):
            raise ValueError("`add` and `change` need the decision text")
        if self.action != "change" and self.new_topic:
            raise ValueError("`new_topic` is only for `change`")
        if self.action == "add" and self.position is not None:
            raise ValueError("`position` is only for `change` and `delete`")
        return self


def _listing(found: list[Row]) -> str:
    return "; ".join(f"{index}. {row.topic}: {row.decision}" for index, row in enumerate(found, start=1))


def _resolve(args: EditDecisionsArgs, found: list[Row]) -> tuple[Row | None, str]:
    """The one row the call names, or a refusal that lists the candidates."""
    topic = args.topic.strip().casefold()
    matches = [row for row in found if row.topic.strip().casefold() == topic]
    if not matches:
        return None, (
            f"the note has no row with the topic {args.topic!r}"
            + (f"; its rows are: {_listing(found)}" if found else "")
            + ". Nothing was changed."
        )
    if args.position is None:
        if len(matches) > 1:
            return None, (
                f"{len(matches)} rows have the topic {args.topic!r}: {_listing(matches)}. "
                "Ask the owner which one and call again with its position. Nothing was changed."
            )
        return matches[0], ""
    if args.position > len(matches):
        return None, (
            f"only {len(matches)} row(s) have the topic {args.topic!r}: {_listing(matches)}. Nothing was changed."
        )
    return matches[args.position - 1], ""


def _plan(arguments: dict[str, Any], ctx: ToolContext) -> tuple[tuple[str, str, str] | None, str]:
    """`(new note text, before line, after line)` or a refusal; reads the note, writes nothing."""
    args, problem = parse_args(EditDecisionsArgs, arguments)
    if args is None:
        return None, problem
    assert isinstance(args, EditDecisionsArgs)
    if ctx.thread_id is None:
        return None, "there is no conversation whose notes can be changed"
    with ctx.deps.session() as session:
        text, _through = house_file.read_summary(session, ctx.thread_id, ctx.package_id)
    text = text or ""
    found = decisions_note.rows(text)
    if args.action == "add":
        decision = (args.decision or "").strip()
        new = decisions_note.append_row(text, args.topic, decision)
        return (new, "(no such row yet)", f"{args.topic.strip()}: {' '.join(decision.split())}"), ""
    if not found:
        return None, "the note has no rows yet. Nothing was changed."
    row, problem = _resolve(args, found)
    if row is None:
        return None, problem
    if args.action == "delete":
        if len(found) < 2:
            return None, "that is the note's only row, and the note cannot be left empty. Nothing was changed."
        return (decisions_note.delete_row(text, row), f"{row.topic}: {row.decision}", "(row removed)"), ""
    topic = (args.new_topic or row.topic).strip()
    decision = (args.decision or row.decision).strip()
    new = decisions_note.replace_row(text, row, topic, decision)
    return (new, f"{row.topic}: {row.decision}", f"{' '.join(topic.split())}: {' '.join(decision.split())}"), ""


def preview(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str:
    planned, problem = _plan(arguments, ctx)
    if planned is None:
        return problem
    new, before, after = planned
    if not new.strip():
        return "that would leave the note empty. Nothing was changed."
    if len(new) > decisions_note.NOTE_MAX_CHARS:
        return f"the note would be longer than {decisions_note.NOTE_MAX_CHARS} characters. Nothing was changed."
    action = str(arguments.get("action"))
    return Confirmation(
        subject="decisions",
        summary=f"Decisions so far — {action} a row:\nNow: {before}\nAfter: {after}",
        proposal={"action": action, "before": before, "after": after},
    )


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    if not ctx.approved:
        return NOT_APPROVED
    planned, problem = _plan(arguments, ctx)
    if planned is None:
        return problem
    assert ctx.thread_id is not None
    with ctx.deps.session() as session:
        refusal = decisions_note.store_note(session, ctx.thread_id, ctx.package_id, planned[0])
        if refusal is not None:
            session.rollback()
            return f"{refusal}. Nothing was changed."
        session.commit()
    return (
        f"The decisions note was changed ({arguments.get('action')}): now {planned[2]}. "
        "Only that row changed; no figure, spec or price was touched."
    )


edit_decisions = AgentTool(
    name="edit_decisions",
    description=(
        "Add, change or delete ONE row of this conversation's \"decisions so far\" note. Call it only when the "
        "owner's own message asks for that; never on your own, and never as part of another request. Name an "
        "existing row by its topic as the note shows it (with `position` when two rows share the topic). The owner "
        "is shown the row now and after and answers yes or no; nothing is written before yes. It changes the note "
        "only, never a dimension, spec or price."
    ),
    schema=EditDecisionsArgs,
    run=run,
    preview=preview,
)
