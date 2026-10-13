"""plugins: global and per-thread enablement reach the tools a specialist binds."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.agent.foreman import last_reply
from app.agent.tools import loaded_plugins
from app.plugins.enablement import (
    EnablementRefused,
    set_global_enabled,
    set_thread_enabled,
)
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness
from tests.test_foreman import HALL, decision


def _session(tool_state) -> Session:
    return Session(tool_state.engine)


def test_a_tool_switched_off_in_one_thread_only(tool_state) -> None:
    plugins = loaded_plugins()
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("intake")]},
        intake={"replies": ["Hello.", "Hello."]},
    )
    harness = make_harness(tool_state, models)
    thread_a = harness.thread
    with _session(tool_state) as session:
        set_thread_enabled(session, plugins, thread_a, "room_fit", False)
        session.commit()

    state_a = harness.turn("hello")
    assert "room_fit" not in state_a["bound_tools"]["designer"]
    assert "create_piece" in state_a["bound_tools"]["designer"]
    assert "cut_list" in state_a["bound_tools"]["designer"]

    harness.start()
    state_b = harness.turn("hello again")
    assert "room_fit" in state_b["bound_tools"]["designer"]


def test_a_non_toggleable_plugin_is_refused(tool_state) -> None:
    harness = make_harness(tool_state)
    with _session(tool_state) as session, pytest.raises(EnablementRefused, match="not toggleable"):
        set_thread_enabled(session, loaded_plugins(), harness.thread, "create_piece", False)


def test_a_globally_disabled_plugin_is_hidden_from_the_thread(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("intake")]}, intake={"replies": ["Hi."]})
    harness = make_harness(tool_state, models)
    with _session(tool_state) as session:
        set_global_enabled(session, "room_fit", False)
        session.commit()
    try:
        state = harness.turn("hello")
        assert "room_fit" not in state["bound_tools"]["designer"]
        assert "cut_list" in state["bound_tools"]["designer"]
    finally:
        with _session(tool_state) as session:
            set_global_enabled(session, "room_fit", True)
            session.commit()


def test_a_resumed_confirmation_keeps_the_turns_tools(tool_state) -> None:
    plugins = loaded_plugins()
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={"replies": ["Designing."]},
    )
    harness = make_harness(tool_state, models)
    harness.turn("a hall bench")
    assert "room_fit" in harness.snapshot().values["bound_tools"]["designer"]

    with _session(tool_state) as session:
        set_thread_enabled(session, plugins, harness.thread, "room_fit", False)
        session.commit()

    resumed = harness.answer("yes")
    assert "room_fit" in resumed["bound_tools"]["designer"]
    assert last_reply(resumed) == "Saved."

    next_turn = harness.turn("design it")
    assert "room_fit" not in next_turn["bound_tools"]["designer"]
    assert set(models["designer"].bound_tools) == {
        "create_piece", "import_design", "import_design_version", "revise_package", "rebuild_piece", "cut_list",
        "compose_room", "read_room_version_dimensions", "edit_decisions", "search_guidelines",
        "ask_owner",
    }
