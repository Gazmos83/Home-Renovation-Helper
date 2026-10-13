"""design-agents: `room_fit` checks a placement against a house-file room."""

from __future__ import annotations

import json
import re

from app.agent import house_file
from app.agent.tools.room_fit import run
from app.blender.schemas import RoomSceneSpec
from app.packages import service
from tests.api_helpers import desk

LIVING = [[0, 0], [4000, 0], [4000, 3500], [0, 3500]]


def setup(tool_deps, tool_state, *, openings=None) -> None:
    """A desk version with a spec.json (what a build would publish) and a stored room."""
    root = tool_state.settings.render_root
    service.create_version(root, "bench", desk(), lambda version: None)
    from app.blender import storage
    from app.blender.custom_build import derive as custom_derive

    folder = storage.version_dir(root, "bench", 1)
    (folder / "spec.json").write_text(
        json.dumps({"overall": custom_derive.overall(desk())}), encoding="utf-8"
    )
    with tool_deps.session() as session:
        house_file.upsert_room(session, "Living room", LIVING, 2600, openings=openings or [])
        session.commit()


def fit(make_ctx, **overrides) -> str:
    args = {"room_name": "Living room", "package_id": "bench", "wall": 0, "offset_mm": 500}
    return run({**args, **overrides}, make_ctx())


def test_a_piece_that_fits_returns_the_placement_and_a_valid_room_document(
    make_ctx, tool_deps, tool_state
) -> None:
    setup(tool_deps, tool_state)
    result = fit(make_ctx)
    assert "fits in Living room on wall 0 at offset 500 mm" in result
    document = json.loads(re.search(r"Room document[^:]*: (\{.*\})$", result, re.MULTILINE).group(1))
    spec = RoomSceneSpec.model_validate(document)
    assert spec.placement.wall == 0
    from app.blender.custom_build import derive as custom_derive

    spec.context({k: float(v) for k, v in custom_derive.overall(desk()).items()})


def test_too_wide_is_refused_naming_the_wall_and_the_excess(make_ctx, tool_deps, tool_state) -> None:
    setup(tool_deps, tool_state)
    result = fit(make_ctx, offset_mm=3900)
    assert result.startswith("it does not fit:")
    assert "wall 0" in result
    assert re.search(r"needs [\d.]+ mm, wall is 4000.0 mm", result)


def test_an_unknown_room_lists_the_known_ones(make_ctx, tool_deps, tool_state) -> None:
    setup(tool_deps, tool_state)
    result = fit(make_ctx, room_name="Attic")
    assert "no room 'Attic'" in result and "Living room" in result


def test_an_unknown_room_names_intake_as_the_way_to_record_one(make_ctx, tool_deps, tool_state) -> None:
    setup(tool_deps, tool_state)
    result = fit(make_ctx, room_name="Attic")
    assert "Intake records a room from its measurements or a plan" in result


def test_with_no_rooms_recorded_the_refusal_says_so(make_ctx, tool_deps, tool_state) -> None:
    setup(tool_deps, tool_state)
    with tool_deps.session() as session:
        for room in house_file.rooms(session):
            session.delete(room)
        session.commit()
    result = fit(make_ctx, room_name="Wohnen")
    assert "no room 'Wohnen'" in result
    assert "no rooms are recorded yet" in result
    assert "Intake records a room" in result


def test_a_wall_that_does_not_exist_is_refused(make_ctx, tool_deps, tool_state) -> None:
    setup(tool_deps, tool_state)
    assert "valid wall index" in fit(make_ctx, wall=9)


def test_a_piece_too_tall_for_the_ceiling_is_refused(make_ctx, tool_deps, tool_state) -> None:
    setup(tool_deps, tool_state)
    with tool_deps.session() as session:
        house_file.upsert_room(session, "Living room", LIVING, 600)
        session.commit()
    assert "taller than the ceiling" in fit(make_ctx)


def test_a_door_in_the_way_is_refused_naming_it(make_ctx, tool_deps, tool_state) -> None:
    door = {"wall": 0, "type": "door", "offset_mm": 600, "width_mm": 900, "height_mm": 2100}
    setup(tool_deps, tool_state, openings=[door])
    result = fit(make_ctx)
    assert "would block the door on wall 0" in result


def test_a_window_above_the_piece_is_not_in_the_way(make_ctx, tool_deps, tool_state) -> None:
    window = {"wall": 0, "type": "window", "offset_mm": 600, "width_mm": 900, "height_mm": 800, "sill_mm": 1500}
    setup(tool_deps, tool_state, openings=[window])
    assert "fits in Living room" in fit(make_ctx)


def test_a_door_on_another_wall_is_not_in_the_way(make_ctx, tool_deps, tool_state) -> None:
    door = {"wall": 2, "type": "door", "offset_mm": 600, "width_mm": 900, "height_mm": 2100}
    setup(tool_deps, tool_state, openings=[door])
    assert "fits in Living room" in fit(make_ctx)


def _composition_plan(tool_deps, tool_state, *, openings=None, corners=None) -> None:
    """An approved Living room composition whose plan may differ from the house-file openings."""
    from app.blender import storage

    root = tool_state.settings.render_root
    plan_corners = corners or LIVING
    with tool_deps.session() as session:
        composition = house_file.record_composition(session, "room", "Living room")
        house_file.record_composition_version(session, composition, 1, None, [])
        house_file.approve_composition_version(session, root, composition.slug, 1)
        session.commit()
        slug = composition.slug
    folder = storage.composition_version_dir(root, slug, 1)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / storage.INPUT_FILE).write_text(
        json.dumps({
            "kind": "room_composition",
            "scope": {"room": "Living room"},
            "items": [],
            "resolved": {
                "rooms": [{
                    "name": "Living room",
                    "corners": plan_corners,
                    "height_mm": 2600.0,
                    "wall_thickness_mm": 100.0,
                    "openings": openings or [],
                }],
                "items": [],
            },
        }),
        encoding="utf-8",
    )
    storage.write_status(folder, status="succeeded")


def test_a_house_file_door_is_ignored_when_the_approved_plan_has_none(
    make_ctx, tool_deps, tool_state
) -> None:
    door = {"wall": 0, "type": "door", "offset_mm": 600, "width_mm": 900, "height_mm": 2100}
    setup(tool_deps, tool_state, openings=[door])
    assert "would block the door" in fit(make_ctx)
    _composition_plan(tool_deps, tool_state, openings=[])
    assert "fits in Living room" in fit(make_ctx)


def test_an_approved_plan_door_still_blocks(make_ctx, tool_deps, tool_state) -> None:
    setup(tool_deps, tool_state, openings=[])
    door = {"wall": 0, "type": "door", "offset_mm": 600, "width_mm": 900, "height_mm": 2100}
    _composition_plan(tool_deps, tool_state, openings=[door])
    assert "would block the door on wall 0" in fit(make_ctx)
