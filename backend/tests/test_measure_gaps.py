"""measure-gaps: clear distances from an item to walls, other items and the ceiling, by code."""

from __future__ import annotations

import pytest

from app.blender.composition_contract import (
    parse_composition,
    place_items,
    room_geometry,
)
from app.blender.room_contract import polygon_distance, segment_distance
from app.compositions import GapRefused, gaps_of

# The owner's five-wall Wohnen: wall 2 runs (6000,0)-(6000,3000); its left end, seen from
# inside, is the corner it shares with wall 3, and wall 3 is not square to it.
WOHNEN = {
    "corners_mm": [[0, 0], [6000, 0], [6000, 3000], [3000, 4500], [0, 3000]],
    "height_mm": 2500, "wall_thickness_mm": 100, "openings": [],
}


def stand_in(item_id, name, w, d, h, **placement):
    return {"id": item_id, "type": "stand-in", "name": name, "width_mm": w, "depth_mm": d, "height_mm": h,
            "colour": "#777777", "placement": placement}


def stored(*items, piece_sizes=None) -> dict:
    document = {"kind": "room_composition", "schema_version": 1, "units": "mm",
                "scope": {"room": "Wohnen"}, "items": list(items)}
    parsed = parse_composition(document, max_items=30)
    result, _subjects = place_items(parsed, rooms={"Wohnen": room_geometry("Wohnen", WOHNEN)}, piece_sizes=piece_sizes or {},
                                    scope_room="Wohnen")
    return result


# 1000 mm wide on wall 2, 700 mm from its left end: offset 3000 - 700 - 1000 from the wall's start.
BED = stand_in("murphy-bed", "Murphy bed", 1000, 300, 700, wall=1, offset_mm=1300)


# --- distance helpers -----------------------------------------------------------


def test_parallel_segments_are_their_spacing_apart() -> None:
    assert segment_distance((0, 0), (10, 0), (0, 5), (10, 5)) == 5


def test_crossing_or_touching_segments_are_zero_apart() -> None:
    assert segment_distance((0, 0), (10, 10), (0, 10), (10, 0)) == 0
    assert segment_distance((0, 0), (10, 0), (10, 0), (10, 5)) == 0


def test_corner_to_corner_is_the_diagonal() -> None:
    assert segment_distance((0, 0), (1, 0), (4, 4), (4, 9)) == pytest.approx(5)


def test_a_square_inside_another_is_zero_apart() -> None:
    outer = ((0, 0), (10, 0), (10, 10), (0, 10))
    inner = ((4, 4), (6, 4), (6, 6), (4, 6))
    assert polygon_distance(outer, inner) == 0
    assert polygon_distance(inner, ((20, 0), (20, 10))) == 14


# --- gaps_of --------------------------------------------------------------------


def test_the_murphy_bed_gaps_to_walls_and_ceiling() -> None:
    gaps = gaps_of(stored(BED), "Murphy bed")
    walls = {wall["label"]: wall["gap_mm"] for wall in gaps["walls"]}
    assert walls["wall 3"] == 700 and walls["wall 1"] == 1300 and walls["wall 2"] == 0
    assert gaps["ceiling_mm"] == 1800 and gaps["underside_mm"] is None


def test_an_item_is_found_by_id_name_or_spacing_variant() -> None:
    document = stored(BED)
    assert gaps_of(document, "murphy-bed")["item"] == "murphy-bed"
    assert gaps_of(document, "MURPHY  BED")["item"] == "murphy-bed"


def test_a_shelf_hung_above_a_desk_gives_the_vertical_clearance() -> None:
    desk = stand_in("desk", "Desk", 1200, 600, 750, wall=0, offset_mm=1000)
    shelf = {"id": "shelf", "type": "piece", "package_id": "wall-shelf", "version": 1,
             "placement": {"wall": 0, "offset_mm": 1000, "mount_height_mm": 1500}}
    gaps = gaps_of(stored(desk, shelf, piece_sizes={"shelf": (1200.0, 250.0, 300.0)}), "wall-shelf")
    [other] = gaps["items"]
    assert (other["id"], other["gap_mm"], other["vertical"]) == ("desk", 750, True)
    assert gaps["underside_mm"] == 1500 and gaps["ceiling_mm"] == 700


def test_two_items_side_by_side_are_their_plan_gap_apart() -> None:
    desk = stand_in("desk", "Desk", 1200, 600, 750, wall=0, offset_mm=1000)
    cabinet = stand_in("cabinet", "Cabinet", 800, 400, 900, wall=0, offset_mm=2700)
    [other] = gaps_of(stored(desk, cabinet), "desk")["items"]
    assert (other["name"], other["gap_mm"], other["vertical"]) == ("Cabinet", 500, False)


def test_an_ambiguous_name_is_refused_with_both_ids() -> None:
    one = stand_in("chair-1", "Chair", 500, 500, 900, x_mm=1000, y_mm=1500, rotation_deg=0)
    two = stand_in("chair-2", "Chair", 500, 500, 900, x_mm=2500, y_mm=1500, rotation_deg=0)
    with pytest.raises(GapRefused, match="chair-1, chair-2"):
        gaps_of(stored(one, two), "Chair")


def test_an_unknown_item_or_missing_plan_or_apartment_is_refused() -> None:
    with pytest.raises(GapRefused, match="no item 'Sofa'"):
        gaps_of(stored(BED), "Sofa")
    with pytest.raises(GapRefused, match="no room plan"):
        gaps_of({"scope": {"room": "Wohnen"}, "items": []}, "bed")
    with pytest.raises(GapRefused, match="apartment"):
        gaps_of({"scope": {"apartment": "Flat"}}, "bed")


# --- the measure_gaps tool --------------------------------------------------------


def _seed(tool_state, *items, room="Wohnen"):
    """Wohnen with composition version 12 holding `items`; a thread whose room is `room`."""
    import json

    from app.agent import house_file
    from app.agent.tools.base import ToolDeps
    from app.blender import storage

    with ToolDeps(tool_state).session() as session:
        wohnen = house_file.upsert_room(session, "Wohnen", WOHNEN["corners_mm"], 2500)
        composition = house_file.record_composition(session, "room", "Wohnen")
        house_file.record_composition_version(session, composition, 12, None, [])
        folder = storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 12)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / storage.INPUT_FILE).write_text(json.dumps(stored(*items)), encoding="utf-8")
        storage.write_status(folder, status="succeeded")
        thread = house_file.create_thread(session, "t")
        scope = wohnen if room == "Wohnen" else house_file.upsert_room(session, room, [[0, 0], [3000, 0], [3000, 2000], [0, 2000]], 2500)
        house_file.set_thread_room(session, thread.id, scope)
        session.commit()
        return thread.id, folder


def test_the_tool_measures_a_stored_version_and_writes_nothing(tool_state, make_ctx) -> None:
    from plugins.room_version_dimensions.tool import run_measure

    wardrobe = stand_in("wardrobe", "Wardrobe", 1000, 600, 2000, wall=0, offset_mm=2000)
    thread_id, folder = _seed(tool_state, BED, wardrobe)
    before = {path.name: path.read_bytes() for path in folder.iterdir()}
    result = run_measure({"version": 12, "item": "Murphy bed"}, make_ctx(thread_id=thread_id))
    assert "wall 3: 700 mm" in result and "wall 1: 1300 mm" in result
    assert "Wardrobe (wardrobe):" in result and "to the ceiling: 1800 mm" in result
    assert result.endswith("Quote these figures; do not recompute them.")
    assert {path.name: path.read_bytes() for path in folder.iterdir()} == before


def test_the_tool_refuses_another_room(tool_state, make_ctx) -> None:
    from plugins.room_version_dimensions.tool import run_measure

    thread_id, _folder = _seed(tool_state, BED, room="Hall")
    result = run_measure({"version": 12, "item": "Murphy bed", "room": "Wohnen"}, make_ctx(thread_id=thread_id))
    assert "not this conversation's confirmed room" in result and "mm" not in result


def test_the_tool_answers_an_unknown_version_cannot_be_measured(tool_state, make_ctx) -> None:
    from plugins.room_version_dimensions.tool import run_measure

    thread_id, _folder = _seed(tool_state, BED)
    assert run_measure({"version": 13, "item": "bed"}, make_ctx(thread_id=thread_id)) == (
        "nothing was measured: Wohnen has no room version 13"
    )


def test_the_tool_refuses_an_apartment(tool_state, make_ctx) -> None:
    from app.agent import house_file
    from app.agent.tools.base import ToolDeps
    from plugins.room_version_dimensions.tool import run_measure

    with ToolDeps(tool_state).session() as session:
        flat = house_file.upsert_apartment(
            session, "Flat", 2550, 120,
            [{"name": "Living", "corners_mm": [[0, 0], [3000, 0], [3000, 3000], [0, 3000]], "height_mm": None, "openings": []}],
        )
        thread = house_file.create_thread(session, "t")
        house_file.set_thread_apartment(session, thread.id, flat)
        session.commit()
        thread_id = thread.id
    assert "not yet in an apartment" in run_measure({"version": 1, "item": "bed"}, make_ctx(thread_id=thread_id))


# --- the saved-place line ---------------------------------------------------------


def test_the_saved_place_line_names_both_end_walls(tool_state) -> None:
    from app.agent import house_file
    from app.agent.tools.base import ToolDeps
    from app.blender import storage
    from app.packages import service
    from app.packages.placements import write_placement
    from tests.api_helpers import desk  # the fold-down desk: 1000 mm wide
    from tests.graph_helpers import fake_models, make_harness

    root = tool_state.settings.render_root
    service.create_version(root, "murphy-bed", {**desk(), "name": "Murphy bed"}, lambda version: None)
    folder = storage.version_dir(root, "murphy-bed", 1)
    storage.write_status(folder, status="succeeded")
    write_placement(folder, "Wohnen", {"room": "Wohnen", "wall": 1, "left_mm": 700, "offset_mm": 1300})
    with ToolDeps(tool_state).session() as session:
        house_file.upsert_room(session, "Wohnen", WOHNEN["corners_mm"], 2500)
        house_file.record_piece(session, "murphy-bed", "Murphy bed")
        house_file.record_version(session, "murphy-bed", 1)
        session.commit()
    models = fake_models(foreman={"decisions": [{"specialist": "designer", "reason": "test"}]}, designer={"replies": ["ok"]})
    harness = make_harness(tool_state, models, room="Wohnen")
    harness.start(package_id="murphy-bed")
    harness.turn("How much space is between the murphy bed and wall 1?")
    assert (
        "Its left end is 700 mm from wall 3 and its right end 1300 mm from wall 1"
        in models["designer"].prompts[-1][0].content
    )


def test_without_measured_ends_the_line_is_unchanged() -> None:
    from app.agent.foreman import placement_note

    saved = {"room": "Hall", "wall": 1, "left_mm": 0, "mount_height_mm": 1700}
    assert placement_note(saved) == (
        "(Saved place of this piece in Hall: wall 2 (index 1), 0 mm from its left end, hung with its "
        "underside at 1700 mm above the floor. Do not ask the owner for these figures again.)"
    )
