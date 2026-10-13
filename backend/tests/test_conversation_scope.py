"""conversation-projects: the room gate, naming a build, and the prompt scoped to the conversation."""

from __future__ import annotations

from app.agent import house_file
from app.agent.foreman import ROOM_QUESTION, last_reply
from app.agent.tools.base import ToolDeps
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness, place_in_room

SQUARE = [[0, 0], [3000, 0], [3000, 2000], [0, 2000]]


def decision(specialist: str) -> dict:
    return {"specialist": specialist, "reason": "test"}


def _house(tool_state) -> None:
    """Hall and Wohnen, three pieces: `hall-bench` and `shoe-rack` in Hall, `murphy-bed` nowhere."""
    with ToolDeps(tool_state).session() as session:
        hall = house_file.upsert_room(session, "Hall", SQUARE, 2500)
        house_file.upsert_room(session, "Wohnen", [[0, 0], [5000, 0], [5000, 4000], [0, 4000]], 2600)
        for package_id, name, room in (
            ("hall-bench", "Hall bench", hall),
            ("shoe-rack", "Shoe rack", hall),
            ("murphy-bed", "Oak queen Murphy bed", None),
        ):
            house_file.record_piece(session, package_id, name, room_id=room.id if room else None)
            house_file.record_version(session, package_id, 1)
        session.commit()


def _active(tool_state, harness) -> str | None:
    with ToolDeps(tool_state).session() as session:
        return house_file.get_thread(session, harness.thread).package_id


def _builds(tool_state, harness) -> list[str]:
    with ToolDeps(tool_state).session() as session:
        return sorted(b.package_id for b in house_file.builds_of(session, harness.thread))


# --- the room gate ----------------------------------------------------------------------


def test_a_new_wish_with_no_confirmed_room_asks_which_room_and_no_specialist_runs(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("intake")]})
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("I want a shoe bench")
    assert last_reply(state) == ROOM_QUESTION
    assert state["specialist"] == ""
    assert all(models[slot].calls == 0 for slot in ("intake", "designer", "builder"))
    assert ROOM_QUESTION in [m.content for m in harness.snapshot().values["messages"]]


def test_a_wish_naming_a_stored_room_goes_to_intake(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, intake={"replies": ["Is it 3000 × 2000?"]})
    state = make_harness(tool_state, models, room=None).turn("a shoe bench for the Hall")
    assert state["specialist"] == "intake"
    assert models["designer"].calls == 0


def test_the_answer_to_the_room_question_goes_to_intake(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("designer"), decision("designer")]},
        intake={"replies": ["How big is the attic?"]},
    )
    harness = make_harness(tool_state, models, room=None)
    assert last_reply(harness.turn("I want a shoe bench")) == ROOM_QUESTION
    state = harness.turn("the attic, 3 by 4 metres")
    assert state["specialist"] == "intake"
    assert last_reply(state) == "How big is the attic?"


def test_a_price_question_is_answered_without_a_confirmed_room(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("researcher")]}, researcher={"replies": ["An oak board costs 25 EUR."]}
    )
    state = make_harness(tool_state, models, room=None).turn("what does an oak board cost at toom?")
    assert state["specialist"] == "researcher"
    assert last_reply(state) == "An oak board costs 25 EUR."


def test_a_design_file_without_a_confirmed_room_gets_the_question_and_is_not_imported(tool_state, tmp_path) -> None:
    import io
    import json

    from langchain_core.messages import HumanMessage

    from app.agent import uploads
    from app.design_import import load_template

    tool_state.settings.upload_root = tmp_path / "uploads"
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Never."]})
    harness = make_harness(tool_state, models, room=None)
    with ToolDeps(tool_state).session() as session:
        upload_id = str(
            uploads.add_upload(
                session, tool_state.settings.upload_root, harness.thread,
                io.BytesIO(json.dumps(load_template()).encode("utf-8")),
                original_name="wall-unit.json", max_bytes=1_000_000, max_per_thread=10,
            ).id
        )
    state = harness.graph.invoke(
        {"messages": [HumanMessage("import this", additional_kwargs={"upload_ids": [upload_id]})]},
        config=harness.config,
    )
    assert last_reply(state) == ROOM_QUESTION
    assert models["designer"].calls == 0
    assert _builds(tool_state, harness) == []


# --- naming a build ---------------------------------------------------------------------


def test_naming_another_piece_on_a_bound_conversation_does_not_switch(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["900 mm."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="shoe-rack")
    state = harness.turn("back to the hall bench: make it 900 mm")
    assert state["specialist"] == "designer"
    assert state["package_id"] == "shoe-rack"
    assert _active(tool_state, harness) == "shoe-rack"
    assert last_reply(state) == "900 mm."


def test_an_unbound_conversation_binds_a_named_piece_with_no_conversation(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Which change?"]})
    harness = make_harness(tool_state, models)
    harness.start()
    place_in_room(harness, "murphy-bed")
    state = harness.turn("revise murphy-bed")
    assert _active(tool_state, harness) == "murphy-bed"
    assert state["package_id"] == "murphy-bed"
    assert state["specialist"] == "designer"
    assert last_reply(state) == "Which change?"


def test_an_unbound_conversation_refuses_a_piece_that_already_has_one(tool_state) -> None:
    from app.agent.foreman import PIECE_HAS_CONVERSATION

    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]})
    owner = make_harness(tool_state, fake_models())
    owner.start(package_id="murphy-bed")
    harness = make_harness(tool_state, models)
    harness.start()
    state = harness.turn("revise murphy-bed")
    assert last_reply(state) == PIECE_HAS_CONVERSATION.format(piece="murphy-bed")
    assert state["specialist"] == ""
    assert _active(tool_state, harness) is None
    assert models["designer"].calls == 0


def test_an_active_build_with_no_room_is_placed_by_intake_first(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, intake={"replies": ["Which room is the bed in?"]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="murphy-bed")
    with ToolDeps(tool_state).session() as session:
        house_file.set_piece_room(session, "murphy-bed", None)
        session.commit()
    state = harness.turn("revise it")
    assert state["specialist"] == "intake" and models["designer"].calls == 0


def test_an_active_build_in_another_room_is_placed_by_intake_first(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, intake={"replies": ["Move it to Wohnen?"]})
    harness = make_harness(tool_state, models, room="Wohnen")
    harness.start(package_id="hall-bench")
    place_in_room(harness, "hall-bench", "Hall")
    state = harness.turn("make it wider")
    assert state["specialist"] == "intake" and models["designer"].calls == 0


# --- the context the conversation carries -------------------------------------------------


def test_a_new_conversation_starts_without_the_room_or_any_piece(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("intake")]})
    harness = make_harness(tool_state, models, room=None)
    harness.turn("a second piece please")
    prompt = "\n".join(str(m.content) for m in models["foreman"].decision_prompts[-1])
    assert "No room is confirmed in this conversation yet." in prompt
    for name in ("Hall", "Wohnen", "hall-bench", "shoe-rack", "murphy-bed"):
        assert name not in prompt.replace("Hall bench", "")


def test_the_confirmed_room_gives_its_size_and_the_bound_piece_in_full(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Designing."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="hall-bench")
    with ToolDeps(tool_state).session() as session:
        # Legacy second build row: must not appear in the Designer's context.
        house_file.add_build(session, harness.thread, "shoe-rack")
        session.commit()
    harness.turn("make the bench deeper")
    prompt = models["designer"].last_prompt_text()
    assert "Hall: bounding box 3000 × 2000 mm, ceiling 2500 mm" in prompt
    assert "- hall-bench (Hall bench): v1" in prompt and "approved: none, room: Hall" in prompt
    assert "Other pieces in this conversation:" not in prompt
    assert "shoe-rack" not in prompt
    assert "murphy-bed" not in prompt and "Wohnen" not in prompt


def test_requests_reach_only_their_pieces_and_conversation(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Noted."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="hall-bench")
    other = make_harness(tool_state, fake_models(), room=None)
    with ToolDeps(tool_state).session() as session:
        house_file.record_extension_request(session, "inlay", "an inlay", package_id="hall-bench")
        house_file.record_extension_request(session, "bevel_mm", "a bevel", thread_id=harness.thread)
        house_file.record_extension_request(session, "carving", "carved doors", package_id="murphy-bed")
        house_file.record_extension_request(session, "old_field", "an old one")
        house_file.record_extension_request(session, "elsewhere", "somewhere else", thread_id=other.thread)
        session.commit()
    harness.turn("what is still open?")
    prompt = models["designer"].last_prompt_text()
    assert "inlay: an inlay" in prompt and "bevel_mm: a bevel" in prompt
    for absent in ("carving", "old_field", "elsewhere"):
        assert absent not in prompt


def test_only_the_confirmed_rooms_composition_is_listed(tool_state) -> None:
    _house(tool_state)
    with ToolDeps(tool_state).session() as session:
        for room in ("Hall", "Wohnen"):
            composition = house_file.record_composition(session, "room", room)
            house_file.record_composition_version(session, composition, 1, None, [])
        session.commit()
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Here."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="hall-bench")
    harness.turn("what is composed?")
    prompt = models["designer"].last_prompt_text()
    assert "- room Hall:" in prompt and "- room Wohnen:" not in prompt


def test_a_second_piece_starts_with_the_room_known_once_it_is_confirmed(tool_state) -> None:
    _house(tool_state)
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("intake")]},
        intake={
            "tool_call_scripts": [[tool_call("confirm_room", {"room": "Hall"})]],
            "replies": ["Hall it is.", "How wide?"],
        },
    )
    harness = make_harness(tool_state, models, room=None)
    paused = harness.turn("a piece for the Hall")
    assert paused["__interrupt__"][0].value["subject"] == "room"
    harness.answer("yes")
    harness.turn("a shoe bench")
    prompt = models["intake"].last_prompt_text()
    assert "Hall: bounding box 3000 × 2000 mm, ceiling 2500 mm" in prompt
    assert "murphy-bed" not in prompt and "No room is confirmed" not in prompt


def test_a_room_name_with_the_delimiter_is_neutralised(tool_state) -> None:
    from app.agent.prompts import CLOSE_TOKEN, neutralise

    name = f"Hall {CLOSE_TOKEN}"
    with ToolDeps(tool_state).session() as session:
        house_file.upsert_room(session, name, SQUARE, 2500)
        session.commit()
    models = fake_models(foreman={"decisions": [decision("intake")]}, intake={"replies": ["ok"]})
    harness = make_harness(tool_state, models, room=name)
    harness.turn("hello")
    prompt = models["intake"].last_prompt_text()
    assert f"{name}:" not in prompt
    assert f"{neutralise(name)}: bounding box 3000 × 2000 mm" in prompt
