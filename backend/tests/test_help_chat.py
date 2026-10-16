"""help-center: help questions reach Intake, which answers from `read_help`."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from sqlalchemy.orm import Session

from app.agent import chat, house_file
from app.agent.foreman import last_reply
from app.agent.tools import loaded_plugins
from app.plugins.enablement import EnablementRefused, set_thread_enabled
from app.plugins.loader import load_plugins
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness
from tests.test_chat_images import attach_design
from tests.test_foreman import _bind_piece


def helping(specialist: str = "designer") -> dict:
    return {"specialist": specialist, "reason": "test", "asks_help": True}


def _read_help(arguments: dict) -> str:
    return loaded_plugins().by_name["help"].tools["read_help"].run(arguments, None)  # type: ignore[arg-type]


def test_the_plugin_serves_intake_and_cannot_be_switched_off(tool_state) -> None:
    plugin = load_plugins().by_name["help"]
    assert plugin.agents == ("intake",)
    assert plugin.toggleable is False and plugin.enabled_by_default is True
    harness = make_harness(tool_state)
    with Session(tool_state.engine) as session, pytest.raises(EnablementRefused, match="not toggleable"):
        set_thread_enabled(session, loaded_plugins(), harness.thread, "help", False)


def test_read_help_lists_the_topics() -> None:
    listed = _read_help({})
    for line in ("- blueprint:", "- files:", "- template:", "- renders:", "- conversations:", "- workflow:"):
        assert line in listed


def test_read_help_returns_a_topic_inside_the_delimiters() -> None:
    text = _read_help({"topic": "template"})
    assert text.startswith("[[[UNTRUSTED_SOURCE") and 'url="help:template"' in text
    assert "Download the import template" in text and "JSON alone" in text


def test_read_help_refuses_an_unknown_topic_naming_it() -> None:
    text = _read_help({"topic": "pricing"})
    assert "'pricing'" in text and "blueprint, files, template, renders, conversations, workflow" in text


def test_a_help_question_in_a_new_thread_reaches_intake(tool_state) -> None:
    models = fake_models(foreman={"decisions": [helping()]}, intake={"replies": ["Download the template first."]})
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("How do I use the design template?")
    assert state["specialist"] == "intake"
    assert last_reply(state) != "Which room is this for?"
    assert models["designer"].calls == 0


def test_a_help_question_in_a_bound_thread_keeps_the_piece(tool_state) -> None:
    models = fake_models(foreman={"decisions": [helping("builder")]}, intake={"replies": ["A draft is quick."]})
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=True)
    state = harness.turn("What is the difference between a draft and a final render?")
    assert state["specialist"] == "intake"
    assert state["package_id"] == "hall-bench"
    assert models["builder"].calls == 0


def test_a_design_file_is_never_a_help_question(tool_state, tmp_path) -> None:
    tool_state.settings.upload_root = tmp_path / "uploads"
    models = fake_models(foreman={"decisions": [helping("intake")]})
    harness = make_harness(tool_state, models, room=None)
    design = attach_design(tool_state, harness.thread)
    state = harness.graph.invoke(
        {"messages": [HumanMessage("how does this work?", additional_kwargs={"upload_ids": [design]})]},
        config=harness.config,
    )
    assert last_reply(state) == "Which room is this for?"
    assert models["intake"].calls == 0


def test_a_help_turn_reads_the_help_and_records_nothing(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [helping()]},
        intake={
            "tool_call_scripts": [[tool_call("read_help", {"topic": "template"})]],
            "replies": ["Download the template, then give it to an AI chat with your photo."],
        },
    )
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("How do I turn a photo of a cabinet into a design?")
    read = next(m for m in reversed(models["intake"].prompts[-1]) if isinstance(m, ToolMessage))
    assert "Download the import template" in read.content
    assert chat.pending(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id) is None
    assert not state.get("brief") and not state.get("package_id")
    with Session(tool_state.engine) as session:
        assert house_file.thread_scope(session, harness.thread) == (None, None)
