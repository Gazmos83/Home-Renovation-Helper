"""The "decisions so far" note as rows, and the one save every writer uses.

The row rules mirror the panel's (`frontend/src/components/chat/DecisionsNote.tsx`:
`noteRows`, `replaceRow`, `appendRow`, `deleteRow`), so a chat edit and a table edit
write the same text. `tests/test_decisions_note.py` runs the panel's own cases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.prompts import neutralise
from app.db.models import Piece, ThreadPiece

NOTE_MAX_CHARS: Final = 8000
NO_SUCH_NOTE: Final = "this conversation has no such note to change"

_HEADING = re.compile(r"^#+\s*(.*?)\s*:?$")
_BOLD_HEADING = re.compile(r"^\*\*(.*?):?\*\*:?$")
_BULLET = re.compile(r"^([-*•]|\d+[.)])\s+")
_LABEL = re.compile(r"^\*\*(.+?):?\*\*:?\s*(.*)$")
_TITLE = re.compile(r"^decisions so far$", re.IGNORECASE)
_HEADING_LINE = re.compile(r"^#+\s")
_VERSION = re.compile(r"\b(?:version|v)\s*(\d+)\b", re.IGNORECASE)
_SAVED = re.compile(r"\b(?:saved|created|built|recorded|made)\b", re.IGNORECASE)
# Wording that makes a row a decision or a reason rather than a bare record of a save.
_DECISION = re.compile(
    r"\b(?:moved|changed?|because|instead|rather|replaced?|switched|decided?|from|to|should|needs?|"
    r"added|removed|approved|wider|narrower|taller|shorter)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Row:
    topic: str
    decision: str
    line: int  # the row's line in the note
    bullet: str
    labelled: bool  # carries its own "**Topic:**"


def _one(value: str) -> str:
    return " ".join(value.split())


def rows(text: str) -> list[Row]:
    """The note's bullets as rows: a "**Label:**" opens its own topic, otherwise the last heading is."""
    found: list[Row] = []
    topic = ""
    for number, raw in enumerate(text.split("\n")):
        line = raw.strip()
        if not line:
            continue
        heading = _HEADING.match(line) or _BOLD_HEADING.match(line)
        if heading:
            if not _TITLE.match(heading.group(1)):
                topic = heading.group(1)
            continue
        marker = _BULLET.match(line)
        bullet = marker.group(1) if marker else "-"
        item = _BULLET.sub("", line, count=1)
        label = _LABEL.match(item)
        row_topic, decision = (label.group(1), label.group(2)) if label else (topic, item)
        found.append(Row(row_topic, decision.replace("**", ""), number, bullet, label is not None))
    return found


def replace_row(text: str, row: Row, topic: str, decision: str) -> str:
    """The note with one row's line rewritten. A changed topic (or an already labelled row) is
    written as "**Topic:** decision"; an unchanged topic under a heading stays a plain bullet."""
    new_topic, new_decision = _one(topic), _one(decision)
    lines = text.split("\n")
    if row.labelled or new_topic != row.topic:
        lines[row.line] = f"{row.bullet} **{new_topic}:** {new_decision}"
    else:
        lines[row.line] = f"{row.bullet} {new_decision}"
    return "\n".join(lines)


def append_row(text: str, topic: str, decision: str) -> str:
    """The note with a new "- **Topic:** decision" line at the end."""
    line = f"- **{_one(topic)}:** {_one(decision)}"
    return f"{text.rstrip()}\n{line}" if text.strip() else line


def delete_row(text: str, row: Row) -> str:
    """The note without one row's line. A heading left with no bullets under it goes too."""
    lines = [line for number, line in enumerate(text.split("\n")) if number != row.line]
    kept = []
    for number, line in enumerate(lines):
        if _HEADING_LINE.match(line.strip()):
            following = next((other for other in lines[number + 1 :] if other.strip()), None)
            if following is None or _HEADING_LINE.match(following.strip()):
                continue
        kept.append(line)
    return "\n".join(kept).strip()


def store_note(session: Session, thread_id: UUID, package_id: str | None, text: str) -> str | None:
    """Save `text` as the owner's note for the thread's active build, as the panel does (neutralised,
    owner-marked). Returns a refusal naming the problem, or `None` once flushed (the caller commits)."""
    cleaned = neutralise(text.strip())
    if not cleaned:
        return "the note cannot be empty"
    if len(cleaned) > NOTE_MAX_CHARS:
        return f"the note would be longer than {NOTE_MAX_CHARS} characters"
    if not house_file.write_owner_summary(session, thread_id, cleaned, package_id):
        return NO_SUCH_NOTE
    return None


def _names(name: str, package_id: str) -> list[str]:
    return [value.lower() for value in {name, package_id, package_id.replace("-", " ")} if value.strip()]


def superseded_version_rows(
    text: str, name: str, package_id: str, approved: int, others: list[tuple[str, str]] = ()
) -> list[Row]:
    """The rows that only record an older version (lower than `approved`) of the piece being saved.

    A row qualifies when every version it names is older, it says saved, created or built, and it
    carries no decision or reason wording. A row naming another piece (`others`, as name and id) and
    not this one is kept. Anything uncertain is kept."""
    mine = _names(name, package_id)
    foreign = [value for pair in others for value in _names(*pair) if value not in mine]
    found: list[Row] = []
    for row in rows(text):
        line = f"{row.topic} {row.decision}".lower()
        numbers = [int(number) for number in _VERSION.findall(line)]
        if not numbers or max(numbers) >= approved:
            continue
        if not _SAVED.search(line) or _DECISION.search(line):
            continue
        if not any(value in line for value in mine) and any(value in line for value in foreign):
            continue
        found.append(row)
    return found


def drop_superseded_version_rows(session: Session, package_id: str, approved: int) -> int:
    """Remove those rows from the note of every conversation bound to the piece, once `approved` is
    its approved version; the number of notes changed. A note left with no rows, and the owner mark,
    are kept as they were. The caller commits."""
    piece = session.get(Piece, package_id)
    name = piece.name if piece else package_id
    others = [(p.name, p.package_id) for p in session.scalars(select(Piece).where(Piece.package_id != package_id))]
    changed = 0
    for build in session.scalars(select(ThreadPiece).where(ThreadPiece.package_id == package_id)):
        if not build.summary:
            continue
        text = build.summary
        for row in sorted(superseded_version_rows(text, name, package_id, approved, others), key=lambda r: -r.line):
            text = delete_row(text, row)
        if text != build.summary and rows(text):
            build.summary = text
            changed += 1
    session.flush()
    return changed
