"""restyle-variants: a request becomes validated plans, or is refused by name."""

from __future__ import annotations

import pytest

from app.restyle.presets import DEFAULT_LOOKS_PATH, DEFAULT_STYLES_PATH, load_presets
from app.restyle.request import (
    RestyleRefused,
    expand_looks,
    piece_variants,
    room_variants,
)

PRESETS = load_presets(DEFAULT_LOOKS_PATH, DEFAULT_STYLES_PATH)
SPEC = {
    "materials": {
        "carcass": {"material": "18 mm oak-veneered birch", "thickness_mm": 18},
        "fronts": {"material": "18 mm black MDF", "thickness_mm": 18},
    }
}
SHARED = {
    "materials": {
        "carcass": {"material": "18 mm birch plywood", "thickness_mm": 18},
        "shelves": {"material": "18 mm birch plywood", "thickness_mm": 18},
    }
}


def test_two_slots_are_resolved_to_their_material_strings() -> None:
    [plan] = piece_variants(SPEC, [{"carcass": "walnut", "fronts": "sage-green"}], PRESETS)
    assert set(plan.payload["materials"]) == {"18 mm oak-veneered birch", "18 mm black MDF"}
    assert plan.payload["materials"]["18 mm oak-veneered birch"]["colour"] == "#5a3e2b"
    assert plan.record["looks"] == {"carcass": "walnut", "fronts": "sage-green"}
    assert plan.base_id == "sage-green-walnut"
    assert "appearance only" in plan.note


def test_the_spec_is_not_changed() -> None:
    before = repr(SPEC)
    piece_variants(SPEC, [{"carcass": "walnut"}], PRESETS)
    assert repr(SPEC) == before


def test_unknown_slot_names_it_and_lists_the_slots() -> None:
    with pytest.raises(RestyleRefused) as caught:
        piece_variants(SPEC, [{"legs": "walnut"}], PRESETS)
    assert caught.value.field == "legs"
    assert "carcass" in caught.value.reason and "fronts" in caught.value.reason


def test_unknown_look_lists_the_looks() -> None:
    with pytest.raises(RestyleRefused, match="walnut"):
        piece_variants(SPEC, [{"carcass": "mahogany"}], PRESETS)


def test_composed_look_is_validated_and_extra_field_refused() -> None:
    [plan] = piece_variants(
        SPEC, [{"carcass": {"colour": "#2f3b34", "roughness": 0.35, "metallic": 0}}], PRESETS
    )
    assert plan.record["looks"] == {"carcass": "custom"}
    with pytest.raises(RestyleRefused) as caught:
        piece_variants(SPEC, [{"carcass": {"colour": "#2f3b34", "roughness": 0.3, "texture_path": "x"}}], PRESETS)
    assert caught.value.field == "texture_path"
    with pytest.raises(RestyleRefused) as caught:
        piece_variants(SPEC, [{"carcass": {"colour": "#2f3b34", "roughness": 0.3, "thickness_mm": 20}}], PRESETS)
    assert caught.value.field == "thickness_mm"


def test_slots_sharing_a_material_must_be_named_together_with_one_look() -> None:
    with pytest.raises(RestyleRefused) as caught:
        piece_variants(SHARED, [{"carcass": "walnut", "shelves": "oak"}], PRESETS)
    assert "carcass" in caught.value.reason and "shelves" in caught.value.reason
    with pytest.raises(RestyleRefused) as caught:
        piece_variants(SHARED, [{"carcass": "walnut"}], PRESETS)
    assert "shelves" in caught.value.reason
    [plan] = piece_variants(SHARED, [{"carcass": "walnut", "shelves": "walnut"}], PRESETS)
    assert list(plan.payload["materials"]) == ["18 mm birch plywood"]


def test_empty_and_oversized_requests_are_refused() -> None:
    with pytest.raises(RestyleRefused):
        piece_variants(SPEC, [], PRESETS)
    with pytest.raises(RestyleRefused):
        piece_variants(SPEC, [{}], PRESETS)
    with pytest.raises(RestyleRefused, match="at most"):
        piece_variants(SPEC, [{"carcass": "walnut"}] * 7, PRESETS)


def test_expand_looks_applies_each_look_to_the_same_slots() -> None:
    assert expand_looks(["walnut", "oak"], ["carcass"], PRESETS) == [{"carcass": "walnut"}, {"carcass": "oak"}]
    assert len(expand_looks(["all"], ["carcass"], PRESETS)) == len(PRESETS.looks)
    with pytest.raises(RestyleRefused, match="slots"):
        expand_looks(["walnut"], [], PRESETS)


def test_room_all_expands_to_every_style() -> None:
    plans = room_variants(["all"], PRESETS)
    assert [p.base_id for p in plans] == list(PRESETS.styles)
    assert plans[0].payload["mode"] == "room"
    assert plans[0].payload["style"]["wall"]["colour"].startswith("#")


def test_room_unknown_style_and_bad_composed_style() -> None:
    with pytest.raises(RestyleRefused, match="scandi"):
        room_variants(["gothic"], PRESETS)
    with pytest.raises(RestyleRefused) as caught:
        room_variants([{"wall": {"colour": "#fff", "roughness": 0.5}}], PRESETS)
    assert caught.value.field is not None
