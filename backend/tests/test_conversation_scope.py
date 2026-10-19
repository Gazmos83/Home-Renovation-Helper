"""conversation-projects: the room gate, naming a build, and the prompt scoped to the conversation."""

from __future__ import annotations

import pytest

from app.agent import house_file
from app.agent.foreman import ROOM_OFFER, ROOM_QUESTION, last_reply
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


def test_a_new_wish_with_no_confirmed_room_offers_a_room_and_no_specialist_runs(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("intake")]})
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("I want a shoe bench")
    assert last_reply(state) == ROOM_OFFER
    assert state["specialist"] == ""
    assert all(models[slot].calls == 0 for slot in ("intake", "designer", "builder"))
    assert ROOM_OFFER in [m.content for m in harness.snapshot().values["messages"]]


# --- the room offer (optional-room-question) ---------------------------------------------


def _declined(tool_state, harness) -> bool:
    with ToolDeps(tool_state).session() as session:
        return house_file.get_thread(session, harness.thread).room_declined


@pytest.mark.parametrize("answer", ["yes", "Yes!", "ja", "Sure, why not", "ok", "Okay."])
def test_a_yes_to_the_offer_asks_which_room(tool_state, answer: str) -> None:
    models = fake_models(foreman={"decisions": [decision("intake"), decision("intake")]})
    harness = make_harness(tool_state, models, room=None)
    assert last_reply(harness.turn("I want a shoe bench")) == ROOM_OFFER
    state = harness.turn(answer)
    assert last_reply(state) == ROOM_QUESTION
    assert state["specialist"] == ""
    assert models["intake"].calls == 0
    assert not _declined(tool_state, harness)


def test_naming_the_room_in_the_answer_goes_to_intake(tool_state) -> None:
    _house(tool_state)
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("intake")]}, intake={"replies": ["Is it 5000 × 4000?"]},
    )
    harness = make_harness(tool_state, models, room=None)
    harness.turn("I want a shoe bench")
    state = harness.turn("yes, Wohnen")
    assert state["specialist"] == "intake"
    assert last_reply(state) == "Is it 5000 × 4000?"
    assert not _declined(tool_state, harness)


def test_a_no_records_the_decline_and_intake_answers(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("intake"), decision("designer")]},
        intake={"replies": ["What is the bench for?", "Noted."]},
    )
    harness = make_harness(tool_state, models, room=None)
    harness.turn("I want a shoe bench")
    state = harness.turn("no")
    assert state["specialist"] == "intake"
    assert last_reply(state) == "What is the bench for?"
    assert _declined(tool_state, harness)
    assert "the owner chose not to view this piece in a room" in state["facts"]
    # Not asked again: a later turn is routed by the other rules.
    state = harness.turn("make it 10 cm wider")
    assert last_reply(state) not in (ROOM_OFFER, ROOM_QUESTION)
    assert state["specialist"] == "intake"


def test_a_vague_answer_counts_as_no(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("intake"), decision("intake")]}, intake={"replies": ["Fine."]})
    harness = make_harness(tool_state, models, room=None)
    harness.turn("I want a shoe bench")
    harness.turn("maybe later")
    assert _declined(tool_state, harness)


def test_an_unassigned_piece_in_a_declined_conversation_goes_to_the_designer(tool_state) -> None:
    _house(tool_state)
    models = fake_models(
        foreman={"decisions": [decision("designer"), decision("designer"), decision("designer")]},
        designer={"replies": ["Shall I?", "Revised."]},
    )
    harness = make_harness(tool_state, models, room=None)
    harness.start(package_id="murphy-bed")
    assert last_reply(harness.turn("make it wider")) == ROOM_OFFER
    harness.turn("no")
    state = harness.turn("make it 10 cm wider")
    assert state["specialist"] == "designer"
    assert last_reply(state) == "Revised."
    assert models["intake"].calls == 0


def test_a_wish_naming_a_stored_room_goes_to_intake(tool_state) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, intake={"replies": ["Is it 3000 × 2000?"]})
    state = make_harness(tool_state, models, room=None).turn("a shoe bench for the Hall")
    assert state["specialist"] == "intake"
    assert models["designer"].calls == 0


def test_the_answer_to_the_room_question_goes_to_intake(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("designer"), decision("designer"), decision("designer")]},
        intake={"replies": ["How big is the attic?"]},
    )
    harness = make_harness(tool_state, models, room=None)
    assert last_reply(harness.turn("I want a shoe bench")) == ROOM_OFFER
    assert last_reply(harness.turn("yes")) == ROOM_QUESTION
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
    assert last_reply(state) == ROOM_OFFER
    assert models["designer"].calls == 0
    assert _builds(tool_state, harness) == []


def test_declining_the_room_hands_the_design_file_to_the_designer(tool_state, tmp_path) -> None:
    models = fake_models(
        foreman={"decisions": [decision("designer"), decision("intake")]}, designer={"replies": ["Imported."]},
    )
    harness = make_harness(tool_state, models, room=None)
    upload_id = _attach(tool_state, harness, tmp_path, name="lamellen-kommode.json")
    models["designer"].tool_call_scripts.append(
        [tool_call("import_design", {"upload_id": upload_id, "package_id": "lamellen-kommode"})]
    )
    assert last_reply(_send(harness, "import this", upload_id)) == ROOM_OFFER
    state = harness.turn("no")
    assert state["specialist"] == "designer"
    assert state["__interrupt__"][0].value["subject"] == "import_design"
    prompt = "\n".join(str(m.content) for m in models["designer"].prompts[0])
    assert f"'lamellen-kommode.json' as upload {upload_id} and chose not to view the piece in a room" in prompt
    assert _builds(tool_state, harness) == []
    state = harness.answer("yes")
    assert _active(tool_state, harness) == "lamellen-kommode"
    with ToolDeps(tool_state).session() as session:
        assert house_file.piece_room_name(session, "lamellen-kommode") is None


# --- a design file attached before the room (pending-design-import) ---------------------


def _attach(
    tool_state, harness, tmp_path, name: str = "kommode-harmony.json", kind: str = "design", design_name: str | None = None
) -> str:
    import io
    import json

    from app.agent import uploads
    from app.design_import import load_template
    from tests.test_review_evidence import _png

    tool_state.settings.upload_root = tmp_path / "uploads"
    if kind == "design":
        # The bare design form: the test is about the hand-off, not the template's guide.
        build = load_template()["build"]
        if design_name is not None:
            build["name"] = design_name
        content = json.dumps(build).encode("utf-8")
    else:
        _png(tmp_path / "photo.png")
        content = (tmp_path / "photo.png").read_bytes()
    with ToolDeps(tool_state).session() as session:
        return str(
            uploads.add_upload(
                session, tool_state.settings.upload_root, harness.thread, io.BytesIO(content),
                original_name=name, max_bytes=1_000_000, max_per_thread=10,
            ).id
        )


def _send(harness, text: str, *upload_ids: str):
    from langchain_core.messages import HumanMessage

    return harness.graph.invoke(
        {"messages": [HumanMessage(text, additional_kwargs={"upload_ids": list(upload_ids)})]},
        config=harness.config,
    )


def _room_confirming(tool_state, tmp_path, *, designer: dict | None = None):
    """A new conversation whose first message attached a design file and got the room question;
    Intake will offer `Wohnen` with `confirm_room`."""
    _house(tool_state)
    models = fake_models(
        foreman={"decisions": [decision("designer"), decision("designer"), decision("intake"), decision("designer")]},
        intake={"steps": [[tool_call("confirm_room", {"room": "Wohnen"})], "This conversation now works in Wohnen."]},
        designer=designer or {},
    )
    harness = make_harness(tool_state, models, room=None)
    upload_id = _attach(tool_state, harness, tmp_path)
    assert last_reply(_send(harness, "I'd like to view this dresser", upload_id)) == ROOM_OFFER
    assert last_reply(harness.turn("yes")) == ROOM_QUESTION
    return harness, models, upload_id


def test_confirming_the_room_hands_the_earlier_design_file_to_the_designer(tool_state, tmp_path) -> None:
    harness, models, upload_id = _room_confirming(tool_state, tmp_path, designer={"replies": ["Imported; it is building."]})
    models["designer"].tool_call_scripts.append(
        [tool_call("import_design", {"upload_id": upload_id, "package_id": "kommode"})]
    )
    state = harness.turn("Wohnen")
    assert state["__interrupt__"][0].value["subject"] == "room"
    state = harness.answer("yes")
    # The same turn goes on to the Designer, which raises the import preview.
    assert state["specialist"] == "designer"
    assert state["__interrupt__"][0].value["subject"] == "import_design"
    assert _builds(tool_state, harness) == []
    prompt = "\n".join(str(m.content) for m in models["designer"].prompts[0])
    assert f"'kommode-harmony.json' as upload {upload_id} before the room was confirmed" in prompt
    assert "room Wohnen" in prompt
    assert "No room is confirmed in this conversation yet." not in prompt

    state = harness.answer("yes")
    assert last_reply(state) == "Imported; it is building."
    assert _active(tool_state, harness) == "kommode"


def test_a_declined_room_confirmation_ends_with_intake(tool_state, tmp_path) -> None:
    harness, models, _upload_id = _room_confirming(tool_state, tmp_path)
    models["intake"].steps[1] = "Which room, then?"
    harness.turn("Wohnen")
    state = harness.answer("no")
    assert state["specialist"] == "intake"
    assert "__interrupt__" not in state
    assert models["designer"].calls == 0


def test_a_declined_import_is_not_offered_again(tool_state, tmp_path) -> None:
    harness, models, upload_id = _room_confirming(tool_state, tmp_path, designer={"replies": ["Not imported."]})
    models["designer"].tool_call_scripts.append(
        [tool_call("import_design", {"upload_id": upload_id, "package_id": "kommode"})]
    )
    harness.turn("Wohnen")
    harness.answer("yes")
    harness.answer("no")
    assert _active(tool_state, harness) is None
    designer_calls = models["designer"].calls
    models["intake"].replies.append("What would you like there?")
    state = harness.turn("what else could go here?")
    assert state["pending_design"] is None
    assert "__interrupt__" not in state
    assert models["designer"].calls == designer_calls


def test_a_conversation_with_a_piece_does_not_hand_off(tool_state, tmp_path) -> None:
    _house(tool_state)
    models = fake_models(
        foreman={"decisions": [decision("intake")]},
        intake={"steps": [[tool_call("confirm_room", {"room": "Hall"})], "This conversation now works in Hall."]},
    )
    harness = make_harness(tool_state, models, room=None)
    harness.start(package_id="hall-bench")
    upload_id = _attach(tool_state, harness, tmp_path)
    state = _send(harness, "the Hall, please", upload_id)
    assert state["pending_design"] is None
    state = harness.answer("yes")
    assert state["specialist"] == "intake"
    assert models["designer"].calls == 0


def test_a_brief_naming_a_room_hands_off_too(tool_state, tmp_path) -> None:
    models = fake_models(
        foreman={"decisions": [decision("designer"), decision("designer"), decision("intake")]},
        intake={
            "steps": [
                [
                    tool_call(
                        "record_brief",
                        {
                            "room_name": "Hall",
                            "corners_mm": [[0, 0], [1200, 0], [1200, 3000], [0, 3000]],
                            "ceiling_height_mm": 2400,
                            "purpose": "a dresser",
                        },
                    )
                ],
                "The brief is saved.",
            ]
        },
        designer={"replies": ["Shall I import it?"]},
    )
    harness = make_harness(tool_state, models, room=None)
    upload_id = _attach(tool_state, harness, tmp_path)
    assert last_reply(_send(harness, "I'd like to view this dresser", upload_id)) == ROOM_OFFER
    assert last_reply(harness.turn("yes")) == ROOM_QUESTION
    harness.turn("the hall, 1.2 by 3 metres, 2.4 high")
    state = harness.answer("yes")
    assert state["specialist"] == "designer"
    assert last_reply(state) == "Shall I import it?"


# --- a design file named like an existing piece (delete-piece) ----------------------------


def test_a_file_named_like_an_existing_piece_is_answered_by_code(tool_state, tmp_path) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Never."]})
    harness = make_harness(tool_state, models, room=None)
    state = _send(harness, "import this", _attach(tool_state, harness, tmp_path, name="murphy-bed.json"))
    reply = last_reply(state)
    assert reply.startswith("The attached design `murphy-bed.json` matches your piece Oak queen Murphy bed (`murphy-bed`).")
    assert "name murphy-bed here and attach the file again" in reply
    assert "delete Oak queen Murphy bed on the Pieces page" in reply
    assert 'reply "keep both" with a new name for the design' in reply
    assert ROOM_OFFER not in reply and ROOM_QUESTION not in reply
    assert state["specialist"] == ""
    assert all(models[slot].calls == 0 for slot in ("foreman", "intake", "designer"))
    assert _builds(tool_state, harness) == []


def _matched(tool_state, tmp_path, designer: dict, foreman_decisions: list | None = None):
    """A new conversation whose first message attached `murphy-bed.json` and got the fixed reply."""
    _house(tool_state)
    models = fake_models(foreman={"decisions": foreman_decisions or [decision("intake")]}, designer=designer)
    harness = make_harness(tool_state, models, room=None)
    upload_id = _attach(tool_state, harness, tmp_path, name="murphy-bed.json")
    assert last_reply(_send(harness, "import this", upload_id)).startswith("The attached design `murphy-bed.json`")
    return harness, models, upload_id


def test_keep_both_with_a_new_name_goes_to_the_designer_with_the_file(tool_state, tmp_path) -> None:
    harness, models, upload_id = _matched(tool_state, tmp_path, {"replies": ["Imported."]})
    models["designer"].tool_call_scripts.append(
        [tool_call("import_design", {"upload_id": upload_id, "package_id": "guest-bed", "name": "Guest bed"})]
    )
    state = harness.turn("Keep both, call it Guest bed")
    assert state["specialist"] == "designer"
    assert models["foreman"].calls == 0
    prompt = "\n".join(str(m.content) for m in models["designer"].prompts[0])
    assert f"'murphy-bed.json' as upload {upload_id}. It matches an existing piece" in prompt
    assert '"Keep both, call it Guest bed"' in prompt
    assert state["__interrupt__"][0].value["subject"] == "import_design"
    harness.answer("yes")
    assert _active(tool_state, harness) == "guest-bed"
    with ToolDeps(tool_state).session() as session:
        names = {p["package_id"]: p["name"] for p in house_file.pieces(session, tool_state.settings.render_root)}
    assert names["guest-bed"] == "Guest bed" and names["murphy-bed"] == "Oak queen Murphy bed"


def test_keep_both_without_a_name_lets_the_designer_ask(tool_state, tmp_path) -> None:
    harness, models, _upload_id = _matched(tool_state, tmp_path, {"replies": ["What should the new piece be called?"]})
    state = harness.turn("beide behalten")
    assert state["specialist"] == "designer"
    prompt = "\n".join(str(m.content) for m in models["designer"].prompts[0])
    assert "If the reply gives no new name, ask for one" in prompt
    assert last_reply(state) == "What should the new piece be called?"
    assert _builds(tool_state, harness) == []


def test_another_answer_to_the_fixed_reply_routes_as_before(tool_state, tmp_path) -> None:
    harness, models, _upload_id = _matched(tool_state, tmp_path, {})
    state = harness.turn("what does it cost?")
    assert state["keep_both_design"] is None
    assert models["foreman"].calls == 1


def test_a_matching_piece_with_a_conversation_points_to_it(tool_state, tmp_path) -> None:
    _house(tool_state)
    with ToolDeps(tool_state).session() as session:
        house_file.create_thread(session, "Bench", package_id="hall-bench")
        session.commit()
    harness = make_harness(tool_state, fake_models(foreman={"decisions": [decision("designer")]}), room=None)
    reply = last_reply(_send(harness, "import this", _attach(tool_state, harness, tmp_path, name="hall-bench.json")))
    assert "attach the file in its conversation (Pieces page → Hall bench)" in reply


def test_the_name_inside_the_design_matches_a_piece(tool_state, tmp_path) -> None:
    _house(tool_state)
    harness = make_harness(tool_state, fake_models(foreman={"decisions": [decision("designer")]}), room=None)
    upload_id = _attach(tool_state, harness, tmp_path, name="export.json", design_name="shoe RACK")
    reply = last_reply(_send(harness, "import this", upload_id))
    assert "`export.json` matches your piece Shoe rack (`shoe-rack`)" in reply


def test_a_file_matching_no_piece_is_handled_as_before(tool_state, tmp_path) -> None:
    _house(tool_state)
    harness = make_harness(tool_state, fake_models(foreman={"decisions": [decision("designer")]}), room=None)
    state = _send(harness, "import this", _attach(tool_state, harness, tmp_path, name="lamellen-kommode.json"))
    assert state["design_matches_piece"] is None
    assert last_reply(state) == ROOM_OFFER


def test_a_conversation_bound_to_the_matching_piece_gets_no_conflict_reply(tool_state, tmp_path) -> None:
    _house(tool_state)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Shall I import it?"]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="hall-bench")
    state = _send(harness, "import this", _attach(tool_state, harness, tmp_path, name="hall-bench.json"))
    assert state["design_matches_piece"] is None
    assert "matches your piece" not in last_reply(state)


def test_the_pending_file_is_the_newest_design_and_ignores_images(tool_state, tmp_path) -> None:
    models = fake_models(foreman={"decisions": [decision("designer"), decision("designer")]})
    harness = make_harness(tool_state, models, room=None)
    older = _attach(tool_state, harness, tmp_path, "older.json")
    newer = _attach(tool_state, harness, tmp_path, "newer.json")
    photo = _attach(tool_state, harness, tmp_path, "room.png", kind="image")
    _send(harness, "these two", older, newer)
    state = _send(harness, "and a photo", photo)
    assert state["pending_design"] == {"upload_id": newer, "name": "newer.json"}


def test_no_file_is_pending_once_the_room_is_confirmed(tool_state, tmp_path) -> None:
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Importing."]})
    harness = make_harness(tool_state, models)
    upload_id = _attach(tool_state, harness, tmp_path)
    state = _send(harness, "import this", upload_id)
    assert state["pending_design"] is None
    assert state["specialist"] == "designer"


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
