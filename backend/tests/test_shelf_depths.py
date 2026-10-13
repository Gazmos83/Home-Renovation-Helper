"""Per-shelf depth: schema, derive placement, overall, pin coverage, revise and summary."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.measurements import Requested, check
from app.agent.prompts import DESIGNER_SHELF_DEPTHS_NOTE, piece_note
from app.agent.revise import revise_spec
from app.blender.custom_build.derive import (
    DeriveError,
    check_adjustable_shelf_depths,
    derive,
    module_bounds,
    overall,
    shelf_boards,
    shelf_covers_pin_columns,
)
from app.blender.schemas import CustomBuildSpec, PackageChanges
from app.blender.spec_contract import SpecValidationError
from tests.drill_helpers import exact, inputs, sheet


def _build(**module) -> dict:
    entry = {
        "id": "cabinet",
        "name": "Cabinet",
        "x": 0,
        "y": 0,
        "z": 0,
        "width": 800,
        "height": 1600,
        "depth": 400,
        "carcass": "carcass",
        "back": "back",
        "shelves": 4,
    }
    entry.update(module)
    return {
        "kind": "custom_build",
        "schema_version": 1,
        "units": "mm",
        "name": "Cabinet",
        "materials": {
            "carcass": {"material": "18 mm oak-veneered birch", "thickness_mm": 18},
            "back": {"material": "12 mm birch plywood", "thickness_mm": 12},
        },
        "modules": [entry],
    }


def _valid(**module) -> dict:
    return CustomBuildSpec.model_validate(_build(**module)).model_dump(mode="json")


def _refusal(document: dict) -> str:
    try:
        CustomBuildSpec.model_validate(document)
    except (ValidationError, SpecValidationError) as error:
        return str(error)
    return "accepted"


def test_one_shelf_deeper_back_flush() -> None:
    document = _valid(shelf_depths_mm=[None, 500, None, None], shelf_depth_align="back")
    module = document["modules"][0]
    boards = shelf_boards(module, 18, 12)
    assert [board.depth for board in boards] == [388, 500, 388, 388]
    assert boards[1].y0 == pytest.approx(388 - 500)
    parts, _hardware, _assembly = derive(document)
    by_id = {part["id"]: part for part in parts}
    assert by_id["cabinet-shelf-1"]["w"] == 388 and by_id["cabinet-shelf-1"]["qty"] == 3
    assert by_id["cabinet-shelf-2"]["w"] == 500 and by_id["cabinet-shelf-2"]["qty"] == 1


def test_shallower_shelf_front_flush() -> None:
    document = _valid(
        back=None,
        shelves=3,
        shelf_depths_mm=[400, 400, 250],
        shelf_depth_align="front",
    )
    boards = shelf_boards(document["modules"][0], 18, 0)
    assert [board.depth for board in boards] == [400, 400, 250]
    assert boards[2].y0 == 0
    parts, _hardware, _assembly = derive(document)
    assert any(part["id"] == "cabinet-shelf-2" and part["w"] == 250 for part in parts)


def test_wrong_list_length_is_refused() -> None:
    message = _refusal(_build(shelf_depths_mm=[None, 500]))
    assert "modules[0].shelf_depths_mm" in message and "4 shelves expected" in message


def test_align_without_depths_is_refused() -> None:
    message = _refusal(_build(shelf_depth_align="front"))
    assert "shelf_depth_align" in message and "shelf_depths_mm" in message


def test_depth_below_minimum_is_refused() -> None:
    message = _refusal(_build(shelf_depths_mm=[None, 40, None, None]))
    assert "modules[0].shelf_depths_mm" in message and "50 mm" in message


def test_protruding_shelf_grows_overall_depth() -> None:
    document = _valid(shelf_depths_mm=[None, 500, None, None], shelf_depth_align="back")
    assert overall(document)["d"] >= 500


def test_depths_cleared_in_a_revision() -> None:
    document = _valid(shelf_depths_mm=[None, 500, None, None], shelf_depth_align="back")
    revised, lines = revise_spec(
        document, PackageChanges.model_validate({"modules": {"cabinet": {"shelf_depths_mm": []}}})
    )
    assert "shelf_depths_mm" not in revised["modules"][0]
    assert "shelf_depth_align" not in revised["modules"][0]
    assert any("shelf_depths_mm" in line and "not set" in line for line in lines)
    assert any("shelf_depth_align" in line and "not set" in line for line in lines)


def test_package_changes_accepts_depths() -> None:
    change = PackageChanges.model_validate(
        {"modules": {"cabinet": {"shelf_depths_mm": [None, 500, None, None], "shelf_depth_align": "back"}}}
    )
    assert change.modules["cabinet"].shelf_depths_mm == [None, 500, None, None]


def test_old_document_unchanged() -> None:
    document = _valid()
    assert "shelf_depths_mm" not in document["modules"][0]
    assert "shelf_depth_align" not in document["modules"][0]
    before = derive(document)[0]
    after = derive(_valid())[0]
    assert [(p["id"], p["qty"], p["l"], p["w"]) for p in before] == [
        (p["id"], p["qty"], p["l"], p["w"]) for p in after
    ]


def test_pin_coverage_helper() -> None:
    assert shelf_covers_pin_columns(-112, 500, 400, 37, 37)
    assert shelf_covers_pin_columns(30, 370, 400, 37, 37)
    assert not shelf_covers_pin_columns(100, 300, 400, 37, 37)


def _pin_inputs() -> dict:
    return inputs(
        {
            "shelf-pin": sheet(
                "shelf_pin",
                {
                    "front_setback_mm": exact(37),
                    "rear_setback_mm": exact(37),
                    "pins_per_shelf": 4,
                },
            )
        }
    )


def test_shallower_adjustable_shelf_still_covers_both_columns() -> None:
    document = _valid(
        back=None,
        shelves=0,
        adjustable_shelves=1,
        shelf_depths_mm=[370],
        shelf_depth_align="back",
    )
    check_adjustable_shelf_depths(document, _pin_inputs())
    derive(document, _pin_inputs())


def test_too_shallow_adjustable_shelf_is_refused() -> None:
    document = _valid(
        back=None,
        shelves=0,
        adjustable_shelves=1,
        shelf_depths_mm=[300],
        shelf_depth_align="back",
    )
    with pytest.raises(DeriveError, match="shelf_depths_mm"):
        check_adjustable_shelf_depths(document, _pin_inputs())


def test_piece_note_shows_depths() -> None:
    document = _valid(shelf_depths_mm=[None, 500, None, None], shelf_depth_align="back")
    note = piece_note("cabinet", 1, document)
    assert "shelf depths" in note and "500 mm" in note and "back-flush" in note


def test_designer_shelf_depths_note_names_the_fields() -> None:
    assert "shelf_depths_mm" in DESIGNER_SHELF_DEPTHS_NOTE
    assert "shelf_depth_align" in DESIGNER_SHELF_DEPTHS_NOTE
    assert "Never tell the owner there is no per-shelf depth field" in DESIGNER_SHELF_DEPTHS_NOTE
    assert "needs no separate `y` or envelope change" in DESIGNER_SHELF_DEPTHS_NOTE
    assert "Never clear or change `side_folds` to satisfy another rule" in DESIGNER_SHELF_DEPTHS_NOTE


def test_one_shelf_depth_is_covered_in_requested_measurements() -> None:
    current = _valid(shelves=4)
    revised = _valid(shelf_depths_mm=[None, 500, None, None], shelf_depth_align="back")
    entry = Requested("second shelf 500 mm deep", "cabinet", "shelf_depths_mm", 500)
    assert check([entry], ["second shelf 500 mm deep"], current, revised) == []


# --- auto-fit-protruding-shelves: a protruding shelf on a folded module --------------------------

HEIGHT_FOLD = {"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}
DEPTH_FOLD = {"side": "left", "from_mm": 200, "along": "depth", "angle_deg": 20, "towards": "inside"}


def test_a_back_aligned_shelf_past_the_folded_inner_depth_is_accepted() -> None:
    document = _valid(shelves=3, side_folds=[HEIGHT_FOLD], shelf_depths_mm=[None, None, 550], shelf_depth_align="back")
    assert document["modules"][0]["side_folds"] == [HEIGHT_FOLD]


def test_a_front_aligned_shelf_past_the_folded_inner_depth_is_still_refused() -> None:
    message = _refusal(
        _build(shelves=3, side_folds=[HEIGHT_FOLD], shelf_depths_mm=[None, None, 550], shelf_depth_align="front")
    )
    assert "modules[0].shelf_depths_mm" in message and "folded inner depth of 388 mm" in message


@pytest.mark.parametrize(("fold", "level"), [(HEIGHT_FOLD, 3), (DEPTH_FOLD, 2)])
def test_a_protruding_board_takes_the_width_the_fold_allows_inside_the_carcass(fold: dict, level: int) -> None:
    depths = [None, None, None]
    depths[level - 1] = 550
    module = _valid(shelves=3, side_folds=[fold], shelf_depths_mm=depths, shelf_depth_align="back")["modules"][0]
    plain = _valid(shelves=3, side_folds=[fold])["modules"][0]
    board = next(board for board in shelf_boards(module, 18, 12) if board.level == level)
    inside = next(board for board in shelf_boards(plain, 18, 12) if board.level == level)
    assert (board.depth, board.y0) == (550, -162)
    assert board.width == inside.width  # the part in front of the carcass adds no width limit
    # the bounds reach 162 mm in front of the module
    assert module_bounds(module, 18, 12)[1:5:3] == (-162, 562)


def test_a_folded_cabinet_keeps_its_fold_through_the_fit() -> None:
    document = _valid(shelves=3, side_folds=[HEIGHT_FOLD])
    document["envelope"] = {"width": 800, "height": 1600, "depth": 400}
    changes = PackageChanges(modules={"cabinet": {"shelf_depths_mm": [None, None, 550], "shelf_depth_align": "back"}})
    revised, lines = revise_spec(document, changes)
    module = revised["modules"][0]
    assert module["side_folds"] == [HEIGHT_FOLD] and module["y"] == 162
    assert revised["envelope"]["depth"] == 562
    assert not any("side_folds" in line for line in lines)
    CustomBuildSpec.model_validate(revised)
