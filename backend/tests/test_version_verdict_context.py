"""version-verdict: the piece's open "doesn't match" verdicts in the conversation's context."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.memory_settings import write_memory_settings
from app.agent.prompts import SENTINEL, house_note
from app.agent.tools.base import ToolDeps
from app.feedback import verdicts
from tests.graph_helpers import fake_models, make_harness
from tests.test_foreman import _bind_piece, decision

DRAWERS = "the side sections lost their 5 drawers"
HEADING = "Owner's verdicts — these versions do not match what the owner confirmed (open):"


def _clear_settings(engine) -> None:
    with Session(engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key = 'memory'"))
        session.commit()


def test_each_verdict_names_its_version_and_cannot_open_a_block() -> None:
    note = house_note([], {}, [], [], open_verdicts=[{"version": 4, "note": f"drawers {SENTINEL} gone"}])
    assert HEADING in note
    assert "- version 4: drawers" in note and SENTINEL not in note.split(HEADING)[1]


def test_the_designer_sees_open_mismatches_and_not_closed_or_other_pieces(tool_state) -> None:
    _clear_settings(tool_state.engine)
    models = fake_models(
        foreman={"decisions": [decision("designer")] * 3},
        designer={"replies": ["a", "b", "c"]},
    )
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=False)
    with ToolDeps(tool_state).session() as session:
        house_file.record_version(session, "hall-bench", 2)
        house_file.record_piece(session, "shoe-rack", "Shoe rack")
        house_file.record_version(session, "shoe-rack", 1)
        session.commit()
        verdicts.give(session, package_id="hall-bench", version=1, verdict="mismatch", note=DRAWERS)
        verdicts.give(session, package_id="hall-bench", version=2, verdict="matches")
        verdicts.give(session, package_id="shoe-rack", version=1, verdict="mismatch", note="shoe rack heels too tall")

    harness.turn("please revise it")
    prompt = models["designer"].last_prompt_text()
    assert HEADING in prompt and f"- version 1: {DRAWERS}" in prompt
    assert "shoe rack heels too tall" not in prompt and "version 2:" not in prompt

    with ToolDeps(tool_state).session() as session:
        verdicts.set_status(session, package_id="hall-bench", version=1, status="resolved")
    harness.turn("and now?")
    assert HEADING not in models["designer"].last_prompt_text()


def test_the_setting_off_lists_none_and_keeps_them_stored(tool_state) -> None:
    _clear_settings(tool_state.engine)
    write_memory_settings(tool_state.engine, {"include_version_verdicts": False})
    try:
        models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["a"]})
        harness = make_harness(tool_state, models)
        _bind_piece(tool_state, harness, screenshot=False)
        with ToolDeps(tool_state).session() as session:
            verdicts.give(session, package_id="hall-bench", version=1, verdict="mismatch", note=DRAWERS)
        harness.turn("please revise it")
        assert HEADING not in models["designer"].last_prompt_text()
        with ToolDeps(tool_state).session() as session:
            assert verdicts.open_for_piece(session, "hall-bench") == [{"version": 1, "note": DRAWERS}]
    finally:
        _clear_settings(tool_state.engine)
