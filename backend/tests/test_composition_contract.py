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


# --- a ceiling-layer item hangs from the ceiling (composition-ceiling-layer) ---------------


def pendant(item_id="pendant", height_mm=1100, **placement):
    return {"id": item_id, "type": "model", "model_id": "c4l1", "name": "Pendelleuchte Calisto",
            "width_mm": 500, "depth_mm": 500, "height_mm": height_mm, "layer": "ceiling",
            "placement": placement or {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 0}}


def table(height_mm=750):
    return {"id": "table", "type": "stand-in", "name": "Table", "width_mm": 1600, "depth_mm": 900,
            "height_mm": height_mm, "colour": "#8a6a48", "placement": {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 0}}


def test_a_ceiling_layer_pendant_is_accepted_and_keeps_its_layer() -> None:
    stored, subjects = place(document(pendant()))
    assert stored["items"][0]["layer"] == "ceiling"
    # Wohnen's ceiling is 2600 mm: the 1100 mm pendant reaches down to 1500 mm.
    assert stored["resolved"]["items"][0]["base_mm"] == 1500.0
    assert subjects == []


def test_a_standing_item_records_no_base() -> None:
    stored, _subjects = place(document(sofa(), rug()))
    assert all("base_mm" not in item for item in stored["resolved"]["items"])


def test_a_piece_on_the_ceiling_layer_is_refused_as_an_unknown_field() -> None:
    assert "unknown items[0] field: layer" in refusal(document({**piece(), "layer": "ceiling"}))


def test_a_pendant_over_the_table_is_accepted_whichever_comes_first() -> None:
    place(document(table(), pendant()))
    place(document(pendant(), table()))


def test_a_pendant_resting_exactly_on_the_table_top_is_accepted() -> None:
    place(document(table(height_mm=1500), pendant()))


def test_a_pendant_hanging_into_a_cabinet_is_refused_naming_both() -> None:
    message = refusal(document(table(height_mm=1600), pendant()))
    assert "table" in message and "pendant" in message and "overlap" in message


def test_two_overlapping_pendants_are_refused_naming_both() -> None:
    message = refusal(document(pendant(), pendant("spot", height_mm=200, x_mm=2700, y_mm=2000, rotation_deg=0)))
    assert "pendant" in message and "spot" in message and "overlap" in message


def test_a_pendant_over_a_rug_is_accepted() -> None:
    place(document(rug(), pendant()))


def test_a_short_pendant_in_front_of_a_door_is_accepted_and_takes_no_placement_rule(tmp_path) -> None:
    from app.compositions import rule_outcome
    from tests.test_design_rules import swing

    # The door is 2100 mm high; a 300 mm pendant hangs down to 2300 mm.
    _stored, subjects = place(document(pendant(height_mm=300, x_mm=4250, y_mm=400, rotation_deg=0)))
    assert subjects == []
    assert rule_outcome(_rules(tmp_path, swing(severity="refuse")), subjects) == (None, "")


def test_a_long_pendant_in_front_of_a_door_is_refused() -> None:
    message = refusal(document(pendant(x_mm=4250, y_mm=400, rotation_deg=0)))
    assert "pendant blocks the door on wall 0" in message


def test_a_ceiling_layer_item_longer_than_the_room_is_high_is_refused() -> None:
    assert "taller than the ceiling" in refusal(document(pendant(height_mm=2700)))


def test_a_ceiling_layer_item_leaving_the_room_is_refused() -> None:
    assert "pendant leaves the room Wohnen" in refusal(document(pendant(x_mm=4900, y_mm=2000, rotation_deg=0)))


def test_a_ceiling_layer_item_hangs_from_its_own_rooms_ceiling() -> None:
    bad = {**L_ROOM, "height_mm": 2400}
    item = {**pendant(height_mm=300, x_mm=1000, y_mm=1000, rotation_deg=0), "room": "Bad"}
    stored, _subjects = place(
        document(item, scope={"apartment": "Wohnung"}), rooms={"Wohnen": WOHNEN, "Bad": bad}, scope_room=None,
    )
    assert stored["resolved"]["items"][0]["base_mm"] == 2100.0


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


# --- hidden items (hidden-room-items) -------------------------------------------------------


def test_a_hidden_sofa_is_accepted_and_keeps_the_flag() -> None:
    stored, _ = place(document({**sofa(), "hidden": True}))
    assert stored["items"][0]["hidden"] is True
    assert stored["resolved"]["items"][0]["hidden"] is True


def test_a_hidden_piece_is_accepted() -> None:
    stored, _ = place(document({**piece(), "hidden": True}))
    assert stored["items"][0]["hidden"] is True


def test_hidden_false_is_stored_as_no_flag() -> None:
    stored, _ = place(document({**armchair(), "hidden": False}))
    assert "hidden" not in stored["items"][0]
    assert "hidden" not in stored["resolved"]["items"][0]


def test_hidden_must_be_true_or_false() -> None:
    message = refusal(document({**sofa(), "hidden": "yes"}))
    assert "sofa" in message and "hidden" in message


def test_a_hidden_sofa_may_overlap_the_armchair_either_way() -> None:
    over = {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 0}
    place(document({**sofa(), "hidden": True}, armchair(**over)))
    place(document(armchair(**over), {**sofa(), "hidden": True}))


def test_a_hidden_item_in_front_of_a_door_is_accepted_and_takes_no_placement_rule(tmp_path) -> None:
    from app.compositions import rule_outcome
    from tests.test_design_rules import swing

    blocker = {**sofa(wall=0, offset_mm=3600), "width_mm": 1200, "hidden": True}
    _stored, subjects = place(document(blocker))
    assert subjects == []
    assert rule_outcome(_rules(tmp_path, swing(severity="refuse")), subjects) == (None, "")


def test_a_hidden_item_still_stays_inside_the_room() -> None:
    message = refusal(document({**sofa(x_mm=4800, y_mm=2000, rotation_deg=0), "hidden": True}))
    assert "sofa leaves the room Wohnen" in message


def test_a_hidden_item_still_takes_the_wall_and_ceiling_checks() -> None:
    assert "runs past the end of wall 1" in refusal(document({**sofa(wall=1, offset_mm=3000), "hidden": True}))
    assert "taller than the ceiling" in refusal(document({**sofa(), "height_mm": 2700, "hidden": True}))


# --- the floor finish (room-floor-finish) ---------------------------------------------------

TILES = {"tile_width_mm": 600, "tile_length_mm": 600, "tile_colour": "#E8E4DC", "grout_colour": "#9a958c",
         "grout_width_mm": 3}


def floored(finish) -> dict:
    return {**document(sofa()), "floor": finish}


def test_a_tiled_floor_is_accepted_with_the_grid_pattern() -> None:
    stored, _ = place(floored(TILES))
    assert stored["floor"] == {**TILES, "tile_colour": "#e8e4dc", "grout_width_mm": 3.0, "pattern": "grid"}


def test_a_staggered_plank_floor_with_no_grout_is_accepted() -> None:
    stored, _ = place(floored({**TILES, "tile_width_mm": 200, "tile_length_mm": 1200, "grout_width_mm": 0,
                               "pattern": "staggered"}))
    assert stored["floor"]["pattern"] == "staggered" and stored["floor"]["grout_width_mm"] == 0


def test_an_unknown_floor_field_is_refused_by_name() -> None:
    assert "texture" in refusal(floored({**TILES, "texture": "marble.png"}))


def test_a_tile_too_small_is_refused_naming_the_field_and_range() -> None:
    message = refusal(floored({**TILES, "tile_width_mm": 5}))
    assert "floor.tile_width_mm" in message and "20 to 2500" in message


def test_an_unknown_pattern_is_refused_naming_the_values() -> None:
    message = refusal(floored({**TILES, "pattern": "herringbone"}))
    assert "floor.pattern" in message and "grid" in message and "staggered" in message


def test_a_document_without_a_floor_keeps_none() -> None:
    stored, _ = place(document(sofa()))
    assert "floor" not in stored


# --- lamp lights (room-lamp-lights) ---------------------------------------------------------

ESSEN = {**WOHNEN, "height_mm": 2500}
WARM = {"type": "point", "lumens": 800, "kelvin": 2700}


def lit_pendant(**light):
    return {"id": "pendant", "type": "model", "model_id": "p1", "name": "Pendant", "width_mm": 500, "depth_mm": 500,
            "height_mm": 1100, "layer": "ceiling", "light": light or WARM,
            "placement": {"x_mm": 2500, "y_mm": 2000, "rotation_deg": 0}}


def test_a_pendant_with_a_warm_light_is_placed_50_mm_above_its_lowest_point() -> None:
    stored, _ = place(document(lit_pendant()), rooms={"Wohnen": ESSEN})
    assert stored["items"][0]["light"] == WARM
    light = stored["resolved"]["items"][0]["light"]
    assert light["at_mm"] == [2500, 2000, 1450] and light["watts"] == 40.0
    assert light["rgb"][0] == 1.0 and light["rgb"][2] < 0.2
    assert stored["resolved"]["rooms"][0]["rig_factor"] == 0.5


def test_a_standing_floor_lamp_lights_50_mm_below_its_top() -> None:
    lamp = {"id": "floor-lamp", "type": "stand-in", "name": "Floor lamp", "width_mm": 400, "depth_mm": 400,
            "height_mm": 1600, "colour": "#202020", "light": {"type": "spot", "lumens": 600, "kelvin": 3000},
            "placement": {"x_mm": 600, "y_mm": 600, "rotation_deg": 0}}
    stored, _ = place(document(lamp))
    assert stored["resolved"]["items"][0]["light"]["at_mm"][2] == 1550


def test_a_light_on_a_piece_is_refused_as_an_unknown_field() -> None:
    assert "light" in refusal(document({**piece(), "light": WARM}))


def test_a_light_on_a_rug_is_refused_naming_both() -> None:
    message = refusal(document({**rug(), "light": WARM}))
    assert "rug" in message and "light" in message


def test_an_unknown_light_type_or_brightness_is_refused() -> None:
    assert "type" in refusal(document(lit_pendant(type="area", lumens=800, kelvin=2700)), rooms={"Wohnen": ESSEN})
    assert "lumens" in refusal(document(lit_pendant(type="point", lumens=20000, kelvin=2700)), rooms={"Wohnen": ESSEN})
    assert "watts" in refusal(document(lit_pendant(type="point", lumens=800, kelvin=2700, watts=40)), rooms={"Wohnen": ESSEN})


def test_more_lights_than_the_limit_are_refused() -> None:
    lamps = [
        {"id": f"spot-{n}", "type": "stand-in", "name": "Spot", "width_mm": 100, "depth_mm": 100, "height_mm": 100,
         "colour": "#202020", "layer": "ceiling", "light": WARM,
         "placement": {"x_mm": 300 + (n % 9) * 450, "y_mm": 400 + (n // 9) * 1500, "rotation_deg": 0}}
        for n in range(17)
    ]
    assert "at most 16 lights, not 17" in refusal(document(*lamps))


def test_a_room_without_lamp_lights_keeps_its_rig() -> None:
    stored, _ = place(document(sofa()))
    assert stored["resolved"]["rooms"][0]["rig_factor"] == 1.0


def test_an_apartment_dims_only_the_lit_room() -> None:
    bad = {"corners_mm": [[5000, 0], [7000, 0], [7000, 2000], [5000, 2000]], "height_mm": 2400,
           "wall_thickness_mm": 100, "openings": []}
    lamp = {**lit_pendant(), "room": "Wohnen"}
    towel = {**sofa(), "id": "cabinet", "width_mm": 600, "depth_mm": 400, "room": "Bad",
             "placement": {"x_mm": 6000, "y_mm": 1000, "rotation_deg": 0}}
    stored, _ = place(document(lamp, towel, scope={"apartment": "Wohnung"}),
                      rooms={"Wohnen": ESSEN, "Bad": bad}, scope_room=None)
    factors = {room["name"]: room["rig_factor"] for room in stored["resolved"]["rooms"]}
    assert factors == {"Wohnen": 0.5, "Bad": 1.0}


# --- LED strips (room-led-strips) -----------------------------------------------------------

KUECHE = {"corners_mm": [[0, 0], [3000, 0], [3000, 3200], [0, 3200]], "height_mm": 2500, "wall_thickness_mm": 100,
          "openings": [{"wall": 1, "type": "window", "offset_mm": 1000, "width_mm": 1000, "height_mm": 1200, "sill_mm": 900}]}


def strip(item_id="under-cabinets", **fields):
    return {"id": item_id, "type": "led-strip", "name": "Under-cabinet strip", "length_mm": 2400, "lumens_per_m": 500,
            "kelvin": 3000, "mount_height_mm": 1450, "placement": {"wall": 2, "offset_mm": 400}, **fields}


def kueche(*items):
    return place(document(*items), rooms={"Wohnen": KUECHE})


def test_a_strip_under_the_wall_cabinets_is_accepted_beside_a_piece_on_that_wall() -> None:
    counter = {**sofa(wall=2, offset_mm=400), "id": "counter", "width_mm": 2400, "depth_mm": 600, "height_mm": 900}
    stored, subjects = kueche(counter, strip())
    resolved = stored["resolved"]["items"][1]
    assert stored["items"][1]["facing"] == "down"
    assert resolved["size_mm"] == {"w": 2400.0, "d": 15.0, "h": 10.0} and resolved["base_mm"] == 1450
    assert resolved["strip"]["watts"] == 60.0 and resolved["strip"]["facing"] == "down"
    assert [item_id for item_id, _ in subjects] == ["counter"]
    assert stored["resolved"]["rooms"][0]["rig_factor"] == 0.5


def test_a_strip_past_the_wall_end_is_refused() -> None:
    assert "runs past the end of wall 2" in refusal(document(strip(placement={"wall": 2, "offset_mm": 1000})),
                                                    rooms={"Wohnen": KUECHE})


def test_a_strip_across_a_window_at_its_height_is_refused_and_one_below_it_is_accepted() -> None:
    across = strip(mount_height_mm=1200, placement={"wall": 1, "offset_mm": 500})
    message = refusal(document(across), rooms={"Wohnen": KUECHE})
    assert "under-cabinets crosses the window on wall 1" in message
    kueche(strip(mount_height_mm=300, placement={"wall": 1, "offset_mm": 500}))


def test_two_strips_overlapping_on_a_wall_are_refused_naming_both() -> None:
    message = refusal(document(strip("a", placement={"wall": 0, "offset_mm": 0}),
                               strip("b", placement={"wall": 0, "offset_mm": 300})), rooms={"Wohnen": KUECHE})
    assert "LED strips a and b overlap on wall 0" in message
    kueche(strip("a", placement={"wall": 0, "offset_mm": 0}), strip("b", mount_height_mm=300, placement={"wall": 0, "offset_mm": 300}))


def test_a_strip_reaching_the_ceiling_is_refused() -> None:
    assert "reaches the ceiling" in refusal(document(strip(mount_height_mm=2495)), rooms={"Wohnen": KUECHE})


def test_a_free_standing_strip_is_refused() -> None:
    message = refusal(document(strip(placement={"x_mm": 1000, "y_mm": 1000, "rotation_deg": 0})), rooms={"Wohnen": KUECHE})
    assert "under-cabinets" in message and "fixed to a wall" in message


@pytest.mark.parametrize("field", ["height_mm", "colour", "layer", "light"])
def test_a_size_colour_layer_or_light_on_a_strip_is_refused_as_unknown(field) -> None:
    assert field in refusal(document(strip(**{field: 10})), rooms={"Wohnen": KUECHE})


@pytest.mark.parametrize(("field", "value"), [("length_mm", 50), ("lumens_per_m", 5000), ("kelvin", 9000), ("facing", "sideways")])
def test_strip_values_out_of_range_are_refused(field, value) -> None:
    assert field in refusal(document(strip(**{field: value})), rooms={"Wohnen": KUECHE})


def test_a_strip_counts_towards_the_light_limit() -> None:
    lamps = [{**lit_pendant(), "id": f"spot-{n}", "width_mm": 100, "depth_mm": 100, "height_mm": 100,
              "placement": {"x_mm": 300 + (n % 6) * 450, "y_mm": 400 + (n // 6) * 1000, "rotation_deg": 0}}
             for n in range(16)]
    message = refusal(document(*lamps, strip()), rooms={"Wohnen": KUECHE})
    assert "at most 16 lights, not 17" in message


# --- a wall-hung piece holds its height above the floor (conversation-continuity) -----------

HUNG_SIZES = {**PIECE_SIZE, "sideboard": (1350.0, 450.0, 800.0), "shelf": (1000.0, 300.0, 400.0)}


def hung(item_id="sideboard", **placement):
    return {"id": item_id, "type": "piece", "package_id": item_id, "version": 2, "placement": placement}


def kommode(**placement):
    return {"id": "kommode", "type": "stand-in", "name": "Kommode", "width_mm": 1350, "depth_mm": 450,
            "height_mm": 914, "colour": "#a08060", "placement": placement or {"wall": 1, "offset_mm": 0}}


def place_hung(doc):
    parsed = parse_composition(doc, max_items=30)
    geometry = {"Wohnen": room_geometry("Wohnen", WOHNEN)}
    return place_items(parsed, rooms=geometry, piece_sizes=HUNG_SIZES, scope_room="Wohnen")


def hung_refusal(doc) -> str:
    with pytest.raises(SpecValidationError) as caught:
        place_hung(doc)
    return str(caught.value)


def test_a_piece_hung_above_a_kommode_is_accepted_at_its_height() -> None:
    stored, _subjects = place_hung(document(kommode(), hung(wall=1, offset_mm=0, mount_height_mm=1700)))
    assert stored["items"][1]["placement"]["mount_height_mm"] == 1700
    resolved = {i["id"]: i for i in stored["resolved"]["items"]}
    assert resolved["sideboard"]["base_mm"] == 1700
    assert "base_mm" not in resolved["kommode"]


def test_a_saved_height_stored_as_a_float_is_accepted_flush_to_the_ceiling() -> None:
    # The saved place stores the height as computed (2600 - 800 = 1800.0), not as a whole number.
    stored, _subjects = place_hung(document(hung(wall=1, offset_mm=0, mount_height_mm=1800.0)))
    resolved = stored["resolved"]["items"][0]
    assert resolved["base_mm"] == 1800


def test_a_piece_without_a_height_stands_on_the_floor() -> None:
    message = hung_refusal(document(kommode(), hung(wall=1, offset_mm=0)))
    assert "kommode" in message and "sideboard" in message and "overlap" in message


def test_a_hung_piece_clashes_with_a_tall_item_below() -> None:
    tall = {**kommode(), "height_mm": 1500}
    message = hung_refusal(document(tall, hung(wall=1, offset_mm=0, mount_height_mm=1200)))
    assert "kommode" in message and "sideboard" in message and "overlap" in message


def test_a_hung_piece_above_the_ceiling_is_refused() -> None:
    message = hung_refusal(document(hung(wall=1, offset_mm=0, mount_height_mm=1900)))
    assert "item sideboard" in message and "2700 mm" in message and "2600 mm" in message


def test_a_hung_piece_above_a_door_clears_it() -> None:
    place_hung(document(hung("shelf", wall=0, offset_mm=3700, mount_height_mm=2150)))
    message = hung_refusal(document(hung("shelf", wall=0, offset_mm=3700, mount_height_mm=1500)))
    assert "blocks the door" in message


def test_a_hung_piece_above_a_window_clears_it() -> None:
    place_hung(document(hung("shelf", wall=2, offset_mm=1200, mount_height_mm=2150)))


def test_a_height_on_a_stand_in_is_refused() -> None:
    message = hung_refusal(document(kommode(wall=1, offset_mm=0, mount_height_mm=500)))
    assert "item kommode" in message and "mount_height_mm" in message


def test_a_height_on_a_free_placement_is_refused() -> None:
    message = hung_refusal(document(hung(x_mm=2000, y_mm=2000, rotation_deg=0, mount_height_mm=500)))
    assert "mount_height_mm" in message
