"""hardware-drilling: the bracket calculation lists the cited end range and leaves inner brackets in words."""

from __future__ import annotations

from app.blender.custom_build.derive import drilling
from tests.drill_helpers import build, inputs, rules, wall_shelf

END = {"min": 100, "max": 200}


def _run(length: int, *, positions: list[int] | None = None, rule_set: dict | None = None) -> dict:
    shelf = wall_shelf(length=length, **({"bracket_positions_mm": positions} if positions else {}))
    return drilling(build(wall_shelves=[shelf]), inputs(rule_set=rules(end=END) if rule_set is None else rule_set))


def _entry(result: dict) -> dict:
    (entry,) = result["entries"]
    return entry


def test_1200_mm_gives_two_brackets_at_the_cited_range_from_each_end() -> None:
    result = _run(1200)
    entry = _entry(result)
    assert [p["position"] for p in entry["positions"]] == [{"min_mm": 100, "max_mm": 200}] * 2
    assert "100–200 mm from each end" in entry["text"] and "topnotch-shelf-brackets" in entry["text"]
    assert result["counts"]["brackets"] == 2 and result["complete"] and result["warnings"] == []


def test_1500_mm_gives_three_with_the_middle_one_in_words() -> None:
    entry = _entry(_run(1500))
    assert [p["position"] for p in entry["positions"]][1] == {"rule": "evenly spaced between them"}
    assert len(entry["positions"]) == 3 and "bracket 2 evenly spaced between them" in entry["text"]


def test_2400_mm_gives_four() -> None:
    assert _run(2400)["counts"]["brackets"] == 4


def test_no_single_end_distance_appears_in_the_output() -> None:
    for length in (1200, 1500, 2400):
        text = str(_run(length))
        assert "150" not in text.replace("1500", "")


def test_a_range_is_not_marked_incomplete() -> None:
    assert _run(1500)["complete"]


def test_a_180_mm_board_is_too_short() -> None:
    result = _run(180)
    entry = _entry(result)
    assert entry["positions"] == [] and entry["problem"] == "board too short for the bracket end distance"
    assert "board too short for the bracket end distance" in result["warnings"][0]
    assert not result["complete"] and result["counts"]["brackets"] is None


def test_a_missing_rule_blanks_the_positions_and_the_count() -> None:
    result = _run(1200, rule_set=rules(count=False, end=END))
    entry = _entry(result)
    assert entry["positions"] == [] and result["counts"]["brackets"] is None
    assert "bracket count rule" in result["warnings"][0]
    assert "bracket end distance" in _run(1200, rule_set=rules())["warnings"][0]


def test_owner_positions_are_kept_and_marked() -> None:
    result = _run(1200, positions=[150, 600, 1050])
    entry = _entry(result)
    assert [p["position"] for p in entry["positions"]] == [{"mm": 150}, {"mm": 600}, {"mm": 1050}]
    assert "set by the owner" in entry["text"] and result["counts"]["brackets"] == 3
    assert result["complete"]


def test_an_exact_end_distance_gives_exact_evenly_spaced_positions() -> None:
    result = _run(1500, rule_set=rules(end={"value": 150}))
    assert [p["position"]["mm"] for p in _entry(result)["positions"]] == [150, 750, 1350]
