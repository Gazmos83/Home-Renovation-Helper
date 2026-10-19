"""place-piece-from-owner-words, benchmark (deterministic): the owner's own placement sentence
is taken as given and ends in the room proposal, never a render offer.

The live replay of the same sentence on the real models is `tests/test_benchmark_agents.py`.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.types import Command

from app.agent import house_file
from app.agent.tools.base import ToolDeps
from tests.fakes import tool_call
from tests.graph_helpers import fake_models
from tests.test_view_in_room import _harness, _stored, viewing

SENTENCE = "Please place the sideboard along wall 2 0 mm from wall 3."
STATED = {"wall": 2, "distance_mm": 0, "from_wall": 3}


def _models():
    return fake_models(
        foreman={"decisions": [viewing("builder")]},
        designer={"tool_call_scripts": [
            [tool_call("ask_placement", STATED)],
            [tool_call("compose_room", {"with_saved_place": True})],
            [tool_call("approve_version", {})],
            [tool_call("compose_room", {"with_saved_place": True})],
        ]},
    )


def _called(state) -> list[str]:
    return [
        call["name"] for m in state["messages"] if isinstance(m, AIMessage) for call in (m.tool_calls or [])
    ]


def _no_render(state, models) -> None:
    assert "render_turntable" not in _called(state)
    assert models["builder"].calls == 0
    replies = [str(m.content) for m in state["messages"] if isinstance(m, AIMessage)]
    assert not any("render" in reply.lower() for reply in replies)


def test_a_stated_place_is_saved_without_questions_and_the_room_is_proposed(tool_state) -> None:
    models = _models()
    harness = _harness(tool_state, models)
    with ToolDeps(tool_state).session() as session:
        house_file.approve_version(session, "bench", 1)
        session.commit()
    state = harness.turn(SENTENCE)
    asked = state["__interrupt__"][0].value
    assert asked["kind"] == "confirmation" and asked["subject"] == "compose_room"
    assert _stored(tool_state)["wall"] == 1 and _stored(tool_state)["left_mm"] == 0
    assert state["specialist"] == "designer"
    _no_render(state, models)


def test_an_unapproved_version_is_approved_first_then_the_room_is_proposed(tool_state) -> None:
    models = _models()
    harness = _harness(tool_state, models)
    state = harness.turn(SENTENCE)
    asked = state["__interrupt__"][0].value
    assert asked["kind"] == "confirmation" and asked["subject"] == "approve_version"
    assert _stored(tool_state)["left_mm"] == 0
    state = harness.graph.invoke(Command(resume={"answer": "yes"}), config=harness.config)
    assert state["__interrupt__"][0].value["subject"] == "compose_room"
    _no_render(state, models)
