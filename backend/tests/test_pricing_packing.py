"""cut-list-pricing: `pack_sheets` (sheet yield) and `sheet_cost`.

No database needed - `pack_sheets` and `sheet_cost` are pure functions over
plain values.
"""

from __future__ import annotations

from app.db.models import SupplierPrice
from app.pricing.pricing import Part, pack_sheets, sheet_cost

SHEET_LENGTH_MM = 2500
SHEET_WIDTH_MM = 1250


def _entry(**overrides: object) -> SupplierPrice:
    """An in-memory price-list entry; `captured_cents` is the base price."""
    base = overrides.pop("captured_cents", 4999)
    values: dict[str, object] = {
        "key": "panel:oak-veneer-birch:18", "label": "Oak-veneered birch 18mm", "category": "panel",
        "unit": "per_m2", "sheet_width_mm": SHEET_WIDTH_MM, "sheet_length_mm": SHEET_LENGTH_MM,
        "thickness_mm": 18, "base_cents": base, "provenance": "manual",
    }
    values.update(overrides)
    return SupplierPrice(**values)  # type: ignore[arg-type]


# --- pack_sheets -----------------------------------------------------------------------


def test_a_batch_that_overflows_one_sheet_uses_two_with_utilisation_below_100() -> None:
    # 6 parts of 1200x600mm, grain-locked: 4 fit sheet 1 (2 shelves of 2),
    # the remaining 2 spill onto sheet 2.
    parts = [Part(id="P", length_mm=1200, width_mm=600, qty=6, grain_locked=True)]

    result = pack_sheets(parts, SHEET_LENGTH_MM, SHEET_WIDTH_MM)

    assert result.sheet_count == 2
    assert result.unfitting == ()
    assert len(result.placements) == 6
    assert 0 < result.utilisation_percent < 100


def test_an_oversize_part_that_fits_no_orientation_is_unfitting() -> None:
    # 2700x1300mm: exceeds the sheet's length both as-is and rotated.
    parts = [Part(id="TOO_BIG", length_mm=2700, width_mm=1300, qty=1, grain_locked=False)]

    result = pack_sheets(parts, SHEET_LENGTH_MM, SHEET_WIDTH_MM)

    assert result.sheet_count == 0
    assert result.placements == ()
    assert [p.id for p in result.unfitting] == ["TOO_BIG"]


def test_a_part_as_long_as_the_sheet_fits_and_the_kerf_is_charged_only_between_pieces() -> None:
    full = pack_sheets([Part("shelf", 2800, 400, 1, True)], 2800, 2070, kerf_mm=4)
    assert (full.sheet_count, full.unfitting) == (1, ())
    # Two 1398 mm pieces and one cut fill 2800 mm exactly; two of 1400 mm do not.
    snug = pack_sheets([Part("a", 1398, 400, 2, True)], 2800, 2070, kerf_mm=4)
    assert {p.shelf_index for p in snug.placements} == {0}
    tight = pack_sheets([Part("a", 1400, 400, 2, True)], 2800, 2070, kerf_mm=4)
    assert {p.shelf_index for p in tight.placements} == {0, 1}


def test_grain_locking_prevents_a_rotation_that_would_otherwise_fit() -> None:
    # 1200x1300mm: fails as-is (width 1300 > sheet width 1250), fits rotated
    # (1300x1200: length 1300 <= 2500, width 1200 <= 1250).
    locked = [Part(id="LOCKED", length_mm=1200, width_mm=1300, qty=1, grain_locked=True)]
    unlocked = [Part(id="FREE", length_mm=1200, width_mm=1300, qty=1, grain_locked=False)]

    locked_result = pack_sheets(locked, SHEET_LENGTH_MM, SHEET_WIDTH_MM)
    unlocked_result = pack_sheets(unlocked, SHEET_LENGTH_MM, SHEET_WIDTH_MM)

    assert locked_result.sheet_count == 0
    assert [p.id for p in locked_result.unfitting] == ["LOCKED"]

    assert unlocked_result.sheet_count == 1
    assert unlocked_result.unfitting == ()
    placed = unlocked_result.placements[0]
    assert placed.rotated is True
    assert placed.length_mm == 1300
    assert placed.width_mm == 1200


def test_packing_is_deterministic_across_two_runs() -> None:
    parts = [
        Part(id="A", length_mm=1200, width_mm=600, qty=3, grain_locked=True),
        Part(id="B", length_mm=800, width_mm=400, qty=4, grain_locked=False),
        Part(id="C", length_mm=2000, width_mm=200, qty=2, grain_locked=True),
    ]

    first = pack_sheets(parts, SHEET_LENGTH_MM, SHEET_WIDTH_MM)
    second = pack_sheets(parts, SHEET_LENGTH_MM, SHEET_WIDTH_MM)

    assert first == second


def test_two_grain_locked_parts_on_one_shelf_share_a_cut() -> None:
    # 800×100 mm, grain-locked: both sit on one shelf (length 804+804 ≤ 2500,
    # shelf height 104). The shared-cut count is one rip plus one crosscut
    # per piece (the cut that frees a piece is the first edge of the next),
    # so two pieces are 3 cuts. Two cuts per piece would be 4.
    parts = [Part(id="P", length_mm=800, width_mm=100, qty=2, grain_locked=True)]

    result = pack_sheets(parts, SHEET_LENGTH_MM, SHEET_WIDTH_MM)

    assert result.sheet_count == 1
    assert {placement.sheet_index for placement in result.placements} == {0}
    assert {placement.shelf_index for placement in result.placements} == {0}
    assert result.shared_cut_count == 3
    assert result.shared_cut_count < 2 * 2


def test_a_part_uses_an_earlier_sheets_leftover_height() -> None:
    # Sorted widest first. The 800 mm part fills most of sheet 0's height.
    # The two 500 mm parts do not fit beside it or in the leftover, so they
    # open sheet 1 and fill it. The 400 mm part is too tall for sheet 1's
    # leftover and short enough for sheet 0's, so it must not open a third sheet.
    parts = [
        Part(id="tall", length_mm=2000, width_mm=800, qty=1, grain_locked=True),
        Part(id="mid-a", length_mm=2000, width_mm=500, qty=1, grain_locked=True),
        Part(id="mid-b", length_mm=2000, width_mm=500, qty=1, grain_locked=True),
        Part(id="short", length_mm=2000, width_mm=400, qty=1, grain_locked=True),
    ]

    result = pack_sheets(parts, SHEET_LENGTH_MM, SHEET_WIDTH_MM)

    by_id = {placement.part_id: placement for placement in result.placements}
    assert result.sheet_count == 2
    assert by_id["short"].sheet_index == 0
    assert by_id["mid-a"].sheet_index == 1
    assert by_id["mid-b"].sheet_index == 1


def test_packing_does_not_depend_on_the_caller_supplied_order() -> None:
    forward = [
        Part(id="A", length_mm=1200, width_mm=600, qty=3, grain_locked=True),
        Part(id="B", length_mm=800, width_mm=400, qty=4, grain_locked=False),
    ]
    reversed_ = list(reversed(forward))

    assert pack_sheets(forward, SHEET_LENGTH_MM, SHEET_WIDTH_MM) == pack_sheets(
        reversed_, SHEET_LENGTH_MM, SHEET_WIDTH_MM
    )


# --- sheet_cost --------------------------------------------------------------------------


def test_sheet_cost_is_none_without_an_effective_price() -> None:
    entry = _entry(captured_cents=None)
    assert sheet_cost(entry, 2) is None


def test_sheet_cost_per_m2_charges_the_whole_sheet_area() -> None:
    entry = _entry(unit="per_m2", captured_cents=4999, sheet_length_mm=2500, sheet_width_mm=1250)
    # area = 2500mm x 1250mm = 3.125 m2; 4999 x 3.125 x 2 sheets = 31243.75 -> 31244.
    assert sheet_cost(entry, 2) == 31244


def test_sheet_cost_per_piece_is_price_times_sheets() -> None:
    entry = _entry(unit="per_piece", captured_cents=1999)
    assert sheet_cost(entry, 3) == 5997


def test_sheet_cost_rounds_half_up_to_the_cent() -> None:
    # 1000mm x 1005mm = 1.005 m2; 100 cents/m2 x 1.005 = 100.5 cents exactly.
    entry = _entry(unit="per_m2", captured_cents=100, sheet_length_mm=1000, sheet_width_mm=1005)
    assert sheet_cost(entry, 1) == 101


def test_sheet_cost_of_zero_sheets_is_zero() -> None:
    entry = _entry(unit="per_piece", captured_cents=1999)
    assert sheet_cost(entry, 0) == 0
