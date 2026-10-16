"""version-verdict: the Designer's chat tool that records a spoken verdict on a version."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.tools.base import Confirmation
from app.db.models import Piece, VersionVerdict
from app.plugins.loader import load_plugins
from plugins.version_verdict.tool import preview, run

PIECE = "amesbury-wardrobe"
SAID = {"verdict": "mismatch", "note": "the side drawers are missing"}


@pytest.fixture
def pieces(tool_state) -> Iterator[None]:
    def clean() -> None:
        with Session(tool_state.engine) as session:
            session.execute(delete(Piece).where(Piece.package_id == PIECE))
            session.commit()

    clean()
    with Session(tool_state.engine) as session:
        house_file.record_piece(session, PIECE, "Amesbury Wardrobe")
        for number in (1, 2, 3, 4):
            house_file.record_version(session, PIECE, number)
        session.commit()
    yield
    clean()


def stored(tool_state) -> list[VersionVerdict]:
    with Session(tool_state.engine) as session:
        return list(session.scalars(select(VersionVerdict)))


def test_the_tool_proposes_what_it_read_and_stores_nothing_until_yes(make_ctx, tool_state, pieces) -> None:
    ctx = make_ctx(package_id=PIECE)
    shown = preview({**SAID, "version": 4}, ctx)
    assert isinstance(shown, Confirmation) and shown.subject == "version_verdict"
    assert shown.summary == (
        'Record "Doesn\'t match — the side drawers are missing" on amesbury-wardrobe version 4?'
    )
    assert shown.proposal == {"package_id": PIECE, "version": 4, "verdict": "mismatch", "note": SAID["note"]}
    assert "confirmation" in run(SAID, ctx)
    assert stored(tool_state) == []


def test_an_approved_verdict_is_stored_open(make_ctx, tool_state, pieces) -> None:
    result = run({**SAID, "version": 4}, replace(make_ctx(package_id=PIECE), approved=True))
    assert result.startswith('Recorded "Doesn\'t match" on amesbury-wardrobe version 4.')
    [row] = stored(tool_state)
    assert (row.version, row.verdict, row.note, row.status) == (4, "mismatch", SAID["note"], "open")


def test_the_latest_version_is_used_when_none_is_named(make_ctx, pieces) -> None:
    shown = preview({"verdict": "matches"}, make_ctx(package_id=PIECE))
    assert shown.proposal["version"] == 4 and shown.proposal["note"] is None


def test_no_bound_piece_is_refused_with_a_question(make_ctx, tool_state, pieces) -> None:
    refusal = preview(SAID, make_ctx())
    assert refusal == "there is no piece bound to this conversation; ask the owner which piece they mean"
    assert run(SAID, replace(make_ctx(), approved=True)) == refusal
    assert stored(tool_state) == []


def test_the_same_checks_as_the_routes_apply(make_ctx, pieces) -> None:
    ctx = make_ctx(package_id=PIECE)
    assert preview({"verdict": "mismatch"}, ctx) == "a note of what does not match is needed"
    assert preview({**SAID, "version": 9}, ctx) == "amesbury-wardrobe has no version 9"
    assert preview({"verdict": "maybe"}, ctx) == "the verdict must be 'matches' or 'mismatch'"


def test_the_manifest_loads_for_the_designer_and_is_toggleable() -> None:
    plugin = load_plugins().by_name["version_verdict"]
    manifest = plugin.manifest
    assert manifest.role == "designer" and manifest.toggleable and manifest.enabled_by_default
    assert list(plugin.tools) == ["record_version_verdict"]
