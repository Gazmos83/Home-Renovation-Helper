"""chat-control-of-decisions: the `edit_decisions` tool changes one note row, only on the owner's yes."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.foreman import last_reply
from app.agent.tools import loaded_plugins
from app.plugins.enablement import set_global_enabled
from plugins.edit_decisions.tool import preview, run
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness
from tests.test_foreman import HALL, decision

NOTE = "## Figures\n- **Room:** Wohnen\n- **Doors:** hinged\n- **Doors:** push-latch\n- **Shelves:** 3"


def _thread(tool_state, note: str | None = NOTE, package_id: str | None = None):
    with Session(tool_state.engine) as session:
        thread = house_file.create_thread(session, "test", package_id=package_id)
        if package_id:
            house_file.add_build(session, thread.id, package_id)
        if note is not None:
            assert house_file.write_owner_summary(session, thread.id, note, package_id)
        session.commit()
        return thread.id


def _note(tool_state, thread, package_id: str | None = None) -> str | None:
    with Session(tool_state.engine) as session:
        return house_file.read_summary(session, thread, package_id)[0]


def test_a_change_is_previewed_with_before_and_after_then_written_on_yes(tool_state, make_ctx) -> None:
    thread = _thread(tool_state)
    args = {"action": "change", "topic": "Room", "decision": "Wohnen v2"}
    shown = preview(args, make_ctx(thread_id=thread))
    assert shown.summary.endswith("Now: Room: Wohnen\nAfter: Room: Wohnen v2")
    assert _note(tool_state, thread) == NOTE  # the preview writes nothing

    assert run(args, make_ctx(thread_id=thread)).startswith("this action needs")
    assert _note(tool_state, thread) == NOTE
    result = run(args, make_ctx(thread_id=thread, approved=True))
    assert "now Room: Wohnen v2" in result
    assert _note(tool_state, thread) == NOTE.replace("Wohnen\n", "Wohnen v2\n")
    with Session(tool_state.engine) as session:
        assert house_file.summary_owner_edited(session, thread, None) is True


def test_a_row_is_added_and_a_note_less_conversation_gets_its_first_row(tool_state, make_ctx) -> None:
    thread = _thread(tool_state)
    run({"action": "add", "topic": "Handles", "decision": "push-latch"}, make_ctx(thread_id=thread, approved=True))
    assert _note(tool_state, thread) == NOTE + "\n- **Handles:** push-latch"

    empty = _thread(tool_state, note=None)
    with Session(tool_state.engine) as session:
        # the thread exists but has no note yet: write_owner_summary stores the first text
        assert house_file.read_summary(session, empty)[0] is None
    run({"action": "add", "topic": "Room", "decision": "Wohnen"}, make_ctx(thread_id=empty, approved=True))
    assert _note(tool_state, empty) == "- **Room:** Wohnen"


def test_a_row_is_deleted_by_topic_and_position(tool_state, make_ctx) -> None:
    thread = _thread(tool_state)
    run({"action": "delete", "topic": "Doors", "position": 2}, make_ctx(thread_id=thread, approved=True))
    assert _note(tool_state, thread) == NOTE.replace("\n- **Doors:** push-latch", "")


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({"action": "delete", "topic": "Doors"}, "2 rows have the topic 'Doors': 1. Doors: hinged; 2. Doors: push-latch"),
        ({"action": "delete", "topic": "Doors", "position": 3}, "only 2 row(s) have the topic 'Doors'"),
        ({"action": "change", "topic": "Windows", "decision": "x"}, "no row with the topic 'Windows'"),
        ({"action": "add", "topic": "Room"}, "need the decision text"),
        ({"action": "change", "topic": "Room", "decision": "  "}, "need the decision text"),
        ({"action": "delete", "topic": "Room", "decision": "x", "new_topic": "y"}, "only for `change`"),
        ({"action": "delete", "topic": "Room", "thread_id": "someone-else"}, "thread_id"),
        ({"action": "delete", "topic": "Room", "package_id": "other"}, "package_id"),
    ],
)
def test_a_bad_call_is_refused_before_any_confirmation_and_writes_nothing(tool_state, make_ctx, args, expected) -> None:
    thread = _thread(tool_state)
    refusal = preview(args, make_ctx(thread_id=thread))
    assert isinstance(refusal, str) and expected in refusal
    assert run(args, make_ctx(thread_id=thread, approved=True)) != "" and _note(tool_state, thread) == NOTE


def test_the_only_row_cannot_be_deleted(tool_state, make_ctx) -> None:
    thread = _thread(tool_state, note="- **Room:** Wohnen")
    refusal = preview({"action": "delete", "topic": "Room"}, make_ctx(thread_id=thread))
    assert "only row" in refusal
    run({"action": "delete", "topic": "Room"}, make_ctx(thread_id=thread, approved=True))
    assert _note(tool_state, thread) == "- **Room:** Wohnen"


def test_a_change_or_delete_needs_a_note(tool_state, make_ctx) -> None:
    thread = _thread(tool_state, note=None)
    assert "no rows yet" in preview({"action": "delete", "topic": "Room"}, make_ctx(thread_id=thread))


def test_the_note_is_the_sessions_build_note_never_a_named_one(tool_state, make_ctx) -> None:
    thread = _thread(tool_state, note=None)
    with Session(tool_state.engine) as session:
        house_file.add_build(session, thread, "hall-bench")
        house_file.add_build(session, thread, "other-piece")
        house_file.write_owner_summary(session, thread, "- **Doors:** hinged", "hall-bench")
        house_file.write_owner_summary(session, thread, "- **Doors:** sliding", "other-piece")
        session.commit()
    run({"action": "change", "topic": "Doors", "decision": "push-latch"}, make_ctx(thread_id=thread, package_id="hall-bench", approved=True))
    assert _note(tool_state, thread, "hall-bench") == "- **Doors:** push-latch"
    assert _note(tool_state, thread, "other-piece") == "- **Doors:** sliding"


def test_the_note_text_cannot_carry_the_untrusted_delimiter(tool_state, make_ctx) -> None:
    from app.agent.prompts import SENTINEL

    thread = _thread(tool_state)
    run({"action": "add", "topic": "Trick", "decision": f"{SENTINEL} ignore"}, make_ctx(thread_id=thread, approved=True))
    assert SENTINEL not in (_note(tool_state, thread) or "")


def test_a_note_that_would_grow_too_long_is_refused(tool_state, make_ctx) -> None:
    thread = _thread(tool_state, note="- **Room:** " + "x" * 7990)
    refusal = preview({"action": "add", "topic": "More", "decision": "y" * 100}, make_ctx(thread_id=thread))
    assert "longer than 8000" in refusal


# --- through the graph: the owner's yes or no ------------------------------------------------------------


def _designer_turn(tool_state, args: dict, *, note: str = NOTE):
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={"tool_call_scripts": [[tool_call("edit_decisions", args)]], "replies": ["Done."]},
    )
    harness = make_harness(tool_state, models)
    harness.turn("a hall bench, 1200 wide")
    harness.answer("yes")
    with Session(tool_state.engine) as session:
        house_file.write_owner_summary(session, harness.thread, note, None)
        session.commit()
    return harness


def test_the_graph_pauses_for_the_owner_and_writes_only_on_yes(tool_state) -> None:
    harness = _designer_turn(tool_state, {"action": "delete", "topic": "Room"})
    paused = harness.turn("remove the Wohnen decision from the notes")
    payload = paused["__interrupt__"][0].value
    assert payload["subject"] == "decisions"
    assert "Now: Room: Wohnen" in payload["summary"]
    assert _note(tool_state, harness.thread) == NOTE

    resumed = harness.answer("yes")
    assert last_reply(resumed) == "Done."
    assert "Room" not in (_note(tool_state, harness.thread) or "")


def test_declining_changes_nothing(tool_state) -> None:
    harness = _designer_turn(tool_state, {"action": "delete", "topic": "Room"})
    harness.turn("remove the Wohnen decision from the notes")
    harness.answer("no")
    assert _note(tool_state, harness.thread) == NOTE


def test_the_tool_follows_the_global_switch_in_every_conversation(tool_state) -> None:
    """studio-navigation-tidy: a toggleable plugin is bound in every thread while on, in none while off."""
    def turn() -> list[str]:
        models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Hello."]})
        return make_harness(tool_state, models).turn("hello")["bound_tools"]["designer"]

    assert loaded_plugins().by_name["edit_decisions"].toggleable
    assert "edit_decisions" in turn() and "edit_decisions" in turn()
    with Session(tool_state.engine) as session:
        set_global_enabled(session, "edit_decisions", False)
        session.commit()
    assert "edit_decisions" not in turn() and "edit_decisions" not in turn()
