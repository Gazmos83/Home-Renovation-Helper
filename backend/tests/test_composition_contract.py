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


def rug(item_id="rug", **placement):
    return {"id": item_id, "type": "stand-in", "name": "Rug", "width_mm": 2300, "depth_mm": 1600, "height_mm": 10,
            "colour": "#c8b8a0", "layer": "floor",
            "placement": placement or {"x_mm": 2500, "y_mm": 2300, "rotation_deg": 0}}


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


def test_an_overlap_at_a_corner_names_both_walls() -> None:
    message = refusal(document(piece(wall=1, offset_mm=1800), sofa(wall=2, offset_mm=0)))
    assert "listening-wall (wall 1, offset 1800 mm) and sofa (wall 2, offset 0 mm) overlap" in message


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


# --- a floor-layer item lies under standing items (composition-floor-layer) ----------------


def test_a_floor_layer_rug_is_accepted_and_keeps_its_layer() -> None:
    stored, _subjects = place(document(rug()))
    assert stored["items"][0]["layer"] == "floor"


def test_a_floor_layer_model_is_accepted() -> None:
    mat = {**armchair(), "height_mm": 20, "layer": "floor"}
    stored, _subjects = place(document(mat))
    assert stored["items"][0]["layer"] == "floor"


def test_an_unknown_layer_value_is_refused_naming_the_item_and_field() -> None:
    message = refusal(document({**rug(), "layer": "wall"}))
    assert "rug" in message and "layer" in message


def test_a_piece_with_a_layer_is_refused_as_an_unknown_field() -> None:
    assert "unknown items[0] field: layer" in refusal(document({**piece(), "layer": "floor"}))


def test_a_floor_layer_item_taller_than_30_mm_is_refused() -> None:
    message = refusal(document({**rug(), "height_mm": 40}))
    assert "rug" in message and "30 mm" in message


def test_a_rug_under_the_sofa_is_accepted() -> None:
    stored, subjects = place(document(sofa(), rug()))
    assert [i["id"] for i in stored["resolved"]["items"]] == ["sofa", "rug"]
    assert [s[0] for s in subjects] == ["sofa"]


def test_a_sofa_on_a_rug_is_accepted_whichever_comes_first() -> None:
    place(document(rug(), sofa()))


def test_two_overlapping_rugs_are_refused_naming_both() -> None:
    message = refusal(document(rug(), rug("runner", x_mm=2600, y_mm=2400, rotation_deg=0)))
    assert "rug" in message and "runner" in message and "overlap" in message


def test_a_rug_in_front_of_a_door_is_accepted_and_takes_no_placement_rule(tmp_path) -> None:
    from app.compositions import rule_outcome
    from tests.test_design_rules import swing

    mat = {**rug(), "width_mm": 800, "depth_mm": 600, "placement": {"x_mm": 4250, "y_mm": 400, "rotation_deg": 0}}
    _stored, subjects = place(document(mat))
    assert subjects == []
    assert rule_outcome(_rules(tmp_path, swing(severity="refuse")), subjects) == (None, "")


def test_a_floor_layer_item_leaving_the_room_is_refused() -> None:
    assert "rug leaves the room Wohnen" in refusal(document(rug(x_mm=4800, y_mm=2000, rotation_deg=0)))


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


# --- the surface map (app-check-2026-10-09) -------------------------------------------------


def test_a_rooms_surface_map_names_each_wall_the_floor_the_ceiling_and_the_items() -> None:
    from app.blender.composition_contract import surface_map

    meshes = ["Ceiling", "Floor", "Wall_0_0", "Wall_0_1", "Wall_0_lintel_0", "Wall_1_0", "Wall_2_0",
              "Wall_3_0", "Wall_10_0", "cabinet-side", "STAND_sofa"]
    surfaces = surface_map(meshes, ["cabinet-side", "STAND_sofa"])
    assert list(surfaces) == ["wall 1", "wall 2", "wall 3", "wall 4", "wall 11", "floor", "ceiling", "items"]
    assert surfaces["wall 1"] == ["Wall_0_0", "Wall_0_1", "Wall_0_lintel_0"]
    assert surfaces["items"] == ["STAND_sofa", "cabinet-side"]
    assert sorted(n for names in surfaces.values() for n in names) == sorted(meshes)


def test_an_apartments_surfaces_are_named_by_room() -> None:
    from types import SimpleNamespace

    from app.blender.composition_contract import apartment_wall_labels, surface_map

    walls = [SimpleNamespace(id="wall-1", rooms=("Wohnen",)), SimpleNamespace(id="wall-2", rooms=("Wohnen", "Küche")),
             SimpleNamespace(id="wall-3", rooms=("Küche",))]
    labels = apartment_wall_labels(walls)
    assert labels == {"wall-1": "Wohnen: wall 1", "wall-2": "Wohnen: wall 2", "wall-3": "Küche: wall 1"}
    surfaces = surface_map(
        ["Wall_wall-1_0", "Wall_wall-2_0", "Wall_wall-3_0", "Floor_Wohnen", "Ceiling_Wohnen", "Floor_Küche"],
        [], labels,
    )
    assert list(surfaces) == [
        "Küche: wall 1", "Küche: floor", "Wohnen: wall 1", "Wohnen: wall 2", "Wohnen: floor", "Wohnen: ceiling",
    ]


def test_a_mesh_no_surface_takes_is_refused_by_name() -> None:
    from app.blender.composition_contract import surface_map

    with pytest.raises(SpecValidationError, match="no surface takes the mesh 'Lamp'"):
        surface_map(["Floor", "Lamp"], [])
