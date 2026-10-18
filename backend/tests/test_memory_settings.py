"""conversation-memory-settings: compression settings, the owner's note, compress-now, and memory settings."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.utils import trim_messages
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent import house_file, summaries
from app.agent.budget import HISTORY_OMITTED_NOTE, RequestBudget, count, fit
from app.agent.memory_settings import (
    DEFAULTS,
    read_memory_settings,
    reset_memory_setting,
    write_memory_settings,
)
from app.agent.prompts import wrap_summary
from app.agent.tools.base import ToolDeps
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.conftest import clean_house_file
from tests.graph_helpers import fake_models
from tests.test_budget import SYSTEM, _exchange
from tests.test_chat_api import install, start
from tests.test_summaries import Recorder, _messages


def _clear(engine) -> None:
    with Session(engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key = 'memory'"))
        session.commit()


@pytest.fixture
def engine(tool_state):
    _clear(tool_state.engine)
    yield tool_state.engine
    _clear(tool_state.engine)


# --- settings -----------------------------------------------------------------------------------


def test_without_a_stored_value_the_settings_are_todays_constants(engine) -> None:
    settings = read_memory_settings(engine)
    assert settings == DEFAULTS
    assert (settings.trigger_percent, settings.keep_turns, settings.note_tokens, settings.tool_result_chars) == (
        100, 0, 400, 300,
    )
    assert f"{settings.note_instructions} {summaries.FIXED_NOTE_RULES}" == summaries.SUMMARY_INSTRUCTION


def test_recent_inputs_default_to_five_and_are_stored_and_reset(engine) -> None:
    """conversation-recent-inputs: older settings without the key read the default."""
    from app.agent.memory_settings import reset_memory_setting

    assert read_memory_settings(engine).recent_inputs == 5
    assert write_memory_settings(engine, {"recent_inputs": 8}).recent_inputs == 8
    assert read_memory_settings(engine).recent_inputs == 8
    assert reset_memory_setting(engine, "recent_inputs").recent_inputs == 5


def test_version_verdicts_are_included_by_default_and_can_be_left_out(engine) -> None:
    """version-verdict: the slice switch for open verdicts."""
    assert read_memory_settings(engine).include_version_verdicts is True
    assert write_memory_settings(engine, {"include_version_verdicts": False}).include_version_verdicts is False
    assert reset_memory_setting(engine, "include_version_verdicts").include_version_verdicts is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trigger_percent", 40), ("keep_turns", 50), ("note_tokens", 50), ("tool_result_chars", 3000),
        ("render_ratings", 11), ("recent_inputs", 21), ("recent_inputs", -1),
    ],
)
def test_an_out_of_range_value_is_refused_naming_the_field(engine, field: str, value: int) -> None:
    with pytest.raises(ValidationError) as caught:
        write_memory_settings(engine, {field: value})
    assert caught.value.errors()[0]["loc"][0] == field
    assert read_memory_settings(engine) == DEFAULTS


def test_a_setting_is_stored_and_reset_to_its_default(engine) -> None:
    assert write_memory_settings(engine, {"note_tokens": 600}).note_tokens == 600
    assert read_memory_settings(engine).note_tokens == 600
    assert reset_memory_setting(engine, "note_tokens").note_tokens == 400


# --- fitting ------------------------------------------------------------------------------------


def _old_fit(budget: RequestBudget, system, history, summarize=None) -> list[BaseMessage]:
    """The fitting rule before these settings, kept here to hold the defaults to it."""
    index = max(i for i, m in enumerate(history) if isinstance(m, HumanMessage))
    earlier, current = list(history[:index]), list(history[index:])
    mandatory = count([*system, *current])
    usable = budget.usable
    if not earlier or mandatory + count(earlier) <= usable:
        return [*system, *earlier, *current]
    note_cost = count([SystemMessage(HISTORY_OMITTED_NOTE.format(count=len(earlier)))])
    remaining = max(0, usable - mandatory - note_cost)
    kept = trim_messages(
        earlier, max_tokens=remaining, token_counter=lambda m, **_k: count(m), strategy="last",
        start_on="human", include_system=False, allow_partial=False,
    ) if remaining > 0 else []
    dropped = earlier[: len(earlier) - len(kept)]
    if summarize is not None and dropped:
        summary = summarize(list(dropped))
        if summary and summary.strip():
            summarised = SystemMessage(wrap_summary(summary.strip()))
            if count([summarised]) <= note_cost + remaining - (count(kept) if kept else 0):
                return [*system, summarised, *kept, *current]
    omitted = sum(1 for m in dropped if isinstance(m, HumanMessage))
    return [*system, SystemMessage(HISTORY_OMITTED_NOTE.format(count=max(omitted, 1))), *kept, *current]


def _thread_of(turns: int) -> list[BaseMessage]:
    history: list[BaseMessage] = []
    for n in range(turns):
        history += _exchange(n)
    return [*history, HumanMessage("and the last board?", id="now")]


@pytest.mark.parametrize("turns", [2, 40])
@pytest.mark.parametrize("summary", [None, "Rooms: hall 1200 mm."])
def test_defaults_send_exactly_what_was_sent_before(turns: int, summary: str | None) -> None:
    history = _thread_of(turns)
    budget = RequestBudget(limit=3_000, output_reserve=500)
    summarize = (lambda _dropped: summary) if summary else None
    assert fit(budget, SYSTEM, history, summarize=summarize) == _old_fit(budget, SYSTEM, history, summarize)


def test_an_earlier_trigger_summarises_history_that_would_still_fit() -> None:
    history = _thread_of(6)
    budget = RequestBudget(limit=3_000, output_reserve=500)
    earlier = count(history[:-1])
    mandatory = count([*SYSTEM, history[-1]])
    share = (mandatory + earlier) * 100 // budget.usable
    assert share < 100  # it fits without a trigger
    seen: list[list[BaseMessage]] = []
    request = fit(
        budget, SYSTEM, history, summarize=lambda d: seen.append(d) or "notes", trigger_percent=max(50, share - 10)
    )
    assert seen and seen[0][0].id == "h0"
    assert request[len(SYSTEM)].content.startswith(wrap_summary("notes")[:20])


def test_only_the_recent_inputs_are_sent_and_older_ones_go_to_the_note() -> None:
    """conversation-recent-inputs: the cut applies even when everything would fit."""
    history = _thread_of(40)
    budget = RequestBudget(limit=200_000, output_reserve=500)
    seen: list[list[BaseMessage]] = []
    request = fit(budget, SYSTEM, history, summarize=lambda d: seen.append(d) or "notes", recent_inputs=5)
    [dropped] = seen
    assert dropped[0].id == "h0" and dropped[-1].id == "a34"
    assert request[len(SYSTEM)].content.startswith(wrap_summary("notes")[:20])
    assert [m.id for m in request[len(SYSTEM) + 1 :]] == [
        *[f"{kind}{n}" for n in range(35, 40) for kind in ("h", "a")], "now",
    ]


def test_a_short_thread_is_sent_whole_without_a_note() -> None:
    history = _thread_of(3)
    budget = RequestBudget(limit=200_000, output_reserve=500)
    seen: list = []
    request = fit(budget, SYSTEM, history, summarize=lambda d: seen.append(d) or "notes", recent_inputs=5)
    assert seen == [] and request == [*SYSTEM, *history]


@pytest.mark.parametrize("turns", [3, 40])
def test_recent_inputs_zero_is_todays_request(turns: int) -> None:
    history = _thread_of(turns)
    budget = RequestBudget(limit=3_000, output_reserve=500)
    summarize = lambda _d: "notes"
    assert fit(budget, SYSTEM, history, summarize=summarize, recent_inputs=0) == fit(
        budget, SYSTEM, history, summarize=summarize
    )


def test_the_recent_cut_never_splits_a_tool_call_from_its_result() -> None:
    from langchain_core.messages import ToolMessage

    from tests.test_budget import _tool_exchange

    history = [m for n in range(10) for m in _tool_exchange(n)] + [HumanMessage("and now?", id="now")]
    request = fit(RequestBudget(limit=200_000, output_reserve=500), SYSTEM, history,
                  summarize=lambda _d: "notes", recent_inputs=2)
    sent = request[len(SYSTEM) + 1 :]
    assert isinstance(sent[0], HumanMessage) and sent[0].id == "h8"
    calls = {c["id"] for m in sent if isinstance(m, AIMessage) for c in m.tool_calls}
    assert all(m.tool_call_id in calls for m in sent if isinstance(m, ToolMessage))


def test_the_kept_turns_are_sent_in_full() -> None:
    history = _thread_of(40)
    budget = RequestBudget(limit=6_000, output_reserve=500)
    request = fit(budget, SYSTEM, history, summarize=lambda _d: "notes", keep_turns=3)
    ids = [m.id for m in request]
    for n in (37, 38, 39):
        assert f"h{n}" in ids and f"a{n}" in ids


def test_exchanges_a_note_covers_are_replaced_even_when_they_fit() -> None:
    history = _thread_of(3)
    budget = RequestBudget(limit=32_000, output_reserve=500)
    seen: list[list[BaseMessage]] = []
    request = fit(budget, SYSTEM, history, summarize=lambda d: seen.append(d) or "notes", covered_through="a1")
    assert [m.id for m in seen[0]] == ["h0", "a0", "h1", "a1"]
    ids = [m.id for m in request]
    assert "h0" not in ids and "h2" in ids and request[-1].id == "now"


# --- the note -----------------------------------------------------------------------------------


def test_an_owner_correction_survives_a_refresh(engine) -> None:
    thread_id = _thread_with(engine)
    summaries.summary_for(engine, thread_id, Recorder("doors: hinged"), _messages(2))
    with Session(engine) as session:
        house_file.write_owner_summary(session, thread_id, "doors: push-latch")
        session.commit()
    call = Recorder("doors: push-latch; shelves: 4")
    assert summaries.summary_for(engine, thread_id, call, _messages(4)) == "doors: push-latch; shelves: 4"
    system, sent, _max = call.calls[0]
    assert summaries.OWNER_EDITED_RULE in system and "Earlier summary:\ndoors: push-latch" in sent
    with Session(engine) as session:
        assert house_file.summary_owner_edited(session, thread_id)


def test_the_fixed_rules_follow_any_edited_instructions(engine) -> None:
    write_memory_settings(engine, {"note_instructions": "Only list the wood.", "note_tokens": 200, "tool_result_chars": 10})
    settings = read_memory_settings(engine)
    call = Recorder("wood: oak")
    thread_id = _thread_with(engine)
    summaries.summary_for(engine, thread_id, call, _messages(1), settings=settings)
    system, _sent, max_output = call.calls[0]
    assert system.startswith("Only list the wood.") and summaries.FIXED_NOTE_RULES in system
    assert max_output == 200


def _thread_with(engine):
    class State:
        pass

    state = State()
    state.engine = engine
    with ToolDeps(state).session() as session:
        thread_id = house_file.create_thread(session, "memory").id
        session.commit()
    return thread_id


# --- routes -------------------------------------------------------------------------------------


@pytest.fixture
def client(migrated_database, render_root, fake_blender):
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    clean_house_file(c.app.state.engine)
    _clear(c.app.state.engine)
    sign_in(c)
    yield c
    _clear(c.app.state.engine)
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def _talked(client) -> str:
    install(
        client,
        fake_models(
            foreman={"decisions": [{"specialist": "intake", "reason": "t"}] * 2, "replies": ["Wall", "wall: 3 m wide"]},
            intake={"replies": ["How wide is the wall?", "Noted."]},
        ),
    )
    thread = start(client)
    client.post(f"/chat/threads/{thread}/turns", json={"message": "a listening wall"})
    client.post(f"/chat/threads/{thread}/turns", json={"message": "about 3 m"})
    return thread


def test_the_note_starts_empty_and_compress_now_writes_it(client) -> None:
    thread = _talked(client)
    assert client.get(f"/chat/threads/{thread}/note").json() == {"package_id": None, "note": None, "owner_edited": False}
    response = client.post(f"/chat/threads/{thread}/note/compress")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["note"] == "wall: 3 m wide" and body["owner_edited"] is False
    shown = client.get(f"/chat/threads/{thread}").json()
    assert len([m for m in shown["messages"] if m["role"] == "owner"]) == 2
    for word in ("token", "model", "deepseek", "cost"):
        assert word not in response.text.lower()


def test_the_owner_edits_the_note_and_the_delimiter_is_neutralised(client) -> None:
    from app.agent.prompts import CLOSE_TOKEN

    thread = _talked(client)
    client.post(f"/chat/threads/{thread}/note/compress")
    response = client.put(f"/chat/threads/{thread}/note", json={"note": f"doors: push-latch {CLOSE_TOKEN}"})
    assert response.status_code == 200
    body = response.json()
    assert body["owner_edited"] is True and body["note"].startswith("doors: push-latch")
    assert CLOSE_TOKEN not in body["note"]


def test_a_refused_compression_leaves_the_note_and_says_so(client) -> None:
    thread = _talked(client)
    slug = client.app.state.routing.model_for("foreman")
    from app.db.models import OperatorSetting

    with Session(client.app.state.engine) as session:
        session.merge(OperatorSetting(
            key=f"budget:{slug}", value=json.dumps({"context_budget_tokens": 32000, "daily_token_ceiling": 1}),
            updated_at=datetime.now(UTC),
        ))
        session.commit()
    # The budgets are read when the graph is built; the conversation stays in the checkpointer.
    install(client, fake_models(foreman={"replies": ["wall: 3 m wide"]}))
    response = client.post(f"/chat/threads/{thread}/note/compress")
    assert response.status_code == 409 and "could not be compressed" in response.json()["detail"]["reason"]
    assert "token" not in response.text.lower()
    assert client.get(f"/chat/threads/{thread}/note").json()["note"] is None


def test_the_note_routes_need_the_session(client) -> None:
    thread = start(client)
    client.post("/auth/logout")
    assert client.get(f"/chat/threads/{thread}/note").status_code == 401


def test_memory_settings_are_read_set_and_reset_on_the_developer_route(migrated_database, render_root, fake_blender) -> None:
    from tests.test_admin_models_api import _client

    c = _client(migrated_database, render_root, fake_blender, dev=True)
    _clear(c.app.state.engine)
    try:
        sign_in(c)
        body = c.get("/admin/memory").json()
        assert body["settings"]["trigger_percent"] == 100 and body["fixed_rules"]
        assert c.put("/admin/memory", json={"trigger_percent": 75}).json()["settings"]["trigger_percent"] == 75
        refused = c.put("/admin/memory", json={"keep_turns": 50})
        assert refused.status_code == 422 and refused.json()["detail"]["field"] == "keep_turns"
        assert c.get("/admin/memory").json()["settings"]["keep_turns"] == 0
        assert c.delete("/admin/memory/trigger_percent").json()["settings"]["trigger_percent"] == 100
        assert c.put("/admin/memory", json={"bogus": 1}).json()["detail"]["field"] == "bogus"
    finally:
        _clear(c.app.state.engine)
        c.__exit__(None, None, None)
    off = _client(migrated_database, render_root, fake_blender, dev=False)
    try:
        sign_in(off)
        assert off.get("/admin/memory").status_code == 404
    finally:
        off.__exit__(None, None, None)


def _seq(messages: Sequence[BaseMessage]) -> list[str | None]:
    return [m.id for m in messages]


def test_kept_turns_start_counts_owner_turns() -> None:
    from app.agent.budget import kept_turns_start

    messages = [HumanMessage("a", id="h0"), AIMessage("b", id="a0"), HumanMessage("c", id="h1"), AIMessage("d", id="a1")]
    assert kept_turns_start(messages, 0) == 4 and kept_turns_start(messages, 1) == 2 and kept_turns_start(messages, 5) == 0
    assert _seq(messages[kept_turns_start(messages, 1):]) == ["h1", "a1"]


# --- what the conversation sees and what is saved ------------------------------------------------


def test_other_builds_can_be_hidden(tool_state, engine) -> None:
    from tests.graph_helpers import make_harness
    from tests.test_foreman import _bind_stored_piece, decision

    write_memory_settings(engine, {"other_builds": "hidden"})
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Here it is."]})
    harness = make_harness(tool_state, models)
    _bind_stored_piece(tool_state, harness)
    harness.turn("what does the hall bench look like now?")
    system = str(models["designer"].prompts[-1][0].content)
    assert "Piece hall-bench v1:" in system and "shoe-rack" not in system


def test_fewer_ratings_are_given_when_set(tool_state, engine, make_ctx) -> None:
    from tests.graph_helpers import make_harness
    from tests.test_foreman import _build_piece, _rate, decision

    write_memory_settings(engine, {"render_ratings": 2})
    _build_piece(tool_state, make_ctx)
    for index in range(5):
        _rate(tool_state, f"comment {index}", minutes=50 - index)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Ok."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    harness.turn("tweak it")
    text = models["designer"].last_prompt_text()
    assert [f"comment {i}" in text for i in range(5)] == [False, False, False, True, True]


def test_preferences_are_not_saved_when_switched_off(make_ctx, tool_deps, engine) -> None:
    from dataclasses import replace

    from app.agent.tools.record_brief import run as record_brief
    from tests.test_record_brief import HALL

    write_memory_settings(engine, {"save_preferences": False})
    record_brief(HALL, replace(make_ctx(), approved=True))
    with tool_deps.session() as session:
        assert house_file.room_by_name(session, "Hall") is not None
        assert house_file.preferences(session) == {}


def test_extension_requests_are_saved_whatever_the_settings(make_ctx, tool_state, tool_deps, engine) -> None:
    from app.agent.tools.revise_package import preview
    from tests.test_revise_package import make_piece

    write_memory_settings(engine, {"include_extension_requests": False, "save_preferences": False})
    make_piece(make_ctx, tool_state)
    preview({"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"bevel_mm": 3}}}}, make_ctx())
    with tool_deps.session() as session:
        assert [r.field for r in house_file.open_extension_requests(session)] == ["modules.cabinet.bevel_mm"]


# --- "Add to decisions": one message compressed into a row (homeowner-chat) --------------------


def test_an_answer_is_parsed_into_a_capped_validated_row() -> None:
    from app.agent.decision_summary import DECISION_MAX_CHARS, parse_row

    row = parse_row("**Topic:** Door latch\nDecision: Use a push-latch, 18 mm.")
    assert (row.topic, row.decision) == ("Door latch", "Use a push-latch, 18 mm.")
    assert len(parse_row("Topic: a\nDecision: " + "x" * 5000).decision) == DECISION_MAX_CHARS
    assert parse_row("Decision: no topic line") is None
    assert parse_row("") is None


def test_a_message_is_compressed_to_a_row_and_nothing_is_written(client) -> None:
    thread = _talked(client)
    install(client, fake_models(foreman={"replies": ["Topic: Wall width\nDecision: The wall is 3 m wide."]}))
    response = client.post(f"/chat/threads/{thread}/note/decision", json={"text": "A very long message " * 50})
    assert response.status_code == 200, response.text
    assert response.json() == {"topic": "Wall width", "decision": "The wall is 3 m wide."}
    assert client.get(f"/chat/threads/{thread}/note").json()["note"] is None
    for word in ("token", "deepseek", "cost"):
        assert word not in response.text.lower()


def test_a_refused_or_failed_summary_gives_an_empty_row(client) -> None:
    from app.db.models import OperatorSetting

    thread = _talked(client)
    slug = client.app.state.routing.model_for("foreman")
    with Session(client.app.state.engine) as session:
        session.merge(OperatorSetting(
            key=f"budget:{slug}", value=json.dumps({"context_budget_tokens": 32000, "daily_token_ceiling": 1}),
            updated_at=datetime.now(UTC),
        ))
        session.commit()
    install(client, fake_models(foreman={"replies": ["Topic: x\nDecision: y"]}))
    response = client.post(f"/chat/threads/{thread}/note/decision", json={"text": "hello"})
    assert response.status_code == 200 and response.json() == {"topic": "", "decision": ""}
    assert client.get(f"/chat/threads/{thread}/note").json()["note"] is None


def test_the_decision_route_checks_the_session_and_the_text(client) -> None:
    thread = start(client)
    assert client.post(f"/chat/threads/{thread}/note/decision", json={"text": ""}).status_code == 422
    assert client.post(f"/chat/threads/{thread}/note/decision", json={"text": "x" * 9000}).status_code == 422
    client.post("/auth/logout")
    assert client.post(f"/chat/threads/{thread}/note/decision", json={"text": "hi"}).status_code == 401


# --- the recent inputs in a real graph (conversation-recent-inputs) -----------------------------------


def _decision(specialist: str) -> dict:
    return {"specialist": specialist, "reason": "test"}


def test_agents_and_routing_get_only_the_recent_inputs_and_the_note(tool_state, engine) -> None:
    from tests.graph_helpers import make_harness

    models = fake_models(
        foreman={"decisions": [_decision("intake")] * 8, "replies": ["NOTE: hall bench 1200 mm."] * 20},
        intake={"replies": [f"noted {n}" for n in range(8)]},
    )
    harness = make_harness(tool_state, models)
    for n in range(8):
        harness.turn(f"owner input {n}")

    agent_sent = "\n".join(str(m.content) for m in models["intake"].prompts[-1])
    for n in range(2):
        assert f"owner input {n}" not in agent_sent  # older than the 5 recent inputs
    for n in range(2, 8):
        assert f"owner input {n}" in agent_sent  # inputs 2-6 are the 5 recent ones, 7 is current
    assert "NOTE: hall bench 1200 mm." in agent_sent

    routing_sent = "\n".join(str(m.content) for m in models["foreman"].decision_prompts[-1])
    assert "owner input 0" not in routing_sent and "owner input 7" in routing_sent
    assert "NOTE: hall bench 1200 mm." in routing_sent  # the stored note, read only


def test_routing_never_writes_a_note(tool_state, engine) -> None:


    with ToolDeps(tool_state).session() as session:
        thread = house_file.create_thread(session, "test")
        session.commit()
        thread_id = thread.id
    note = summaries.stored_note(engine, thread_id)
    assert note([HumanMessage("old", id="h0")]) is None  # nothing stored: the shortened-history note is sent
    with Session(engine) as session:
        assert house_file.read_summary(session, thread_id, None)[0] in (None, "")


def test_the_setting_off_sends_the_whole_short_history(tool_state, engine) -> None:
    from tests.graph_helpers import make_harness

    write_memory_settings(engine, {"recent_inputs": 0})
    models = fake_models(foreman={"decisions": [_decision("intake")] * 8}, intake={"replies": ["ok"] * 8})
    harness = make_harness(tool_state, models)
    for n in range(8):
        harness.turn(f"owner input {n}")
    agent_sent = "\n".join(str(m.content) for m in models["intake"].prompts[-1])
    assert all(f"owner input {n}" in agent_sent for n in range(8))
