"""apartment-shell: the shell contract — shared walls, overlap, openings, plausibility."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.blender.room_contract import SpecValidationError
from app.blender.shell_contract import normalise_shell, polygon_area_m2, rooms_overlap

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "packages" / "apartment-two-room.json"


@pytest.fixture
def two_room() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_two_room_fixture_shares_one_wall(two_room: dict) -> None:
    ctx = normalise_shell(two_room)
    assert [room.name for room in ctx.rooms] == ["Living room", "Bedroom"]
    # Four edges per room, and the edge at x = 5200 is one wall: 4 + 4 - 1.
    assert len(ctx.walls) == 7
    shared = [wall for wall in ctx.walls if wall.shared]
    assert len(shared) == 1
    wall = shared[0]
    assert wall.rooms == ("Living room", "Bedroom")
    assert {wall.a[0], wall.b[0]} == {5200.0}
    assert wall.length_mm == pytest.approx(3800)
    assert [(o["type"], o["offset_mm"], o["width_mm"]) for o in wall.openings] == [("door", 1200, 900)]


def test_a_door_listed_by_both_rooms_is_cut_once(two_room: dict) -> None:
    # The bedroom's wall 3 runs (5200,3800) -> (5200,0); the door is 1200..2100 from the south.
    two_room["rooms"][1]["openings"] = [
        {"wall": 3, "type": "door", "offset_mm": 3800 - 2100, "width_mm": 900, "height_mm": 2050}
    ]
    wall = next(w for w in normalise_shell(two_room).walls if w.shared)
    assert len(wall.openings) == 1


def test_overlapping_rooms_are_refused_naming_both(two_room: dict) -> None:
    two_room["rooms"][1]["corners"] = [[5000, 0], [8400, 0], [8400, 3800], [5000, 3800]]
    with pytest.raises(SpecValidationError, match=r"rooms 'Living room' and 'Bedroom' overlap"):
        normalise_shell(two_room)


def test_identical_rooms_overlap(two_room: dict) -> None:
    two_room["rooms"][1]["corners"] = copy.deepcopy(two_room["rooms"][0]["corners"])
    with pytest.raises(SpecValidationError, match="overlap"):
        normalise_shell(two_room)


def test_touching_along_an_edge_is_not_overlap() -> None:
    assert not rooms_overlap([(0, 0), (1000, 0), (1000, 1000), (0, 1000)], [(1000, 0), (2000, 0), (2000, 1000), (1000, 1000)])


def test_a_shorter_neighbour_splits_the_long_wall(two_room: dict) -> None:
    two_room["rooms"][1]["corners"] = [[5200, 1000], [8400, 1000], [8400, 3000], [5200, 3000]]
    ctx = normalise_shell(two_room)
    # Living: south, east split in three (outer, shared, outer), north, west = 6; bedroom: 3 own.
    assert len(ctx.walls) == 9
    shared = next(w for w in ctx.walls if w.shared)
    assert shared.length_mm == pytest.approx(2000)
    # The door (1200..2100 from the south) sits wholly inside the shared 1000..3000 span.
    assert [(o["offset_mm"], o["width_mm"]) for o in shared.openings] == [(200, 900)]


def test_an_opening_across_a_shared_boundary_is_refused(two_room: dict) -> None:
    two_room["rooms"][1]["corners"] = [[5200, 1500], [8400, 1500], [8400, 3000], [5200, 3000]]
    with pytest.raises(SpecValidationError, match="crosses the boundary"):
        normalise_shell(two_room)


def test_an_l_shaped_room_belongs_to_an_apartment(two_room: dict) -> None:
    two_room["rooms"][0]["corners"] = [[0, 0], [5200, 0], [5200, 1900], [2600, 1900], [2600, 3800], [0, 3800]]
    two_room["rooms"][0]["openings"] = []
    two_room["rooms"][1]["corners"] = [[5200, 0], [8400, 0], [8400, 1900], [5200, 1900]]
    ctx = normalise_shell(two_room)
    assert len(ctx.rooms[0].corners) == 6


def test_an_invalid_room_is_named(two_room: dict) -> None:
    two_room["rooms"][1]["openings"] = [
        {"wall": 0, "type": "door", "offset_mm": 100, "width_mm": 900, "height_mm": 2050, "sill_mm": 40}
    ]
    with pytest.raises(SpecValidationError, match=r"room 'Bedroom'.*must not have a sill"):
        normalise_shell(two_room)


def test_unknown_fields_and_duplicate_room_names_are_refused(two_room: dict) -> None:
    extra = copy.deepcopy(two_room)
    extra["rooms"][0]["colour"] = "red"
    with pytest.raises(SpecValidationError, match="unknown field 'colour'"):
        normalise_shell(extra)
    twin = copy.deepcopy(two_room)
    twin["rooms"][1]["name"] = "Living room"
    with pytest.raises(SpecValidationError, match="used more than once"):
        normalise_shell(twin)


def test_a_clean_fixture_has_no_warnings(two_room: dict) -> None:
    assert normalise_shell(two_room).warnings == ()


def test_plausibility_warnings_name_the_room_and_never_refuse(two_room: dict) -> None:
    two_room["apartment"]["ceiling_height_mm"] = 2100
    two_room["rooms"][0]["openings"] = [
        {"wall": 0, "type": "window", "offset_mm": 800, "width_mm": 1800, "height_mm": 500, "sill_mm": 1500},
        {"wall": 1, "type": "door", "offset_mm": 1200, "width_mm": 600, "height_mm": 2000},
    ]
    ctx = normalise_shell(two_room, printed_areas_m2={"Living room": 22.0})
    text = "\n".join(ctx.warnings)
    assert "Living room: ceiling 2100 mm is outside the usual 2300–3200 mm" in text
    assert "Living room: window 0 has a 1500 mm sill" in text
    assert "Living room: door 1 is 600 mm wide" in text
    assert f"the outline gives {polygon_area_m2(ctx.rooms[0].corners):.2f} m² but the plan prints 22.00 m²" in text
    assert "Bedroom: ceiling 2100 mm" in text


def test_the_fixture_round_trips_through_its_own_input_document(two_room: dict) -> None:
    ctx = normalise_shell(two_room)
    again = normalise_shell(ctx.input_document())
    assert len(again.walls) == len(ctx.walls)


def test_a_thin_overlap_strip_and_an_l_notch_are_judged_by_area() -> None:
    wide = [(0, 0), (5200, 0), (5200, 3800), (0, 3800)]
    assert rooms_overlap(wide, [(5000, 0), (8400, 0), (8400, 3800), (5000, 3800)])
    l_shape = [(0, 0), (4000, 0), (4000, 1500), (2000, 1500), (2000, 3500), (0, 3500)]
    # A room sitting in the L's missing quarter touches it but shares no area.
    assert not rooms_overlap(l_shape, [(2000, 1500), (4000, 1500), (4000, 3500), (2000, 3500)])
    # One reaching into the left arm overlaps.
    assert rooms_overlap(l_shape, [(1500, 2000), (3000, 2000), (3000, 3500), (1500, 3500)])


def test_the_apartment_4_living_room_loads_as_a_one_room_apartment() -> None:
    from app.blender.shell_contract import polygon_area_m2

    apt4 = json.loads((FIXTURE.parent / "room-scene-apt4-living.json").read_text(encoding="utf-8"))
    room = apt4["room"]
    document = {
        "kind": "apartment_shell", "schema_version": 1, "units": "mm",
        "apartment": {
            "name": "Apartment 4", "ceiling_height_mm": room["height_mm"],
            "wall_thickness_mm": room["wall_thickness_mm"],
        },
        "rooms": [{"name": "Wohnen", "corners": room["corners"], "openings": apt4["openings"]}],
    }
    ctx = normalise_shell(document, printed_areas_m2={"Wohnen": 32.287})
    assert len(ctx.walls) == 4 and not any(w.shared for w in ctx.walls)
    assert polygon_area_m2(ctx.rooms[0].corners) == pytest.approx(32.287, rel=0.005)
    # The area matches the printed one; only the 1050 mm terrace door is outside the usual range.
    assert ctx.warnings == ("Wohnen: door 1 is 1050 mm wide, outside the usual 700–1000 mm",)
