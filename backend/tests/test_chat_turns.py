"""homeowner-chat: a turn, a confirmation round trip, a gateway failure, absent memory."""

from __future__ import annotations

import httpx2
import openai
from langchain_core.messages import ToolMessage

from app.agent import chat, house_file
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness

HALL = {
    "room_name": "Hall",
    "corners_mm": [[0, 0], [1200, 0], [1200, 3000], [0, 3000]],
    "ceiling_height_mm": 2400,
    "purpose": "a bench by the front door",
    "budget_eur": 400,
}


def decision(specialist: str = "intake") -> dict:
    return {"specialist": specialist, "reason": "test"}


def run_turn(harness, text: str) -> chat.TurnResult:
    return chat.answer(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id, message=text)


def run_resume(harness, answer: str, reason: str | None = None) -> chat.TurnResult:
    return chat.resume(
        harness.graph, thread_id=harness.thread, owner_id=harness.owner_id,
        answer_value=answer, reason=reason,
    )


def test_a_plain_turn_returns_the_reply_and_the_specialist(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision()]}, intake={"replies": ["How wide is the hall?"]})
    harness = make_harness(tool_state, models)
    result = run_turn(harness, "I want a bench for the hall")
    assert result == chat.TurnResult(reply="How wide is the hall?", specialist="intake")
    assert chat.pending(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id) is None
    assert [m["role"] for m in chat.history(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id)] == [
        "owner",
        "assistant",
    ]


def test_a_confirmation_round_trip_with_yes_writes_the_house_file(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision()]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved. Shall I design it?"]},
    )
    harness = make_harness(tool_state, models)

    paused = run_turn(harness, "a hall bench, 1200 wide, 2400 high, 400 euro")
    assert paused.pending is not None
    assert paused.pending.subject == "brief"
    assert "Room Hall: 1200 × 3000 mm" in paused.pending.summary
    assert paused.pending.proposal["brief"]["budget_eur"] == 400
    waiting = chat.pending(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id)
    assert waiting is not None and waiting.confirmation_id == paused.pending.confirmation_id

    done = run_resume(harness, "yes")
    assert done.pending is None
    assert done.reply == "Saved. Shall I design it?"
    from sqlalchemy.orm import Session

    with Session(harness.state.engine) as session:
        assert house_file.room_by_name(session, "Hall") is not None
        assert house_file.preferences(session)["budget_eur"] == "400"


def test_no_with_a_reason_writes_nothing_and_the_reason_reaches_the_specialist(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision()]},
        intake={
            "tool_call_scripts": [[tool_call("record_brief", HALL)]],
            "replies": ["Understood, what budget instead?"],
        },
    )
    harness = make_harness(tool_state, models, room="Studio")
    run_turn(harness, "a hall bench")
    declined = run_resume(harness, "no", reason="the budget is 250")
    assert declined.reply == "Understood, what budget instead?"

    from sqlalchemy.orm import Session

    with Session(harness.state.engine) as session:
        assert house_file.room_by_name(session, "Hall") is None
    tool_messages = [
        m for m in harness.snapshot().values["messages"] if isinstance(m, ToolMessage)
    ]
    assert tool_messages[-1].content == "The brief was not saved. Reason: the budget is 250"


def test_a_gateway_timeout_is_reported_and_leaves_no_unanswered_message(tool_state) -> None:
    timeout = openai.APITimeoutError(request=httpx2.Request("POST", "https://openrouter.ai/x"))
    models = fake_models(foreman={"decisions": [decision()]}, intake={"error": timeout})
    harness = make_harness(tool_state, models)

    result = run_turn(harness, "a bench please")

    assert result.failure_class == "timeout"
    assert result.reply is None
    assert chat.history(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id) == []


def test_a_later_turn_after_a_failure_works(tool_state) -> None:
    timeout = openai.APITimeoutError(request=httpx2.Request("POST", "https://openrouter.ai/x"))
    models = fake_models(
        foreman={"decisions": [decision(), decision()]},
        intake={"error": timeout, "replies": ["Hello again."]},
    )
    harness = make_harness(tool_state, models)
    run_turn(harness, "first")
    models["intake"].error = None
    result = run_turn(harness, "second")
    assert result.reply == "Hello again."
    assert [m["text"] for m in chat.history(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id)] == [
        "second",
        "Hello again.",
    ]


def test_absent_memory_is_a_stated_failure() -> None:
    from uuid import uuid4

    result = chat.answer(None, thread_id=uuid4(), owner_id=uuid4(), message="hello")
    assert result.failure_class == "unavailable"
    assert "memory is not available" in result.failure_reason
    result = chat.resume(None, thread_id=uuid4(), owner_id=uuid4(), answer_value="yes")
    assert result.failure_class == "unavailable"


def test_a_render_notice_is_shown_in_history_but_never_sent_to_a_model(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision(), decision()]},
        intake={"replies": ["How wide is the hall?", "Thanks."]},
    )
    harness = make_harness(tool_state, models)
    run_turn(harness, "I want a bench for the hall")
    words = "The draft turntable of hall-bench version 1 is ready. You can also check it in the Project panel."
    with tool_state_session(tool_state) as session:
        house_file.add_notice(
            session, harness.thread, after_messages=2, outcome="succeeded", tier="draft", text=words,
            package_id="hall-bench", version=1,
        )
        session.commit()
    run_turn(harness, "Two metres wide")

    for model in models.values():
        for prompt in model.prompts + model.decision_prompts:
            assert all(words not in str(message.content) for message in prompt)
    with tool_state_session(tool_state) as session:
        notices = house_file.notices_for(session, harness.thread)
    shown = chat.history(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id, notices=notices)
    assert [m["role"] for m in shown] == ["owner", "assistant", "notice", "owner", "assistant"]
    assert shown[2] == {
        "role": "notice", "kind": "render", "text": words, "outcome": "succeeded", "tier": "draft",
        "package_id": "hall-bench", "version": 1,
    }


def test_a_build_notice_is_shown_in_history_but_never_sent_to_a_model(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision(), decision()]},
        intake={"replies": ["How wide is the hall?", "Thanks."]},
    )
    harness = make_harness(tool_state, models)
    run_turn(harness, "I want a bench for the hall")
    words = "hall-bench version 2 is built."
    with tool_state_session(tool_state) as session:
        house_file.add_notice(
            session, harness.thread, after_messages=2, outcome="succeeded", kind="build", tier=None,
            text=words, package_id="hall-bench", version=2,
        )
        session.commit()
    run_turn(harness, "Two metres wide")

    for model in models.values():
        for prompt in model.prompts + model.decision_prompts:
            assert all(words not in str(message.content) for message in prompt)
    with tool_state_session(tool_state) as session:
        notices = house_file.notices_for(session, harness.thread)
    shown = chat.history(harness.graph, thread_id=harness.thread, owner_id=harness.owner_id, notices=notices)
    assert shown[2] == {
        "role": "notice", "kind": "build", "text": words, "outcome": "succeeded", "tier": None,
        "package_id": "hall-bench", "version": 2,
    }


def tool_state_session(tool_state):
    from app.agent.tools.base import ToolDeps

    return ToolDeps(tool_state).session()
