"""design-guidelines: the bracket count and spacing checks judge the owner's wall-shelf positions."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.guidelines.checks import CHECKS
from app.guidelines.rules import DesignRulesError, evaluate, load_rules, partition
from tests.drill_helpers import COUNT_TABLE, build, wall_shelf

SOURCE = {"publication": "asr-a1-2", "section": "5.1", "quote": "a quoted clause"}


def _rules(tmp_path: Path, *, count: bool = True, spacing: bool = True) -> tuple:
    entries = []
    if count:
        entries.append({
            "id": "bracket-count", "applies_to": "piece", "check": "shelf_bracket_count_for_length",
            "params": {"table": COUNT_TABLE}, "severity": "warn", "source": SOURCE,
        })
    if spacing:
        entries.append({
            "id": "bracket-spacing", "applies_to": "piece", "check": "shelf_bracket_spacing_mm",
            "params": {"end_distance_mm": {"min": 100, "max": 200, "unit": "mm"}, "even_tolerance_mm": 10},
            "severity": "warn", "source": SOURCE,
        })
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump({"rules": entries}))
    return load_rules(path, known_sources=frozenset({"asr-a1-2"}))


def _warnings(tmp_path: Path, length: int, positions: list[int] | None) -> list[str]:
    shelf = wall_shelf(length=length, **({"bracket_positions_mm": positions} if positions else {}))
    _refusals, warnings = partition(evaluate(_rules(tmp_path), "piece", build(wall_shelves=[shelf])))
    return [finding.text() for finding in warnings]


def test_too_few_brackets_for_a_long_shelf_names_the_rule_shelf_count_limit_and_source(tmp_path: Path) -> None:
    (text,) = [t for t in _warnings(tmp_path, 1500, [150, 1350]) if t.startswith("bracket-count")]
    assert "wall-shelf-1" in text and "2 brackets" in text and "at least 3" in text and "(asr-a1-2, 5.1)" in text


def test_a_length_between_two_rows_uses_the_next_row(tmp_path: Path) -> None:
    assert not [t for t in _warnings(tmp_path, 650, [150, 500]) if t.startswith("bracket-count")]


def test_longer_than_the_table_uses_the_last_row(tmp_path: Path) -> None:
    (text,) = [t for t in _warnings(tmp_path, 2400, [150, 1200, 2250]) if t.startswith("bracket-count")]
    assert "3 brackets" in text and "at least 4" in text


def test_an_outer_bracket_too_close_to_an_end_is_warned_for_each_end(tmp_path: Path) -> None:
    ends = [t for t in _warnings(tmp_path, 1200, [50, 600, 1150]) if t.startswith("bracket-spacing")]
    assert len(ends) == 2
    assert all("50 mm" in t and "100 to 200 mm" in t for t in ends)
    assert "left end" in ends[0] and "right end" in ends[1]


def test_uneven_inner_spacing_names_the_largest_difference_and_the_tolerance(tmp_path: Path) -> None:
    (text,) = [t for t in _warnings(tmp_path, 1800, [150, 500, 1650]) if "gaps" in t]
    assert "largest difference from the mean gap 400 mm" in text and "at most 10 mm" in text


def test_a_single_bracket_is_judged_on_its_end_distances_only(tmp_path: Path) -> None:
    found = [t for t in _warnings(tmp_path, 300, [150]) if t.startswith("bracket-spacing")]
    assert found == []  # 150 mm from each end is inside 100 to 200 mm, and there are no gaps
    assert not any("gaps" in t for t in _warnings(tmp_path, 900, [450]))


def test_calculated_brackets_pass_and_the_spacing_check_is_not_applied_to_them(tmp_path: Path) -> None:
    spec = build(wall_shelves=[wall_shelf(length=1500)])
    assert evaluate(_rules(tmp_path), "piece", spec) == []
    assert [m for rule in _rules(tmp_path) for m in CHECKS[rule.check].run(spec, rule.params)] == []


def test_the_owners_good_positions_give_no_warning(tmp_path: Path) -> None:
    assert _warnings(tmp_path, 1200, [150, 600, 1050]) == []


@pytest.mark.parametrize("bad", [{"min": 200, "max": 100, "unit": "mm"}, {"min": 100, "max": 200, "unit": "cm"}])
def test_the_end_range_must_be_an_ordered_range_in_mm(tmp_path: Path, bad: dict) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump({"rules": [{
        "id": "bracket-spacing", "applies_to": "piece", "check": "shelf_bracket_spacing_mm",
        "params": {"end_distance_mm": bad, "even_tolerance_mm": 10}, "severity": "warn", "source": SOURCE,
    }]}))
    with pytest.raises(DesignRulesError, match="bracket-spacing"):
        load_rules(path, known_sources=frozenset({"asr-a1-2"}))
