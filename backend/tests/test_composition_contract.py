"""room-composition: the composition contract — shape, scope, items and their placement."""

from __future__ import annotations

import copy

import pytest

from app.blender.composition_contract import (
    parse_composition,
    place_items,
    room_geometry,
)
from app.blender.spec_contract import SpecValidationError

WOHNEN = {
    "corners_mm": [[0, 0], [5000, 0], [5000, 4000], [0, 4000]],
    "height_mm": 2600,
    "wall_thickness_mm": 100,
    "openings": [
        {"wall": 0, "type": "door", "offset_mm": 3800, "width_mm": 900, "height_mm": 2100, "sill_mm": 0},
        {"wall": 2, "type": "window", "offset_mm": 1000, "width_mm": 1500, "height_mm": 1200, "sill_mm": 900},
    ],
}
L_ROOM = {
    "corners_mm": [[0, 0], [4000, 0], [4000, 2000], [2000, 2000], [2000, 4000], [0, 4000]],
    "height_mm": 2500, "wall_thickness_mm": 100, "openings": [],
}
PIECE_SIZE = {"listening-wall": (2200.0, 400.0, 2200.0)}


def document(*items, scope=None) -> dict:
    return {
        "kind": "room_composition", "schema_version": 1, "units": "mm",
        "scope": scope or {"room": "Wohnen"}, "items": list(items),
    }


def piece(**placement):
    return {"id": "listening-wall", "type": "piece", "package_id": "listening-wall", "version": 4,
            "placement": placement or {"wall": 1, "offset_mm": 0}}


def sofa(**placement):
    return {"id": "sofa", "type": "stand-in", "name": "Sofa", "width_mm": 2200, "depth_mm": 950, "height_mm": 800,
            "colour": "#7A6A58", "placement": placement or {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 0}}


def armchair(**placement):
    return {"id": "armchair", "type": "model", "model_id": "a1b2", "name": "Armchair",
            "width_mm": 800, "depth_mm": 700, "height_mm": 900,
            "placement": placement or {"x_mm": 1000, "y_mm": 3000, "rotation_deg": 45}}


def place(doc, rooms=None, scope_room="Wohnen"):
    parsed = parse_composition(doc, max_items=30)
    geometry = {name: room_geometry(name, room) for name, room in (rooms or {"Wohnen": WOHNEN}).items()}
    return place_items(parsed, rooms=geometry, piece_sizes=PIECE_SIZE, scope_room=scope_room)


def refusal(doc, **kw) -> str:
    with pytest.raises(SpecValidationError) as caught:
        place(doc, **kw)
    return str(caught.value)


# --- a composition document describes one room or one apartment ---------------------------


def test_a_room_scope_with_the_three_item_types_is_accepted() -> None:
    stored, subjects = place(document(piece(), sofa(), armchair()))
    assert [i["type"] for i in stored["items"]] == ["piece", "stand-in", "model"]
    assert stored["items"][1]["colour"] == "#7a6a58"
    sizes = {i["id"]: i["size_mm"] for i in stored["resolved"]["items"]}
    assert sizes == {
        "listening-wall": {"w": 2200.0, "d": 400.0, "h": 2200.0},
        "sofa": {"w": 2200.0, "d": 950.0, "h": 800.0},
        "armchair": {"w": 800.0, "d": 700.0, "h": 900.0},
    }
    assert [r["name"] for r in stored["resolved"]["rooms"]] == ["Wohnen"]
    assert [s[0] for s in subjects] == ["listening-wall", "sofa", "armchair"]


@pytest.mark.parametrize("field", ["output", "frames", "resolution", "engine"])
def test_an_output_field_is_refused_by_name(field: str) -> None:
    doc = document(sofa())
    doc[field] = {"frames": 36}
    assert field in refusal(doc)


def test_an_unknown_item_field_is_refused_by_name() -> None:
    item = sofa()
    item["bevel_mm"] = 3
    assert "bevel_mm" in refusal(document(item))


def test_an_apartment_item_without_a_room_is_refused_naming_it() -> None:
    message = refusal(document(sofa(), scope={"apartment": "Flat"}), scope_room=None)
    assert "'sofa'" in message and "names no room" in message


def test_an_apartment_item_in_a_room_outside_the_scope_is_refused() -> None:
    item = {**sofa(), "room": "Attic"}
    assert "Attic" in refusal(document(item, scope={"apartment": "Flat"}), scope_room=None)


def test_the_item_count_is_capped() -> None:
    items = [{**sofa(), "id": f"s{i}"} for i in range(31)]
    with pytest.raises(SpecValidationError, match="at most 30 items"):
        parse_composition(document(*items), max_items=30)


def test_duplicate_ids_and_bad_colours_are_refused() -> None:
    with pytest.raises(SpecValidationError, match="used more than once"):
        parse_composition(document(sofa(), sofa()), max_items=30)
    bad = sofa()
    bad["colour"] = "brown"
    with pytest.raises(SpecValidationError, match="#rrggbb"):
        parse_composition(document(bad), max_items=30)


# --- every item is placed validly ---------------------------------------------------------


def test_two_items_that_overlap_are_refused_naming_both() -> None:
    message = refusal(document(sofa(), armchair(x_mm=2500, y_mm=2000, rotation_deg=0)))
    assert "sofa" in message and "armchair" in message and "overlap" in message


def test_items_side_by_side_on_one_wall_may_touch() -> None:
    left = sofa(wall=3, offset_mm=0)
    right = {**armchair(), "placement": {"wall": 3, "offset_mm": 2200}}
    place(document(left, right))


def test_an_item_across_a_door_is_refused_naming_the_door_and_wall() -> None:
    message = refusal(document(sofa(wall=0, offset_mm=2500)))
    assert "sofa blocks the door on wall 0" in message


def test_a_free_item_in_front_of_a_door_is_refused() -> None:
    assert "blocks the door" in refusal(document(armchair(x_mm=4250, y_mm=400, rotation_deg=0)))


def test_a_low_item_under_a_window_is_allowed_but_a_tall_one_is_refused() -> None:
    low = sofa(wall=2, offset_mm=900)  # 800 mm tall, the sill is at 900
    place(document(low))
    tall = {**armchair(), "height_mm": 1000, "placement": {"wall": 2, "offset_mm": 1200}}
    assert "blocks the window on wall 2" in refusal(document(tall))


def test_an_item_reaching_into_the_missing_quarter_of_an_l_room_is_refused() -> None:
    doc = document(sofa(x_mm=2500, y_mm=2400, rotation_deg=0))
    message = refusal(doc, rooms={"Wohnen": L_ROOM})
    assert "sofa leaves the room Wohnen" in message


def test_an_item_taller_than_the_ceiling_is_refused() -> None:
    tall = copy.deepcopy(armchair())
    tall["height_mm"] = 2700
    assert "taller than the ceiling" in refusal(document(tall))


def test_an_item_running_past_the_end_of_its_wall_is_refused() -> None:
    message = refusal(document(piece(wall=1, offset_mm=2000)))
    assert "runs past the end of wall 1" in message


def test_a_wall_placement_stands_its_back_on_the_wall_facing_in() -> None:
    stored, subjects = place(document(piece(wall=1, offset_mm=500)))
    resolved = stored["resolved"]["items"][0]
    # Wall 1 runs from (5000, 0) to (5000, 4000): the piece's centre is 200 mm in from it.
    assert resolved["centre_mm"] == [4800.0, 1600.0]
    assert resolved["rotation_deg"] == pytest.approx(90.0)
    assert subjects[0][1].placement["outward_normal"] == pytest.approx((1.0, 0.0))


# --- placement design rules apply to every item -------------------------------------------


def _rules(tmp_path, *rules):
    from tests.test_design_rules import table

    return table(tmp_path, *rules)


def test_a_warn_rule_is_reported_per_item_and_a_refuse_rule_refuses(tmp_path) -> None:
    from app.compositions import rule_outcome
    from tests.test_design_rules import passage

    # The sofa faces into the room with 2525 mm of floor in front; the armchair, against wall 3, much more.
    _stored, subjects = place(document(sofa(x_mm=2500, y_mm=1000, rotation_deg=0), armchair(wall=3, offset_mm=0)))

    refusal_found, warnings = rule_outcome(_rules(tmp_path, passage(3000)), subjects)
    assert refusal_found is None
    assert warnings.startswith("item sofa: passage:") and "asr-a1-2" in warnings

    refusal_found, _ = rule_outcome(_rules(tmp_path, passage(3000, severity="refuse")), subjects)
    assert refusal_found.startswith("item sofa: refused by a design rule: passage")


def test_without_rules_nothing_is_reported(tmp_path) -> None:
    from app.compositions import rule_outcome

    _stored, subjects = place(document(sofa()))
    assert rule_outcome((), subjects) == (None, "")


# --- an empty room (rooms-page) ------------------------------------------------------------


def test_an_empty_room_is_accepted_and_resolves_the_room_with_no_items() -> None:
    stored, subjects = place(document())
    assert stored["items"] == [] and subjects == []
    assert [room["name"] for room in stored["resolved"]["rooms"]] == ["Wohnen"]
    assert stored["resolved"]["items"] == []


def test_an_empty_apartment_is_refused() -> None:
    with pytest.raises(SpecValidationError, match="an apartment composition needs at least one item"):
        parse_composition(document(scope={"apartment": "Wohnung"}), max_items=30)


def test_items_that_are_not_a_list_are_refused() -> None:
    with pytest.raises(SpecValidationError, match="items must be a list"):
        parse_composition({**document(), "items": "sofa"}, max_items=30)
