"""view-piece-in-room: placement questions, the hand-off to the Builder and the routing."""

from __future__ import annotations

from langgraph.types import Command

from app.agent import house_file
from app.agent.foreman import ROOM_QUESTION, last_reply
from app.agent.tools.base import ToolDeps
from app.blender import storage
from app.packages import service
from app.packages.placements import read_placement
from plugins.ask_placement.tool import WALL_QUESTION
from tests.api_helpers import desk
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness

WOHNEN = [[0, 0], [6000, 0], [6000, 3000], [3000, 4500], [0, 3000]]
WANTS = "I would like to view this in the room"


def viewing(specialist: str = "designer") -> dict:
    return {"specialist": specialist, "reason": "test", "views_in_room": True}


def _built_bench(tool_state) -> None:
    root = tool_state.settings.render_root
    service.create_version(root, "bench", desk(), lambda version: None)
    folder = storage.version_dir(root, "bench", 1)
    storage.write_status(folder, status="succeeded")
    (folder / "model.blend").write_bytes(b"")
    with ToolDeps(tool_state).session() as session:
        house_file.upsert_room(session, "Wohnen", WOHNEN, 2600)
        house_file.record_piece(session, "bench", "Bench")
        house_file.record_version(session, "bench", 1)
        session.commit()


def _harness(tool_state, models, room: str | None = "Wohnen"):
    _built_bench(tool_state)
    harness = make_harness(tool_state, models, room=room)
    harness.start(package_id="bench")
    return harness


def _stored(tool_state):
    return read_placement(storage.version_dir(tool_state.settings.render_root, "bench", 1), "Wohnen")


def test_a_first_view_asks_where_to_place_it_and_renders_nothing(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [viewing("builder")]},
        designer={"tool_call_scripts": [[tool_call("ask_placement", {})]], "replies": ["Placed."]},
    )
    harness = _harness(tool_state, models)
    state = harness.turn(WANTS)
    assert state["specialist"] == "designer"
    asked = state["__interrupt__"][0].value
    assert asked["kind"] == "questions" and asked["tool"] == "ask_placement"
    assert asked["layout"] == "room"
    assert asked["questions"][0]["text"] == WALL_QUESTION
    assert asked["questions"][0]["choices"][0] == "Wall 1 (6000 mm)"
    assert models["builder"].calls == 0
    prompt = "\n".join(str(m.content) for m in models["designer"].prompts[0])
    assert "Call ask_placement now" in prompt


def test_answering_the_placement_stores_it_and_hands_the_turn_to_the_builder(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [viewing()]},
        designer={"tool_call_scripts": [[tool_call("ask_placement", {})]], "replies": ["Placed on wall 1."]},
        builder={"replies": ["A draft still in Wohnen is on its way."]},
    )
    harness = _harness(tool_state, models)
    harness.turn(WANTS)
    state = harness.graph.invoke(Command(resume={"answers": ["Wall 1 (6000 mm)", "300"]}), config=harness.config)
    assert _stored(tool_state)["left_mm"] == 300
    assert state["specialist"] == "builder"
    assert last_reply(state) == "A draft still in Wohnen is on its way."
    prompt = "\n".join(str(m.content) for m in models["builder"].prompts[0])
    assert 'tier "draft" and in_room true' in prompt


def test_a_place_that_does_not_fit_is_not_handed_to_the_builder(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [viewing()]},
        designer={"tool_call_scripts": [[tool_call("ask_placement", {})]], "replies": ["That is too wide there."]},
    )
    harness = _harness(tool_state, models)
    harness.turn(WANTS)
    state = harness.graph.invoke(Command(resume={"answers": ["Wall 2 (3000 mm)", "2900"]}), config=harness.config)
    assert _stored(tool_state) is None
    assert state["specialist"] == "designer"
    assert models["builder"].calls == 0


def test_a_saved_place_goes_straight_to_the_builder(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [viewing(), viewing()]},
        designer={"tool_call_scripts": [[tool_call("ask_placement", {})]], "replies": ["Placed."]},
        builder={"replies": ["Started.", "Started again."]},
    )
    harness = _harness(tool_state, models)
    harness.turn(WANTS)
    harness.graph.invoke(Command(resume={"answers": ["Wall 1 (6000 mm)", "300"]}), config=harness.config)
    designer_calls = models["designer"].calls
    state = harness.turn("show it in the room again")
    assert state["specialist"] == "builder"
    assert "__interrupt__" not in state
    assert models["designer"].calls == designer_calls


def test_a_conversation_that_declined_a_room_is_asked_which_room(tool_state) -> None:
    models = fake_models(foreman={"decisions": [viewing()]})
    harness = _harness(tool_state, models, room=None)
    with ToolDeps(tool_state).session() as session:
        house_file.decline_room(session, harness.thread)
        session.commit()
    state = harness.turn(WANTS)
    assert last_reply(state) == ROOM_QUESTION
    assert models["designer"].calls == 0 and models["builder"].calls == 0
