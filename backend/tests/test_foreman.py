"""design-agents: Foreman routing, the specialists' loops, prompt shape, thread isolation."""

from __future__ import annotations

from dataclasses import replace

from langchain_core.messages import HumanMessage

from app.agent.foreman import MAX_TOOL_ROUNDS, last_reply
from app.agent.prompts import UNTRUSTED_CONTENT_PREAMBLE
from app.agent.tools.create_piece import run as create_run
from tests.api_helpers import desk
from tests.conftest import wait_for_status
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness

HALL = {
    "room_name": "Hall",
    "corners_mm": [[0, 0], [1200, 0], [1200, 3000], [0, 3000]],
    "ceiling_height_mm": 2400,
    "purpose": "a bench by the front door",
    "budget_eur": 400,
}


def decision(specialist: str) -> dict:
    return {"specialist": specialist, "reason": "test"}


def test_a_new_wish_with_no_piece_goes_to_intake_whatever_the_model_says(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("designer")]}, intake={"replies": ["Tell me more."]})
    state = make_harness(tool_state, models).turn("I want a bench")
    assert state["specialist"] == "intake"
    assert models["designer"].calls == 0


def test_the_builder_is_never_chosen_without_a_piece_with_a_version(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("builder")]}, intake={"replies": ["First a design."]})
    state = make_harness(tool_state, models).turn("render me a turntable")
    assert state["specialist"] == "intake"
    assert models["builder"].calls == 0
    assert last_reply(state) == "First a design."


def test_with_a_confirmed_brief_but_no_piece_the_builder_request_goes_to_the_designer(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("builder")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={"replies": ["Let me design it first."]},
    )
    harness = make_harness(tool_state, models)
    harness.turn("a hall bench, 1200 wide")
    harness.answer("yes")
    state = harness.turn("now render it")
    assert state["specialist"] == "designer"
    assert models["builder"].calls == 0


def test_a_bound_piece_with_a_version_lets_the_builder_answer(tool_state, make_ctx) -> None:
    create_run({"package_id": "bench", "spec": desk()}, replace(make_ctx(), approved=True))
    from app.blender import storage

    wait_for_status(storage.version_dir(tool_state.settings.render_root, "bench", 1))
    models = fake_models(foreman={"decisions": [decision("builder")]}, builder={"replies": ["Ready."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    state = harness.turn("show me the bench")
    assert state["specialist"] == "builder"
    assert last_reply(state) == "Ready."


def test_a_pending_confirmation_resumes_in_the_specialist_that_raised_it(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved. Shall I design it?"]},
    )
    harness = make_harness(tool_state, models)

    paused = harness.turn("a hall bench, 1200 wide, 2400 high, 400 euro")
    interrupts = harness.snapshot().interrupts
    assert len(interrupts) == 1
    assert interrupts[0].value["subject"] == "brief"
    assert models["intake"].calls == 1

    resumed = harness.answer("yes")
    assert last_reply(resumed) == "Saved. Shall I design it?"
    assert models["intake"].calls == 2
    assert models["foreman"].calls == 1          # not asked again on resume
    assert models["designer"].calls == 0
    assert paused is not None
    assert not harness.snapshot().interrupts


def test_the_round_cap_forces_a_text_answer_with_no_tools_bound(tool_state) -> None:
    loop_call = [tool_call("cut_list", {"package_id": "ghost"}, "c")]
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={
            "tool_call_scripts": [loop_call for _ in range(MAX_TOOL_ROUNDS + 3)],
            "replies": ["I could not finish; the cut list is still outstanding."],
        },
    )
    harness = make_harness(tool_state, models)
    harness.turn("hall bench")
    harness.answer("yes")
    state = harness.turn("list the parts of ghost")

    designer = models["designer"]
    assert designer.calls == MAX_TOOL_ROUNDS + 1
    assert designer.bound_tools == []
    assert "No further tool calls are available" in designer.last_prompt_text()
    assert last_reply(state) == "I could not finish; the cut list is still outstanding."


def test_the_prompt_carries_the_guard_once_and_binds_only_the_headers_tools(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={"replies": ["Designing."]},
    )
    harness = make_harness(tool_state, models)
    harness.turn("hall bench")
    harness.answer("yes")
    harness.turn("design it")

    system = str(models["designer"].prompts[-1][0].content)
    assert system.count(UNTRUSTED_CONTENT_PREAMBLE) == 1
    assert system.endswith(UNTRUSTED_CONTENT_PREAMBLE)
    assert set(models["designer"].bound_tools) == {"create_piece", "revise_package", "cut_list", "room_fit"}
    assert models["intake"].bound_tools == ["record_brief"]
    # The Foreman's own prompt is guarded and binds nothing.
    foreman_prompt = "\n".join(str(m.content) for m in models["foreman"].decision_prompts[-1])
    assert foreman_prompt.count(UNTRUSTED_CONTENT_PREAMBLE) == 1


def test_the_house_file_reaches_intake_and_the_designer_but_not_as_an_instruction(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={"replies": ["Designing."]},
    )
    harness = make_harness(tool_state, models)
    harness.turn("hall bench")
    harness.answer("yes")
    harness.turn("design it")
    assert "Hall: 1200 × 3000 mm, ceiling 2400 mm" in models["designer"].last_prompt_text()
    assert "budget_eur: 400" in models["designer"].last_prompt_text()


def test_two_threads_do_not_share_a_conversation(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("intake")]},
        intake={"replies": ["First answer.", "Second answer."]},
    )
    one = make_harness(tool_state, models)
    two = make_harness(tool_state, models)
    two.graph = one.graph  # the same compiled graph and checkpointer, two threads

    one.turn("a secret about the hall")
    two.turn("something else")

    second_prompt = "\n".join(str(m.content) for m in models["intake"].prompts[-1])
    assert "something else" in second_prompt
    assert "a secret about the hall" not in second_prompt
    assert [m.content for m in one.snapshot().values["messages"] if isinstance(m, HumanMessage)] == [
        "a secret about the hall"
    ]
