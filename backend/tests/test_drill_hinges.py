"""hardware-drilling: the hinge calculation lists positions, cup values and plates, ranges kept as ranges."""

from __future__ import annotations

from app.blender.custom_build.derive import drilling
from tests.drill_helpers import SOURCE, build, exact, inputs, module, ranged, sheet

HINGE = {
    "cup_diameter_mm": exact(35), "cup_depth_mm": exact(13), "cup_edge_distance_mm": exact(5),
    "end_distance_mm": exact(100), "plate_item": "plate-110", "plate_setback_mm": exact(37),
    "plate_hole_spacing_mm": exact(32),
}


def _run(values: dict | None, *, height: int = 1200, doors: int = 1, key: str = "hinge-concealed-110", **front) -> dict:
    spec = build(modules=[module(height=height, fronts=[{"type": "door", "count": doors, "opening": "hinge", **front}])])
    sheets = {key: sheet("hinge", values)} if values is not None else {}
    return drilling(spec, inputs(sheets))


def _door(result: dict) -> dict:
    return next(e for e in result["entries"] if e["part"] == "m-door-1")


def _plates(result: dict) -> dict:
    return next(e for e in result["entries"] if e["what"].startswith("mounting plates"))


def _positions(entry: dict) -> dict:
    return {p["label"]: p["position"] for p in entry["positions"]}


def test_a_1200_mm_door_has_three_hinges_cup_values_and_plates() -> None:
    result = _run(HINGE)
    door = _door(result)
    # door height 1200 - 3 mm gap; hinges at 100 from each end, one midway
    hinges = [p["position"]["mm"] for p in door["positions"] if p["label"] in {"1", "2", "3"}]
    assert hinges == [100, 598.5, 1097]
    assert _positions(door)["cup centre"] == {"mm": 22.5}
    assert "cup Ø 35 mm" in door["text"]
    assert all(v["source"] == SOURCE for v in door["values"])
    plates = _plates(result)
    assert len(plates["positions"]) == 3 and plates["missing"] == []
    assert plates["positions"][0]["position"] == {"mm": 101.5}  # door starts 1.5 mm above the module bottom
    assert result["complete"]


def test_the_sheets_count_table_replaces_the_height_rule() -> None:
    result = _run(HINGE | {"count_table": [{"max_height_mm": 1500, "hinges": 4}]})
    assert len([p for p in _door(result)["positions"] if p["label"].isdigit()]) == 4


def test_a_missing_cup_edge_distance_blanks_only_the_cup_offset() -> None:
    values = {k: v for k, v in HINGE.items() if k != "cup_edge_distance_mm"}
    result = _run(values)
    door = _door(result)
    assert "cup centre" not in _positions(door) and len([p for p in door["positions"] if p["label"].isdigit()]) == 3
    assert "drilling positions missing: cup edge distance" in result["warnings"][0]
    assert not result["complete"]


def test_a_ranged_end_distance_gives_outer_hinges_and_plates_as_ranges_and_the_inner_in_words() -> None:
    result = _run(HINGE | {"end_distance_mm": ranged(80, 120)})
    door = _door(result)
    positions = _positions(door)
    assert positions["1"] == {"min_mm": 80, "max_mm": 120} and positions["3"] == {"min_mm": 80, "max_mm": 120}
    assert positions["2"] == {"rule": "evenly spaced between them"}
    assert "80–120 mm from each end" in door["text"]
    plates = _positions(_plates(result))
    assert plates["plate 1"] == {"min_mm": 81.5, "max_mm": 121.5}
    assert plates["plate 3"] == {"min_mm": 1197 - 120 + 1.5, "max_mm": 1197 - 80 + 1.5}
    assert plates["plate 2"] == {"rule": "level with its hinge"}
    assert result["warnings"] == [] and result["complete"]


def test_an_exact_cup_diameter_stays_exact_and_a_ranged_edge_distance_gives_a_range() -> None:
    result = _run(HINGE | {"cup_edge_distance_mm": ranged(3, 6)})
    centre = _positions(_door(result))["cup centre"]
    assert centre == {"min_mm": 20.5, "max_mm": 23.5}
    assert "cup Ø 35 mm" in _door(result)["text"]
    both = _positions(_door(_run(HINGE | {"cup_diameter_mm": ranged(34, 36)})))["cup centre"]
    assert "rule" in both and "34–36 mm" in both["rule"]


def test_two_hinge_items_never_share_values() -> None:
    spec = build(modules=[module(fronts=[
        {"type": "door", "count": 1, "opening": "hinge", "hinge": "hinge-a"},
        {"type": "door", "count": 1, "opening": "hinge", "hinge": "hinge-b"},
    ])])
    result = drilling(spec, inputs({"hinge-a": sheet("hinge", HINGE)}))
    first, second = (e for e in result["entries"] if e["what"] == "hinges")
    assert first["missing"] == [] and "cup centre" in _positions(first)
    assert second["missing"] == ["no data sheet for hinge-b"] and second["positions"] == []
    assert "cup" not in second["text"].replace("blank", "")


def test_borings_are_counted_even_with_no_data() -> None:
    result = _run(None, height=700, doors=4)
    assert result["counts"]["hinge_cup_borings"] == 8
    assert not result["complete"] and "no data sheet for hinge-concealed-110" in result["warnings"][0]


def test_hinge_plates_on_a_folded_left_side_sit_on_the_sloped_board() -> None:
    spec = build(
        modules=[
            module(
                width=800,
                height=2000,
                depth=400,
                fronts=[{"type": "door", "count": 2, "opening": "hinge"}],
                side_folds=[
                    {"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}
                ],
            )
        ]
    )
    result = drilling(spec, inputs({"hinge-concealed-110": sheet("hinge", HINGE)}))
    plates = [e for e in result["entries"] if e["what"].startswith("mounting plates")]
    parts = {e["part"] for e in plates}
    assert "m-side" not in parts
    assert "m-side-left-upper" in parts
    upper = next(e for e in plates if e["part"] == "m-side-left-upper")
    assert "sloped board" in upper["text"]
    assert any(p["position"].get("mm", 0) > 0 for p in upper["positions"])


def test_an_unfolder_module_still_names_the_side_row() -> None:
    result = _run(HINGE, height=1200, doors=1)
    assert _plates(result)["part"] == "m-side"
    assert _door(result)["part"] == "m-door-1"
