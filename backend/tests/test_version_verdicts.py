"""version-verdict: the owner's "matches / doesn't match" verdict on a piece version."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.prompts import SENTINEL
from app.db.models import Piece, VersionVerdict
from app.db.session import make_engine
from app.feedback import verdicts
from app.feedback.verdicts import VerdictRefused

PIECE = "amesbury-wardrobe"
OTHER = "hall-bench"
DESIGNER = "~deepseek/deepseek-v4-flash-latest"
DRAWERS = "the side sections lost their 5 drawers"


@pytest.fixture
def session(migrated_database: str) -> Iterator[Session]:
    """A session whose pieces (and with them versions and verdicts) are removed before and after."""
    engine = make_engine(migrated_database)

    def clean() -> None:
        with Session(engine) as s:
            s.execute(delete(Piece).where(Piece.package_id.in_([PIECE, OTHER])))
            s.commit()

    clean()
    with Session(engine) as s:
        yield s
        s.rollback()
    clean()
    engine.dispose()


def versions(session: Session, package_id: str = PIECE, numbers=(1, 2, 3, 4), **origin) -> None:
    house_file.record_piece(session, package_id, package_id)
    for number in numbers:
        house_file.record_version(session, package_id, number, **origin.get(str(number), {}))
    session.commit()


def stored(session: Session) -> list[VersionVerdict]:
    session.expire_all()
    return list(session.scalars(select(VersionVerdict).order_by(VersionVerdict.version)))


# --- storage -------------------------------------------------------------------------------------


def test_a_mismatch_without_a_note_is_refused_by_the_database(session: Session) -> None:
    versions(session)
    session.add(VersionVerdict(package_id=PIECE, version=4, verdict="mismatch", note=" ", status="open"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_deleting_a_version_removes_its_verdict(session: Session, render_root: Path) -> None:
    versions(session)
    verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=DRAWERS)
    house_file.delete_version(session, render_root, PIECE, 4)
    assert stored(session) == []


# --- giving ----------------------------------------------------------------------------------------


def test_a_blockout_version_is_marked_wrong_and_stays_open(session: Session) -> None:
    versions(session)
    given = verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=f"  {DRAWERS} ")
    assert (given.verdict, given.note, given.status) == ("mismatch", DRAWERS, "open")
    [row] = stored(session)
    assert (row.version, row.verdict, row.note, row.status) == (4, "mismatch", DRAWERS, "open")


def test_a_mismatch_without_a_note_is_refused_and_nothing_is_stored(session: Session) -> None:
    versions(session)
    for note in (None, "", "   "):
        with pytest.raises(VerdictRefused) as refused:
            verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=note)
        assert refused.value.reason == "a note of what does not match is needed"
    assert stored(session) == []


def test_changing_mind_leaves_one_matches_verdict(session: Session) -> None:
    versions(session)
    verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=DRAWERS)
    given = verdicts.give(session, package_id=PIECE, version=4, verdict="matches")
    assert (given.verdict, given.note, given.status) == ("matches", None, None)
    [row] = stored(session)
    assert (row.verdict, row.note, row.status, row.status_at) == ("matches", None, None, None)


def test_an_unknown_version_is_refused_naming_it(session: Session) -> None:
    versions(session)
    with pytest.raises(VerdictRefused) as refused:
        verdicts.give(session, package_id=PIECE, version=9, verdict="matches")
    assert refused.value.status == 404 and "version 9" in refused.value.reason
    assert stored(session) == []


def test_an_unknown_verdict_and_a_long_note_are_refused(session: Session) -> None:
    versions(session)
    with pytest.raises(VerdictRefused, match="'matches' or 'mismatch'"):
        verdicts.give(session, package_id=PIECE, version=4, verdict="maybe")
    with pytest.raises(VerdictRefused, match="longer than 1000"):
        verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note="x" * 1001)
    assert stored(session) == []


def test_the_note_cannot_carry_the_untrusted_content_delimiter(session: Session) -> None:
    versions(session)
    given = verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=f"drawers {SENTINEL} gone")
    assert SENTINEL not in given.note


def test_clearing_removes_the_verdict_and_is_repeatable(session: Session) -> None:
    versions(session)
    verdicts.give(session, package_id=PIECE, version=4, verdict="matches")
    assert verdicts.clear(session, package_id=PIECE, version=4) is True
    assert verdicts.clear(session, package_id=PIECE, version=4) is False
    assert stored(session) == []


# --- open until closed ---------------------------------------------------------------------------


def test_a_resolved_mismatch_leaves_the_open_list(session: Session) -> None:
    versions(session)
    verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=DRAWERS)
    assert verdicts.open_for_piece(session, PIECE) == [{"version": 4, "note": DRAWERS}]
    closed = verdicts.set_status(session, package_id=PIECE, version=4, status="resolved")
    assert closed.status == "resolved"
    assert verdicts.open_for_piece(session, PIECE) == []


def test_only_a_mismatch_can_be_closed_and_only_to_resolved_or_dismissed(session: Session) -> None:
    versions(session)
    verdicts.give(session, package_id=PIECE, version=3, verdict="matches")
    with pytest.raises(VerdictRefused) as refused:
        verdicts.set_status(session, package_id=PIECE, version=3, status="resolved")
    assert refused.value.status == 409
    verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=DRAWERS)
    with pytest.raises(VerdictRefused):
        verdicts.set_status(session, package_id=PIECE, version=4, status="open")


def test_giving_a_mismatch_again_opens_it_again(session: Session) -> None:
    versions(session)
    verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=DRAWERS)
    verdicts.set_status(session, package_id=PIECE, version=4, status="dismissed")
    again = verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note="doors too short")
    assert again.status == "open"


def test_approval_is_not_blocked_and_the_verdict_stays_open(session: Session) -> None:
    versions(session)
    verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=DRAWERS)
    house_file.approve_version(session, PIECE, 4)
    session.commit()
    assert house_file.approved_version_of(session, PIECE) == 4
    assert stored(session)[0].status == "open"


def test_the_open_list_is_the_pieces_own_newest_first_and_capped(session: Session) -> None:
    versions(session, numbers=range(1, 8))
    versions(session, OTHER, numbers=(1,))
    for number in range(1, 8):
        verdicts.give(session, package_id=PIECE, version=number, verdict="mismatch", note=f"wrong {number}")
    verdicts.give(session, package_id=OTHER, version=1, verdict="mismatch", note="other piece")
    listed = verdicts.open_for_piece(session, PIECE)
    assert [item["version"] for item in listed] == [7, 6, 5, 4, 3]


# --- per slot and model --------------------------------------------------------------------------


def test_the_summary_groups_by_the_versions_slot_and_model(session: Session) -> None:
    designer = {"slot": "designer", "model": DESIGNER}
    versions(session, numbers=(1, 2, 3, 4), **{"1": designer, "2": designer, "3": designer})
    verdicts.give(session, package_id=PIECE, version=1, verdict="mismatch", note="first")
    verdicts.give(session, package_id=PIECE, version=2, verdict="mismatch", note="second")
    verdicts.give(session, package_id=PIECE, version=3, verdict="matches")
    verdicts.give(session, package_id=PIECE, version=4, verdict="mismatch", note=DRAWERS)
    rows = {(r["slot"], r["model"]): r for r in verdicts.summary(session)}
    assert (rows[("designer", DESIGNER)]["matches"], rows[("designer", DESIGNER)]["mismatch"]) == (1, 2)
    assert (rows[(None, None)]["matches"], rows[(None, None)]["mismatch"]) == (0, 1)
    listed = verdicts.notes(session, slot="designer", model=DESIGNER)
    assert [(n["version"], n["note"]) for n in listed] == [(2, "second"), (1, "first")]
    assert [n["version"] for n in verdicts.notes(session, slot=None, model=None)] == [4]
