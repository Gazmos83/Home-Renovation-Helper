"""design-agents: Intake and the Designer ask questions through `ask_owner`."""

from __future__ import annotations

from langchain_core.messages import ToolMessage

from app.agent import chat
from app.agent.foreman import ONE_AT_A_TIME_NOTE
from app.plugins.loader import load_plugins
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness
from tests.test_foreman import HALL, decision

TWO = {
    "questions": [
        {"text": "Ceiling height?", "unit": "mm"},
        {"text": "Budget?", "unit": "EUR"},
    ]
}


def _intake_asks(tool_state, *calls, replies=("Thanks, noted.",)):
    models = fake_models(
        foreman={"decisions": [decision("intake")]},
        intake={"tool_call_scripts": [list(calls)], "replies": list(replies)},
    )
    harness = make_harness(tool_state, models)
    harness.start()
    return models, harness


def _pending(harness) -> chat.Pending | None:
    return chat.pending(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id)


def test_the_plugin_serves_intake_and_the_designer_and_cannot_be_switched_off() -> None:
    plugin = load_plugins().by_name["ask_owner"]
    assert plugin.agents == ("intake", "designer")
    assert plugin.toggleable is False and plugin.enabled_by_default is True


def test_a_valid_set_pauses_the_turn_with_the_questions(tool_state) -> None:
    _models, harness = _intake_asks(tool_state, tool_call("ask_owner", TWO))
    harness.turn("a hall bench")

    pending = _pending(harness)
    assert pending is not None and pending.kind == "questions"
    assert pending.questions == [
        {"text": "Ceiling height?", "unit": "mm", "choices": []},
        {"text": "Budget?", "unit": "EUR", "choices": []},
    ]
    assert pending.subject == "" and pending.proposal == {}


def test_answers_return_to_intake_in_the_same_turn_and_stay_in_the_history(tool_state) -> None:
    models, harness = _intake_asks(tool_state, tool_call("ask_owner", TWO))
    harness.turn("a hall bench")
    result = chat.final_result(chat.resume_events(
        harness.graph, thread_id=harness.thread, owner_id=harness.owner_id, value={"answers": ["2500", "900"]},
    ))
    assert result.reply == "Thanks, noted." and result.pending is None

    tool_result = next(m for m in reversed(models["intake"].prompts[-1]) if isinstance(m, ToolMessage))
    assert "1. Ceiling height? → 2500 mm" in tool_result.content
    assert "2. Budget? → 900 EUR" in tool_result.content

    shown = chat.history(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id)
    assert shown[-2] == {
        "role": "assistant",
        "kind": "answers",
        "text": "",
        "rows": [
            {"question": "Ceiling height?", "answer": "2500 mm"},
            {"question": "Budget?", "answer": "900 EUR"},
        ],
    }
    assert shown[-1] == {"role": "assistant", "text": "Thanks, noted."}


def test_a_declined_set_returns_the_owners_words(tool_state) -> None:
    models, harness = _intake_asks(tool_state, tool_call("ask_owner", TWO), replies=("Measure tomorrow, then.",))
    harness.turn("a hall bench")
    result = chat.final_result(chat.resume_events(
        harness.graph, thread_id=harness.thread, owner_id=harness.owner_id,
        value={"declined": "I'll measure tomorrow"},
    ))
    assert result.pending is None
    tool_result = next(m for m in reversed(models["intake"].prompts[-1]) if isinstance(m, ToolMessage))
    assert "I'll measure tomorrow" in tool_result.content
    shown = chat.history(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id)
    assert {"role": "owner", "text": "I'll measure tomorrow"} in shown


def test_nine_questions_are_refused_to_the_model_and_nothing_is_pending(tool_state) -> None:
    nine = {"questions": [{"text": f"Question {n}?"} for n in range(9)]}
    models, harness = _intake_asks(tool_state, tool_call("ask_owner", nine))
    harness.turn("a hall bench")

    assert _pending(harness) is None
    refusal = next(m for m in reversed(models["intake"].prompts[-1]) if isinstance(m, ToolMessage))
    assert "questions" in refusal.content and "at most 8" in refusal.content


def test_bad_choices_are_refused_naming_the_field(tool_state) -> None:
    one_choice = {"questions": [{"text": "Wood?", "choices": ["oak"]}]}
    models, harness = _intake_asks(tool_state, tool_call("ask_owner", one_choice))
    harness.turn("a hall bench")
    assert _pending(harness) is None
    refusal = next(m for m in reversed(models["intake"].prompts[-1]) if isinstance(m, ToolMessage))
    assert "questions.0.choices" in refusal.content


def test_an_ask_after_a_gated_call_in_the_same_round_is_not_run(tool_state) -> None:
    models, harness = _intake_asks(
        tool_state, tool_call("record_brief", HALL), tool_call("ask_owner", TWO), replies=("Saved.",)
    )
    harness.turn("a hall bench")
    pending = _pending(harness)
    assert pending is not None and pending.kind == "confirmation" and pending.subject == "brief"

    harness.answer("yes")
    assert _pending(harness) is None
    results = [m for m in models["intake"].prompts[-1] if isinstance(m, ToolMessage)]
    assert results[-1].content == ONE_AT_A_TIME_NOTE
