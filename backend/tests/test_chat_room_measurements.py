"""chat-room-measurements-follow-approved-version: house block and read tool match the inspector."""

from __future__ import annotations

import json
from pathlib import Path

from app import compositions
from app.agent import house_file
from app.agent.prompts import house_note
from app.agent.tools.base import ToolDeps
from app.blender import storage
from plugins.room_version_dimensions.tool import run
from tests.graph_helpers import fake_models, make_harness

WOHNEN_PLAN = [[0.0, 0.0], [6200.0, 0.0], [6200.0, 5700.0], [3500.0, 5700.0], [1289.0, 6064.0]]
WOHNEN_HOUSE = [[0.0, 0.0], [6200.0, 0.0], [6200.0, 6064.0], [0.0, 6064.0]]


def decision(specialist: str) -> dict:
    return {"specialist": specialist, "reason": "test"}


def _write_plan(folder: Path, *, corners=None, height_mm: float = 2500.0, wall3: float | None = None) -> None:
    plan = list(corners or WOHNEN_PLAN)
    if wall3 is not None:
        # Stretch wall 3 (between corners 2 and 3) to the given length by moving corner 3 in x.
        plan = [list(p) for p in plan]
        plan[3][0] = plan[2][0] - wall3
    document = {
        "kind": "room_composition",
        "scope": {"room": "Wohnen"},
        "items": [],
        "resolved": {
            "rooms": [
                {
                    "name": "Wohnen",
                    "corners": plan,
                    "height_mm": height_mm,
                    "wall_thickness_mm": 100.0,
                    "openings": [],
                }
            ],
            "items": [],
        },
    }
    folder.mkdir(parents=True, exist_ok=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps(document), encoding="utf-8")
    storage.write_status(folder, status="succeeded")


def _seed_wohnen(session, render_root: Path, *, versions: tuple[int, ...] = (1, 2), wall3_by_version: dict | None = None):
    house_file.upsert_room(session, "Wohnen", WOHNEN_HOUSE, 2500)
    composition = house_file.record_composition(session, "room", "Wohnen")
    for number in versions:
        house_file.record_composition_version(
            session, composition, number, number - 1 if number > 1 else None, []
        )
        _write_plan(
            storage.composition_version_dir(render_root, "wohnen", number),
            wall3=(wall3_by_version or {}).get(number),
        )
    return composition


def test_house_note_lists_five_walls_when_dimensions_are_given() -> None:
    dims = {
        "version": 2,
        "approved": True,
        "walls": [
            {"label": "wall 1", "length_mm": 6200},
            {"label": "wall 2", "length_mm": 5700},
            {"label": "wall 3", "length_mm": 2700},
            {"label": "wall 4", "length_mm": 2241},
            {"label": "wall 5", "length_mm": 6199},
        ],
        "ceilings": [{"room": "Wohnen", "height_mm": 2500}],
    }
    note = house_note(
        [{"name": "Wohnen", "corners_mm": WOHNEN_HOUSE, "height_mm": 2500, "openings": [], "dimensions": dims}],
        {},
        [],
        [],
    )
    assert "composition version 2 (approved)" in note
    assert "wall 1: 6200 mm" in note and "wall 2: 5700 mm" in note
    assert "wall 3: 2700 mm" in note and "wall 4: 2241 mm" in note and "wall 5: 6199 mm" in note
    assert "ceiling 2500 mm" in note
    assert "bounding box" not in note
    assert "6200 × 6064" not in note


def test_house_note_keeps_house_file_figures_without_dimensions() -> None:
    note = house_note(
        [{"name": "Wohnen", "corners_mm": WOHNEN_HOUSE, "height_mm": 2500, "openings": []}],
        {},
        [],
        [],
    )
    assert "bounding box 6200 × 6064 mm, ceiling 2500 mm" in note
    assert "composition version" not in note


def _foreman_house_prompt(models) -> str:
    """The Foreman's decision prompt, which always carries the house note."""
    return "\n".join(str(message.content) for message in models["foreman"].decision_prompts[-1])


def test_wohnen_v2_block_lists_the_five_walls_and_ceiling(tool_state) -> None:
    render_root = tool_state.settings.render_root
    with ToolDeps(tool_state).session() as session:
        _seed_wohnen(session, render_root)
        house_file.approve_composition_version(session, render_root, "wohnen", 2)
        session.commit()
    models = fake_models(foreman={"decisions": [decision("researcher")]}, researcher={"replies": ["ok"]})
    make_harness(tool_state, models, room="Wohnen").turn("how long are the walls?")
    prompt = _foreman_house_prompt(models)
    assert "composition version 2 (approved)" in prompt
    assert "wall 1: 6200 mm" in prompt
    assert "wall 2: 5700 mm" in prompt
    assert "wall 3: 2700 mm" in prompt
    assert "wall 4: 2241 mm" in prompt
    assert "wall 5: 6199 mm" in prompt
    assert "ceiling 2500 mm" in prompt
    room_line = next(line for line in prompt.splitlines() if line.startswith("- Wohnen:"))
    assert "bounding box" not in room_line


def test_approving_v3_changes_the_next_block(tool_state) -> None:
    render_root = tool_state.settings.render_root
    with ToolDeps(tool_state).session() as session:
        _seed_wohnen(session, render_root, versions=(1, 2, 3), wall3_by_version={3: 2900})
        house_file.approve_composition_version(session, render_root, "wohnen", 2)
        session.commit()
    models = fake_models(
        foreman={"decisions": [decision("researcher"), decision("researcher")]},
        researcher={"replies": ["v2", "v3"]},
    )
    harness = make_harness(tool_state, models, room="Wohnen")
    harness.turn("walls?")
    first = _foreman_house_prompt(models)
    assert "composition version 2 (approved)" in first
    assert "wall 3: 2700 mm" in first
    with ToolDeps(tool_state).session() as session:
        house_file.approve_composition_version(session, render_root, "wohnen", 3)
        session.commit()
    harness.turn("walls again?")
    prompt = _foreman_house_prompt(models)
    assert "composition version 3 (approved)" in prompt
    assert "wall 3: 2900 mm" in prompt
    assert "wall 3: 2700 mm" not in prompt


def test_no_approved_version_is_labelled(tool_state) -> None:
    render_root = tool_state.settings.render_root
    with ToolDeps(tool_state).session() as session:
        _seed_wohnen(session, render_root, versions=(1, 2))
        session.commit()
    models = fake_models(foreman={"decisions": [decision("researcher")]}, researcher={"replies": ["ok"]})
    make_harness(tool_state, models, room="Wohnen").turn("walls?")
    prompt = _foreman_house_prompt(models)
    assert "composition version 2 (not approved)" in prompt
    assert "wall 1: 6200 mm" in prompt


def test_no_composition_keeps_house_file_figures(tool_state) -> None:
    with ToolDeps(tool_state).session() as session:
        house_file.upsert_room(session, "Wohnen", WOHNEN_HOUSE, 2500)
        session.commit()
    models = fake_models(foreman={"decisions": [decision("researcher")]}, researcher={"replies": ["ok"]})
    make_harness(tool_state, models, room="Wohnen").turn("how big is it?")
    prompt = _foreman_house_prompt(models)
    assert "bounding box 6200 × 6064 mm, ceiling 2500 mm" in prompt
    assert "composition version" not in prompt


def test_the_tool_refuses_another_room(tool_state, make_ctx) -> None:
    render_root = tool_state.settings.render_root
    with ToolDeps(tool_state).session() as session:
        hall = house_file.upsert_room(session, "Hall", [[0, 0], [3000, 0], [3000, 2000], [0, 2000]], 2500)
        _seed_wohnen(session, render_root)
        thread = house_file.create_thread(session, "t")
        house_file.set_thread_room(session, thread.id, hall)
        session.commit()
        thread_id = thread.id
    result = run({"version": 2, "room": "Wohnen"}, make_ctx(thread_id=thread_id))
    assert "not this conversation's confirmed room" in result
    assert "6200" not in result
    assert "wall 1" not in result


def test_chat_figures_equal_the_dimensions_route(tool_state) -> None:
    render_root = tool_state.settings.render_root
    with ToolDeps(tool_state).session() as session:
        _seed_wohnen(session, render_root)
        house_file.approve_composition_version(session, render_root, "wohnen", 2)
        session.commit()
        from_chat = compositions.dimensions_of_scope(
            session, render_root, scope="room", name="Wohnen"
        )
    document = compositions.read_document(storage.composition_version_dir(render_root, "wohnen", 2))
    from_route = compositions.room_dimensions(document)
    assert from_chat is not None and from_route is not None
    assert [(w["label"], w["length_mm"]) for w in from_chat["walls"]] == [
        (w["label"], w["length_mm"]) for w in from_route["walls"]
    ]
    assert from_chat["ceilings"][0]["height_mm"] == from_route["ceilings"][0]["height_mm"]
    assert from_chat["version"] == 2 and from_chat["approved"] is True
    assert [(w["label"], w["length_mm"]) for w in from_chat["walls"]] == [
        ("wall 1", 6200),
        ("wall 2", 5700),
        ("wall 3", 2700),
        ("wall 4", 2241),
        ("wall 5", 6199),
    ]
