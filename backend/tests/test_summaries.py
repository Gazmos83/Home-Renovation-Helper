"""token-budget: a thread's summary is made, reused, refreshed and never recursive."""

from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent import house_file, summaries
from app.agent.budget import BudgetRefused
from app.agent.prompts import SUMMARY_LABEL
from app.agent.tools.base import ToolDeps
from tests.graph_helpers import fake_models, make_harness
from tests.test_foreman import decision


def _thread(tool_state):
    with ToolDeps(tool_state).session() as session:
        thread_id = house_file.create_thread(session, "summaries").id
        session.commit()
    return thread_id


def _messages(count: int) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for n in range(count):
        out += [HumanMessage(f"hall is {1000 + n} mm", id=f"h{n}"), AIMessage(f"noted {n}", id=f"a{n}")]
    return out


class Recorder:
    def __init__(self, answer: str = "Rooms: hall 1200 mm.") -> None:
        self.answer = answer
        self.calls: list[tuple[str, str, int]] = []

    def __call__(self, system, messages, max_output) -> str:
        self.calls.append((system, messages[0].content, max_output))
        return self.answer


def test_a_summary_is_made_once_and_reused_with_no_call(tool_state) -> None:
    thread_id = _thread(tool_state)
    call = Recorder()
    dropped = _messages(3)

    assert summaries.summary_for(tool_state.engine, thread_id, call, dropped) == "Rooms: hall 1200 mm."
    assert len(call.calls) == 1
    system, text, max_output = call.calls[0]
    assert system == summaries.SUMMARY_INSTRUCTION and max_output == summaries.SUMMARY_OUTPUT_TOKENS == 400
    assert "Owner: hall is 1000 mm" in text and "Assistant: noted 2" in text

    with ToolDeps(tool_state).session() as session:
        assert house_file.read_summary(session, thread_id) == ("Rooms: hall 1200 mm.", "a2")
    assert summaries.summary_for(tool_state.engine, thread_id, call, dropped) == "Rooms: hall 1200 mm."
    assert len(call.calls) == 1


def test_a_refresh_sends_the_stored_summary_and_only_the_new_exchanges(tool_state) -> None:
    thread_id = _thread(tool_state)
    summaries.summary_for(tool_state.engine, thread_id, Recorder("Rooms: hall 1000 mm."), _messages(2))
    call = Recorder("Rooms: hall 1000 mm; desk planned.")

    assert summaries.summary_for(tool_state.engine, thread_id, call, _messages(4)) == "Rooms: hall 1000 mm; desk planned."
    text = call.calls[0][1]
    assert "Earlier summary:\nRooms: hall 1000 mm." in text
    assert "hall is 1002 mm" in text and "hall is 1001 mm" not in text
    with ToolDeps(tool_state).session() as session:
        assert house_file.read_summary(session, thread_id)[1] == "a3"


def test_a_refused_summary_call_gives_none_and_stores_nothing(tool_state) -> None:
    thread_id = _thread(tool_state)

    def refused(system, messages, max_output):
        raise BudgetRefused("daily_limit", 100, 50)

    assert summaries.summary_for(tool_state.engine, thread_id, refused, _messages(2)) is None
    with ToolDeps(tool_state).session() as session:
        assert house_file.read_summary(session, thread_id) == (None, None)


def test_a_long_thread_is_summarised_for_the_call_and_stored_unchanged(tool_state) -> None:
    """Default budgets: messages of ~48k characters push earlier turns out of a 32k budget."""
    big = "the hall wall is 1200 mm and the bench sits under the window " * 800
    models = fake_models(
        foreman={"decisions": [decision("researcher")] * 4, "replies": ["Rooms: hall 1200 mm."] * 20},
        researcher={"replies": ["ok"] * 4},
    )
    harness = make_harness(tool_state, models)
    harness.start()
    for n in range(4):
        harness.turn(f"turn {n}: {big}")

    researcher_prompt = models["researcher"].prompts[-1]
    summary = next(m for m in researcher_prompt if isinstance(m, SystemMessage) and m.content.startswith(SUMMARY_LABEL))
    assert "Rooms: hall 1200 mm." in summary.content
    assert not any("earlier exchange(s)" in str(m.content) for m in researcher_prompt)

    # The stored conversation still holds every message.
    stored = harness.snapshot().values["messages"]
    assert [m.content.split(":")[0] for m in stored if isinstance(m, HumanMessage)] == [f"turn {n}" for n in range(4)]

    # A summary call is never itself summarised.
    summary_prompts = [p for p in models["foreman"].prompts if p and p[0].content == summaries.SUMMARY_INSTRUCTION]
    assert summary_prompts
    for prompt in summary_prompts:
        assert not any(isinstance(m, SystemMessage) and SUMMARY_LABEL in str(m.content) for m in prompt[1:])


def test_a_summary_is_kept_per_build_and_switching_brings_the_builds_own_back(tool_state) -> None:
    thread_id = _thread(tool_state)
    with ToolDeps(tool_state).session() as session:
        house_file.add_build(session, thread_id, "hall-bench")
        house_file.add_build(session, thread_id, "shoe-rack")
        session.commit()
    bench, rack = Recorder("bench: oak, 900 mm"), Recorder("rack: pine")

    assert summaries.summary_for(tool_state.engine, thread_id, bench, _messages(2), "hall-bench") == "bench: oak, 900 mm"
    assert summaries.summary_for(tool_state.engine, thread_id, rack, _messages(3), "shoe-rack") == "rack: pine"
    assert "Piece: hall-bench" in bench.calls[0][1] and "Piece: shoe-rack" in rack.calls[0][1]

    # Back to the bench: its own summary is reused with no model call.
    again = Recorder("never asked")
    assert summaries.summary_for(tool_state.engine, thread_id, again, _messages(2), "hall-bench") == "bench: oak, 900 mm"
    assert again.calls == []
    with ToolDeps(tool_state).session() as session:
        assert house_file.read_summary(session, thread_id, "hall-bench") == ("bench: oak, 900 mm", "a1")
        assert house_file.read_summary(session, thread_id, "shoe-rack") == ("rack: pine", "a2")
        assert house_file.read_summary(session, thread_id) == (None, None)


def test_without_an_active_build_the_threads_own_summary_is_used(tool_state) -> None:
    thread_id = _thread(tool_state)
    call = Recorder("no build yet: hall 1200 mm")
    assert summaries.summary_for(tool_state.engine, thread_id, call, _messages(2)) == "no build yet: hall 1200 mm"
    assert "Piece:" not in call.calls[0][1]
    with ToolDeps(tool_state).session() as session:
        assert house_file.read_summary(session, thread_id) == ("no build yet: hall 1200 mm", "a1")


def test_the_instruction_asks_to_keep_only_the_named_piece() -> None:
    assert "When a piece is named, keep only what concerns that piece." in summaries.SUMMARY_INSTRUCTION
