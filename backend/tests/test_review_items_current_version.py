"""review-items-follow-approved-version: the open review items in the context are the current version's."""

from __future__ import annotations

from app.agent import house_file
from app.agent.prompts import house_note
from app.agent.tools.base import ToolDeps
from tests.graph_helpers import fake_models, make_harness
from tests.test_foreman import _bind_piece, decision

ITEM = {
    "aspect": "brief",
    "expected": "a width of 1200 mm",
    "expected_source": "brief",
    "observed": "1400 mm wide",
    "image": 1,
    "severity": "major",
}


def _reviews(session, versions: dict[int, list[dict]]) -> None:
    house_file.record_piece(session, "hall-bench", "Hall bench")
    for number, items in versions.items():
        house_file.record_version(session, "hall-bench", number)
        house_file.record_review(session, "hall-bench", number, ["screenshot.png"], items)
    session.flush()


def test_an_older_versions_review_is_ignored_and_the_versions_own_is_used(db_session) -> None:
    _reviews(db_session, {1: [ITEM], 2: [{**ITEM, "expected": "two drawers"}]})
    old = house_file.latest_open_items(db_session, "hall-bench", 1)
    new = house_file.latest_open_items(db_session, "hall-bench", 2)
    assert [(i["version"], i["expected"]) for i in old] == [(1, "a width of 1200 mm")]
    assert [(i["version"], i["expected"]) for i in new] == [(2, "two drawers")]
    assert house_file.latest_open_items(db_session, "hall-bench", 3) == []


def test_reading_writes_nothing(db_session) -> None:
    _reviews(db_session, {1: [ITEM]})
    before = [i.status for r in house_file.reviews_for(db_session, "hall-bench", 1) for i in house_file.items_of(db_session, r.id)]
    house_file.latest_open_items(db_session, "hall-bench", 2)
    after = [i.status for r in house_file.reviews_for(db_session, "hall-bench", 1) for i in house_file.items_of(db_session, r.id)]
    assert before == after == ["open"]


def test_each_item_names_its_version() -> None:
    note = house_note([], {}, [], [], review_items=[{"aspect": "brief", "version": 3, "expected": "a", "observed": "b"}])
    assert "- brief (version 3): expected a; observed b" in note


def test_the_designer_gets_the_approved_versions_review_not_the_newest_versions(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("designer"), decision("designer"), decision("designer")]},
        designer={"replies": ["a", "b", "c"]},
    )
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=False)
    with ToolDeps(tool_state).session() as session:
        house_file.record_review(session, "hall-bench", 1, ["screenshot.png"], [ITEM])
        house_file.record_version(session, "hall-bench", 2)
        session.commit()
    # Latest version 2 has no review: the version 1 item is not shown.
    harness.turn("what is open?")
    assert "Open review items:" not in models["designer"].last_prompt_text()
    # Approving version 1 makes its review the current one.
    with ToolDeps(tool_state).session() as session:
        house_file.approve_version(session, "hall-bench", 1)
        session.commit()
    harness.turn("and now?")
    assert "brief (version 1): expected a width of 1200 mm" in models["designer"].last_prompt_text()
    # Approving version 2, which has no review, shows nothing.
    with ToolDeps(tool_state).session() as session:
        house_file.approve_version(session, "hall-bench", 2)
        session.commit()
    harness.turn("and again?")
    assert "Open review items:" not in models["designer"].last_prompt_text()


def test_a_review_reads_the_raised_limit_in_the_brief() -> None:
    from app.agent.house_file import raised_height_limit
    from plugins.revision_review.tool import json_brief

    brief = raised_height_limit({"room": "Wohnen", "max_piece_height_mm": 2200}, 2238, 17)
    assert "max_piece_height_mm: 2238" in json_brief(brief)
    assert "max_piece_height_from_version: 17" in json_brief(brief)


def _statuses(session, version: int) -> dict[str, str]:
    return {
        i.expected: i.status
        for r in house_file.reviews_for(session, "hall-bench", version)
        for i in house_file.items_of(session, r.id)
    }


def test_items_expecting_an_older_height_limit_are_dismissed_and_nothing_else(db_session) -> None:
    def item(expected: str) -> dict:
        return {**ITEM, "expected": expected}

    _reviews(
        db_session,
        {
            1: [item("max_piece_height_mm 2200.0"), item("max_piece_height_mm: 2238"), item("doors on the bottom"),
                item("max_piece_height_mm 2400.0")],
            2: [item("max_piece_height_mm 2200.0")],
        },
    )
    assert house_file.dismiss_outdated_height_items(db_session, "hall-bench", 1, 2238) == 1
    assert _statuses(db_session, 1) == {
        "max_piece_height_mm 2200.0": "dismissed",
        "max_piece_height_mm: 2238": "open",
        "doors on the bottom": "open",
        "max_piece_height_mm 2400.0": "open",
    }
    assert _statuses(db_session, 2) == {"max_piece_height_mm 2200.0": "open"}  # another version
    assert house_file.dismiss_outdated_height_items(db_session, "hall-bench", 1, 2238) == 0  # idempotent
