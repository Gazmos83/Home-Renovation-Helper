"""The owner's verdict on a piece version (version-verdict design decision 3).

Does the version match what the owner confirmed? One current verdict per version:
giving one again replaces it, clearing removes it. Unlike a render rating it needs
no render, so a blockout version can be judged. A `mismatch` carries a note and
stays `open` until the owner resolves or dismisses it; a verdict never changes a
spec, an approval, a build or a render.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.prompts import neutralise
from app.db.models import PieceVersion, VersionVerdict

VERDICTS: Final = ("matches", "mismatch")
CLOSED: Final = ("resolved", "dismissed")
MAX_NOTE_CHARACTERS: Final = 1000
OPEN_LIMIT: Final = 5


class VerdictRefused(Exception):
    """A verdict that cannot be recorded. `reason` is safe to show; `status` is HTTP-shaped."""

    def __init__(self, reason: str, *, failure_class: str = "refused", status: int = 422) -> None:
        super().__init__(reason)
        self.reason = reason
        self.failure_class = failure_class
        self.status = status


@dataclass(frozen=True, slots=True)
class Given:
    """A stored verdict with the version's origin, for the reply and tracing."""

    package_id: str
    version: int
    verdict: str
    note: str | None
    status: str | None
    slot: str | None
    model: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def clean_note(note: object, verdict: str) -> str | None:
    """The note as stored, or a refusal: text, at most 1 000 characters, required for a mismatch."""
    if note is not None and not isinstance(note, str):
        raise VerdictRefused("the note must be text", failure_class="invalid_note")
    cleaned = neutralise(note.strip()) if note else ""
    if len(cleaned) > MAX_NOTE_CHARACTERS:
        raise VerdictRefused(
            f"the note is longer than {MAX_NOTE_CHARACTERS} characters", failure_class="invalid_note"
        )
    if verdict == "mismatch" and not cleaned:
        raise VerdictRefused(
            "a note of what does not match is needed", failure_class="note_required"
        )
    return cleaned or None


def _version(session: Session, package_id: str, version: int) -> PieceVersion:
    row = session.get(PieceVersion, (package_id, version))
    if row is None:
        raise VerdictRefused(
            f"{package_id} has no version {version}", failure_class="unknown_version", status=404
        )
    return row


def _given(row: VersionVerdict, origin: PieceVersion) -> Given:
    return Given(
        row.package_id, row.version, row.verdict, row.note, row.status, origin.slot, origin.model
    )


def give(session: Session, *, package_id: str, version: int, verdict: object, note: object = None) -> Given:
    """Store (or replace) the version's verdict; a mismatch is open again after any change."""
    if verdict not in VERDICTS:
        raise VerdictRefused(
            "the verdict must be 'matches' or 'mismatch'", failure_class="invalid_verdict"
        )
    cleaned = clean_note(note, verdict)
    origin = _version(session, package_id, version)
    row = session.get(VersionVerdict, (package_id, version))
    now = _now()
    status = "open" if verdict == "mismatch" else None
    if row is None:
        row = VersionVerdict(package_id=package_id, version=version)
        session.add(row)
    row.verdict = verdict
    row.note = cleaned
    row.status = status
    row.status_at = now if status else None
    row.updated_at = now
    session.commit()
    return _given(row, origin)


def clear(session: Session, *, package_id: str, version: int) -> bool:
    """Remove the version's verdict; whether there was one."""
    _version(session, package_id, version)
    row = session.get(VersionVerdict, (package_id, version))
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


def set_status(session: Session, *, package_id: str, version: int, status: object) -> Given:
    """Mark the version's open mismatch resolved or dismissed."""
    if status not in CLOSED:
        raise VerdictRefused(
            "the status must be 'resolved' or 'dismissed'", failure_class="invalid_status"
        )
    origin = _version(session, package_id, version)
    row = session.get(VersionVerdict, (package_id, version))
    if row is None or row.verdict != "mismatch":
        raise VerdictRefused(
            f"{package_id} version {version} has no mismatch to close",
            failure_class="no_mismatch",
            status=409,
        )
    row.status = status
    row.status_at = _now()
    session.commit()
    return _given(row, origin)


def current(session: Session, package_id: str, version: int) -> VersionVerdict | None:
    """The version's verdict, or `None`; refused when the version is not recorded."""
    _version(session, package_id, version)
    return session.get(VersionVerdict, (package_id, version))


def as_dict(row: VersionVerdict | None) -> dict | None:
    """The homeowner's view of a verdict: never the slot or model."""
    if row is None:
        return None
    return {
        "verdict": row.verdict,
        "note": row.note,
        "status": row.status,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def open_for_piece(session: Session, package_id: str, limit: int = OPEN_LIMIT) -> list[dict]:
    """The piece's open mismatches across its versions, newest first, for the agents' context."""
    rows = session.scalars(
        select(VersionVerdict)
        .where(
            VersionVerdict.package_id == package_id,
            VersionVerdict.verdict == "mismatch",
            VersionVerdict.status == "open",
        )
        .order_by(VersionVerdict.updated_at.desc())
        .limit(limit)
    )
    return [{"version": row.version, "note": row.note} for row in rows]


def summary(session: Session, *, days: int = 30) -> list[dict]:
    """Verdict counts per slot and model of the version. Origin-less versions group under none."""
    cutoff = _now() - timedelta(days=days)
    rows = session.execute(
        select(
            PieceVersion.slot,
            PieceVersion.model,
            func.count().filter(VersionVerdict.verdict == "matches"),
            func.count().filter(VersionVerdict.verdict == "mismatch"),
            func.max(VersionVerdict.updated_at).filter(VersionVerdict.note.is_not(None)),
        )
        .join(
            PieceVersion,
            (PieceVersion.package_id == VersionVerdict.package_id)
            & (PieceVersion.version == VersionVerdict.version),
        )
        .where(VersionVerdict.updated_at >= cutoff)
        .group_by(PieceVersion.slot, PieceVersion.model)
        .order_by(PieceVersion.slot.nulls_last(), PieceVersion.model.nulls_last())
    ).all()
    return [
        {
            "slot": slot,
            "model": model,
            "matches": matches,
            "mismatch": mismatch,
            "latest_note_at": latest.isoformat() if latest else None,
        }
        for slot, model, matches, mismatch, latest in rows
    ]


def notes(session: Session, *, slot: str | None, model: str | None, limit: int = 50) -> list[dict]:
    """The notes of one summary group, newest first, each naming its piece and version."""
    rows = session.execute(
        select(VersionVerdict)
        .join(
            PieceVersion,
            (PieceVersion.package_id == VersionVerdict.package_id)
            & (PieceVersion.version == VersionVerdict.version),
        )
        .where(
            PieceVersion.slot.is_(None) if slot is None else PieceVersion.slot == slot,
            PieceVersion.model.is_(None) if model is None else PieceVersion.model == model,
            VersionVerdict.note.is_not(None),
        )
        .order_by(VersionVerdict.updated_at.desc())
        .limit(limit)
    ).scalars()
    return [
        {
            "package_id": row.package_id,
            "version": row.version,
            "verdict": row.verdict,
            "status": row.status,
            "note": row.note,
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]
