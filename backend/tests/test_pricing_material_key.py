"""cut-list-pricing: `material_key`, run against the materials the fold-down desk derives.

Every distinct material string a package derives is a test case: a phrasing the
vocabulary misses must be loud (`unknown:<slug>`), never silently mis-priced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.blender.custom_build.derive import derive
from app.pricing.pricing import material_key

TEMPLATE = Path(__file__).resolve().parents[1] / "fixtures" / "packages" / "templates" / "fold-down-desk.json"


def test_every_material_the_fold_down_desk_derives_is_priced_or_loudly_unknown() -> None:
    parts, _hardware, _assembly = derive(json.loads(TEMPLATE.read_text(encoding="utf-8")))
    keys = {material_key(str(row["material"])) for row in parts}
    assert keys, "the desk derives parts"
    for key in keys:
        assert key.startswith(("panel:", "stock:", "unknown:")), key


EXPECTED = {
    "12 mm birch plywood": "panel:birch-ply:12",
    "18 mm birch": "panel:birch:18",
    "18 mm black MDF": "panel:black-mdf:18",
    "18 mm oak, ripped to 16": "unknown:18-mm-oak-ripped-to-16",
    "18 mm oak-veneered birch": "panel:oak-veneer-birch:18",
    "25×25×2 mm SHS, black powder coat": "stock:steel-shs-25",
    "30 mm birch + black furniture linoleum": "panel:birch:30",
    "30 mm oak-veneered birch": "panel:oak-veneer-birch:30",
    "black anodised aluminium flat bar": "stock:aluminium-flat",
}


@pytest.mark.parametrize(("material", "expected"), sorted(EXPECTED.items()))
def test_each_known_material_string_maps_as_expected(material: str, expected: str) -> None:
    assert material_key(material) == expected


def test_an_unknown_phrase_is_reported_not_guessed() -> None:
    assert material_key("Recycled ocean plastic sheet, 9 mm") == "unknown:recycled-ocean-plastic-sheet-9-mm"


def test_the_oak_veneered_phrase_wins_over_the_bare_birch_fallback() -> None:
    assert material_key("18 mm oak-veneered birch") != material_key("18 mm birch")


def test_matching_is_case_insensitive() -> None:
    assert material_key("18 MM OAK-VENEERED BIRCH") == "panel:oak-veneer-birch:18"


def test_a_cross_section_spec_never_yields_a_bogus_leading_thickness() -> None:
    """"25×25×2 mm SHS" has no *leading* "<n> mm" - only "25" for the SHS size."""
    assert material_key("25×25×2 mm SHS, black powder coat") == "stock:steel-shs-25"


# --- the sheet families toom sells (material-review-on-import) --------------------------


@pytest.mark.parametrize(
    ("material", "expected"),
    [
        ("15 mm Multiplexplatte Birke", "panel:multiplex-birch:15"),
        ("18 mm Multiplex birch", "panel:multiplex-birch:18"),
        ("18 mm Tischlerplatte", "panel:tischlerplatte:18"),
        ("24 mm blockboard", "panel:tischlerplatte:24"),
        ("18 mm Leimholzplatte Fichte", "panel:leimholz-spruce:18"),
        ("27 mm Leimholz spruce", "panel:leimholz-spruce:27"),
        ("18 mm Leimholzplatte Buche", "panel:leimholz-beech:18"),
        ("18 mm Leimholz beech", "panel:leimholz-beech:18"),
        ("18 mm MDF", "panel:mdf:18"),
        ("19 mm Möbelbauplatte Erle foliert", "panel:moebelbauplatte:19"),
        ("19 mm furniture board", "panel:moebelbauplatte:19"),
    ],
)
def test_each_toom_sheet_family_maps_to_its_own_class(material: str, expected: str) -> None:
    assert material_key(material) == expected


def test_raw_mdf_is_distinct_from_black_mdf() -> None:
    assert material_key("18 mm MDF") == "panel:mdf:18"
    assert material_key("18 mm black MDF") == "panel:black-mdf:18"


def test_multiplex_birch_is_never_read_as_plain_birch() -> None:
    assert material_key("18 mm Multiplex birch") != material_key("18 mm birch")


def test_a_family_without_a_leading_thickness_is_still_unknown() -> None:
    assert material_key("Leimholzplatte Buche") == "unknown:leimholzplatte-buche"
