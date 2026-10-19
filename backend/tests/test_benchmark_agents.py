"""agent-benchmark: core owner sentences replayed through the real routed models.

Skipped unless `--benchmark` is passed; it spends a few cents on OpenRouter per case. Each case
seeds its own house file in the test database, runs one owner turn through the real Foreman
graph with the models routed for each slot, and checks observable outcomes only: the pause
shown, the state stored, the tools called and words that must not appear. Builds are stubbed
(no Blender) and no confirmation is answered, so nothing is created, built or rendered.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import house_file
from app.agent.foreman import build_graph, last_reply
from app.agent.models.budgets import Budgets
from app.agent.models.profiles import Profiles
from app.agent.models.routing import load_routing, read_routing_overrides
from app.agent.models.slots import build_slot_models
from app.agent.tools.base import ToolDeps
from app.blender import storage
from app.config import load_settings
from app.db.session import make_engine
from app.packages import service
from app.packages.placements import read_placement, write_placement
from tests.api_helpers import desk
from tests.graph_helpers import Harness

pytestmark = pytest.mark.benchmark

# The owner's Wohnen outline: five walls, counter-clockwise.
WOHNEN = [[0, 0], [6000, 0], [6000, 3000], [3000, 4500], [0, 3000]]


@pytest.fixture
def live_harness(tool_state):
    """A harness on the test database whose slots use the real routed models."""
    live = load_settings()
    if live.openrouter_api_key.get_secret_value().strip() in ("", "change-me", "sk-or-v1-change-me"):
        pytest.skip("OPENROUTER_API_KEY is not set")
    # The owner's /admin routing overrides are read from the app's database; nothing is written there.
    routing = load_routing(overrides=read_routing_overrides(make_engine(str(live.database_url))))
    models = build_slot_models(live, routing, Profiles(tool_state.engine))
    tool_state.models = models
    graph = build_graph(
        tool_state.engine,
        tool_state.settings,
        model_provider=models.__getitem__,
        model_ids=routing.model_for,
        checkpointer=InMemorySaver(),
        deps=ToolDeps(tool_state),
        budgets=Budgets(tool_state.engine),
    )
    return Harness(graph=graph, models=models, state=tool_state, room="Wohnen")


def _built_sideboard(tool_state, *, approved: bool) -> None:
    root = tool_state.settings.render_root
    service.create_version(root, "sideboard", {**desk(), "name": "Sideboard"}, lambda version: None)
    folder = storage.version_dir(root, "sideboard", 1)
    storage.write_status(folder, status="succeeded")
    (folder / "model.blend").write_bytes(b"")
    with ToolDeps(tool_state).session() as session:
        house_file.upsert_room(session, "Wohnen", WOHNEN, 2500)
        house_file.record_piece(session, "sideboard", "Sideboard")
        house_file.record_version(session, "sideboard", 1)
        if approved:
            house_file.approve_version(session, "sideboard", 1)
        session.commit()


def _calls(harness: Harness, state: dict[str, Any]) -> list[str]:
    """Every tool call of the turn, including those of a specialist paused mid-turn."""
    messages = list(state.get("messages", []))
    for task in harness.graph.get_state(harness.config, subgraphs=True).tasks:
        if task.state is not None:
            messages += task.state.values.get("messages", [])
    return [f"{c['name']}({c['args']})" for m in messages if isinstance(m, AIMessage) for c in (m.tool_calls or [])]


def _check(step: str, ok: bool, harness: Harness, state: dict[str, Any]) -> None:
    pause = state["__interrupt__"][0].value if state.get("__interrupt__") else None
    assert ok, (
        f"benchmark step '{step}' failed: specialist={state.get('specialist')!r}, "
        f"tools={_calls(harness, state)}, pause={pause}, reply={last_reply(state)[:300]!r}"
    )


def test_a_placement_stated_in_the_owners_words(live_harness, tool_state) -> None:
    _built_sideboard(tool_state, approved=True)
    live_harness.start(package_id="sideboard")
    state = live_harness.turn("Please place the sideboard along wall 2 0 mm from wall 3.")

    _check("routing", state.get("specialist") == "designer", live_harness, state)
    pause = state["__interrupt__"][0].value if state.get("__interrupt__") else {}
    _check("question set", pause.get("kind") != "questions", live_harness, state)
    stored = read_placement(storage.version_dir(tool_state.settings.render_root, "sideboard", 1), "Wohnen")
    _check("stored placement", bool(stored) and stored["wall"] == 1 and stored["left_mm"] == 0, live_harness, state)
    _check("pause", pause.get("kind") == "confirmation" and pause.get("subject") == "compose_room", live_harness, state)
    called = " ".join(_calls(live_harness, state))
    replies = " ".join(str(m.content) for m in state["messages"] if isinstance(m, AIMessage))
    _check("wording", "render_turntable" not in called and "render" not in replies.lower(), live_harness, state)


def _placed_murphy_bed(tool_state, *, left_mm: float) -> None:
    """A built 1000 mm wide "Murphy bed" on wall 2 of Wohnen (3000 mm long), `left_mm` from its
    left end. Wall 2's left end, seen from inside, is the corner it shares with wall 3."""
    root = tool_state.settings.render_root
    service.create_version(root, "murphy-bed", {**desk(), "name": "Murphy bed"}, lambda version: None)
    folder = storage.version_dir(root, "murphy-bed", 1)
    storage.write_status(folder, status="succeeded")
    (folder / "model.blend").write_bytes(b"")
    write_placement(folder, "Wohnen", {
        "room": "Wohnen", "wall": 1, "left_mm": left_mm, "offset_mm": 3000 - left_mm - 1000,
    })
    with ToolDeps(tool_state).session() as session:
        house_file.upsert_room(session, "Wohnen", WOHNEN, 2500)
        house_file.record_piece(session, "murphy-bed", "Murphy bed")
        house_file.record_version(session, "murphy-bed", 1)
        session.commit()


def _states_mm(reply: str, figure: int) -> bool:
    """`figure` mm in the reply, written 1300, 1,300, 1.300 or 1 300, and not part of a longer number."""
    digits = str(figure)
    grouped = digits if figure < 1000 else rf"{digits[:-3]}[,. ]?{digits[-3:]}"
    return re.search(rf"(?<![\d.,]){grouped}\s?mm", reply) is not None


def test_a_gap_between_a_placed_piece_and_a_wall(live_harness, tool_state) -> None:
    _placed_murphy_bed(tool_state, left_mm=700)
    folder = storage.version_dir(tool_state.settings.render_root, "murphy-bed", 1)
    before = read_placement(folder, "Wohnen")
    live_harness.start(package_id="murphy-bed")

    # Wall 3 is at the bed's left end: the saved figure itself.
    state = live_harness.turn("How much space is between the murphy bed and wall 3?")
    _check("no pause", not state.get("__interrupt__"), live_harness, state)
    _check("gap to wall 3", _states_mm(last_reply(state), 700), live_harness, state)

    # Wall 1 is at the right end: 3000 mm wall - 700 mm - 1000 mm bed.
    state = live_harness.turn("And how much space is between the murphy bed and wall 1?")
    _check("no pause", not state.get("__interrupt__"), live_harness, state)
    _check("gap to wall 1", _states_mm(last_reply(state), 1300), live_harness, state)
    _check("placement unchanged", read_placement(folder, "Wohnen") == before, live_harness, state)


def test_gaps_in_a_room_version_come_from_measure_gaps(live_harness, tool_state) -> None:
    import json

    from app.compositions import gaps_of
    from tests.test_measure_gaps import BED, stand_in, stored

    wardrobe = stand_in("wardrobe", "Wardrobe", 1000, 600, 2000, wall=0, offset_mm=3500)
    shelf = {"id": "wall-shelf", "type": "piece", "package_id": "wall-shelf", "version": 1,
             "placement": {"wall": 0, "offset_mm": 1000, "mount_height_mm": 1600}}
    document = stored(BED, wardrobe, shelf, piece_sizes={"wall-shelf": (1200.0, 250.0, 300.0)})
    with ToolDeps(tool_state).session() as session:
        house_file.upsert_room(session, "Wohnen", WOHNEN, 2500)
        composition = house_file.record_composition(session, "room", "Wohnen")
        house_file.record_composition_version(session, composition, 12, None, [])
        session.commit()
    folder = storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 12)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps(document), encoding="utf-8")
    storage.write_status(folder, status="succeeded")
    bed = gaps_of(document, "murphy-bed")
    to_wall_1 = next(w["gap_mm"] for w in bed["walls"] if w["label"] == "wall 1")
    to_wardrobe = next(i["gap_mm"] for i in bed["items"] if i["id"] == "wardrobe")
    shelf_to_ceiling = gaps_of(document, "wall-shelf")["ceiling_mm"]

    live_harness.start()
    state = live_harness.turn(
        "In Wohnen v12, how much space is there between the Murphy bed and wall 1, between the "
        "Murphy bed and the wardrobe, and between the wall shelf and the ceiling?"
    )
    _check("no pause", not state.get("__interrupt__"), live_harness, state)
    _check("measure_gaps called", "measure_gaps(" in " ".join(_calls(live_harness, state)), live_harness, state)
    reply = last_reply(state)
    for step, figure in (("bed to wall 1", to_wall_1), ("bed to wardrobe", to_wardrobe), ("shelf to ceiling", shelf_to_ceiling)):
        _check(step, _states_mm(reply, figure), live_harness, state)
