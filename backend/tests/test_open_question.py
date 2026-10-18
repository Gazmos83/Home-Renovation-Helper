"""open-question-first-turn: an open question is answered before the room offer."""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.foreman import ROOM_OFFER, last_reply
from app.agent.prompts import OPEN_QUESTION_NOTE
from tests.graph_helpers import fake_models, make_harness
from tests.test_chat_images import attach_design


def asking(**flags: bool) -> dict:
    return {"specialist": "designer", "reason": "test", "open_question": True, **flags}


def wishing() -> dict:
    return {"specialist": "designer", "reason": "test"}


def test_brainstorming_in_a_new_conversation(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [asking()]},
        designer={"replies": ["A kitchen counter is usually about 900 mm high."]},
    )
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("I'd like to build a kitchen counter, how tall should it be?")
    assert state["specialist"] == "designer"
    assert last_reply(state) == "A kitchen counter is usually about 900 mm high."
    assert models["designer"].bound_tools == ["search_guidelines"]
    assert OPEN_QUESTION_NOTE in models["designer"].last_prompt_text()
    assert not state.get("package_id")
    with Session(tool_state.engine) as session:
        assert house_file.thread_scope(session, harness.thread) == (None, None)


def test_the_wish_after_the_question_gets_the_room_offer(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [asking(), wishing()]},
        designer={"replies": ["About 900 mm."]},
    )
    harness = make_harness(tool_state, models, room=None)
    harness.turn("I'd like to build a kitchen counter, how tall should it be?")
    state = harness.turn("OK, design me one 900 mm high")
    assert last_reply(state) == ROOM_OFFER
    assert models["designer"].calls == 1
    assert not state.get("open_question_turn")


def test_a_request_phrased_as_a_question_is_not_brainstorming(tool_state) -> None:
    models = fake_models(foreman={"decisions": [wishing()]})
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("Can you design a shoe bench for me?")
    assert last_reply(state) == ROOM_OFFER
    assert models["designer"].calls == 0


def test_a_file_is_never_an_open_question(tool_state, tmp_path) -> None:
    tool_state.settings.upload_root = tmp_path / "uploads"
    models = fake_models(foreman={"decisions": [asking()]})
    harness = make_harness(tool_state, models, room=None)
    design = attach_design(tool_state, harness.thread)
    state = harness.graph.invoke(
        {"messages": [HumanMessage("is this a good height?", additional_kwargs={"upload_ids": [design]})]},
        config=harness.config,
    )
    assert last_reply(state) == ROOM_OFFER
    assert models["designer"].calls == 0


def test_help_keeps_its_place(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [asking(asks_help=True)]},
        intake={"replies": ["Download the template from the Pieces page."]},
    )
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("how do I download the design template?")
    assert state["specialist"] == "intake"
    assert models["designer"].calls == 0


def test_an_open_question_with_a_confirmed_room_is_routed_as_before(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [asking()]},
        intake={"replies": ["What would you like to build?"]},
    )
    harness = make_harness(tool_state, models)
    state = harness.turn("what height works for a counter?")
    assert not state.get("open_question_turn")
