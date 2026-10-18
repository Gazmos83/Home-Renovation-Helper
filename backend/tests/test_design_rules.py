"""design-guidelines: the rules table loads strictly and the four checks warn or refuse in code."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.agent import house_file
from app.agent.tools.base import Confirmation
from app.agent.tools.create_piece import preview, run
from app.agent.tools.revise_package import preview as revise_preview
from app.agent.tools.room_fit import run as room_fit_run
from app.blender.room_contract import normalise_room_scene
from app.guidelines.checks import CHECKS
from app.guidelines.rules import DesignRulesError, evaluate, load_rules, partition
from tests.api_helpers import desk
from tests.conftest import wait_for_status

SOURCES = frozenset({"asr-a1-2"})
SOURCE = {"publication": "asr-a1-2", "section": "5.1", "quote": "a quoted clause"}


def rule(rule_id: str, check: str, params: dict, *, applies_to: str, severity: str = "warn") -> dict:
    return {"id": rule_id, "applies_to": applies_to, "check": check, "params": params,
            "severity": severity, "source": SOURCE}


def table(tmp_path: Path, *rules: dict) -> tuple:
    import yaml

    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump({"rules": list(rules)}))
    return load_rules(path, known_sources=SOURCES)


def passage(min_mm: float, severity: str = "warn") -> dict:
    return rule("passage", "front_clearance_mm", {"min_mm": min_mm}, applies_to="placement", severity=severity)


def swing(severity: str = "warn") -> dict:
    return rule("swing", "door_swing_clear", {}, applies_to="placement", severity=severity)


def height(severity: str = "warn") -> dict:
    return rule("top", "height_range_mm", {"match": ["cabinet"], "min_mm": 700, "max_mm": 1000},
                applies_to="piece", severity=severity)


def span(max_span: float, severity: str = "warn") -> dict:
    return rule("span", "shelf_span_mm_for_thickness",
                {"table": [{"thickness_mm": 18, "max_span_mm": max_span}]}, applies_to="piece", severity=severity)


def room_context(*, door_wall: int | None = None):
    openings = [] if door_wall is None else [
        {"wall": door_wall, "type": "door", "offset_mm": 100, "width_mm": 800, "height_mm": 2000, "sill_mm": 0}
    ]
    document = {
        "kind": "room_scene", "schema_version": 1, "units": "mm",
        "room": {"corners": [[0, 0], [3000, 0], [3000, 2000], [0, 2000]], "height_mm": 2500, "wall_thickness_mm": 100},
        "openings": openings, "placement": {"wall": 0, "offset_mm": 2000}, "furnishings": [],
        "output": {"kind": "still"},
    }
    return normalise_room_scene(document, package_overall={"w": 1000.0, "h": 1450.0, "d": 300.0})


# --- loading ----------------------------------------------------------------------------


def test_the_shipped_table_loads() -> None:
    shipped = {r.check: r for r in load_rules()}
    assert set(shipped) == {
        "shelf_bracket_count_for_length", "shelf_bracket_spacing_mm", "shelf_pin_count_for_width", "hinge_count_for_height",
    }
    assert all(r.severity == "warn" for r in shipped.values())
    assert all(shipped[check].source.publication == "topnotch-shelf-brackets"
               for check in ("shelf_bracket_count_for_length", "shelf_bracket_spacing_mm"))
    spacing = shipped["shelf_bracket_spacing_mm"].params
    assert (spacing.end_distance_mm.min, spacing.end_distance_mm.max, spacing.end_distance_mm.unit) == (100, 200, "mm")
    assert [(row.max_length_mm, row.min_brackets) for row in shipped["shelf_bracket_count_for_length"].params.table] == [
        (600, 2), (1200, 2), (1800, 3), (2000, 4),
    ]


def test_every_check_is_loadable_by_its_name(tmp_path: Path) -> None:
    spacing = rule("spacing", "shelf_bracket_spacing_mm",
                   {"end_distance_mm": {"min": 100, "max": 200, "unit": "mm"}, "even_tolerance_mm": 10},
                   applies_to="piece")
    rules = table(tmp_path, passage(900), swing(), height(), span(1000), bracket_count(), spacing,
                  pin_count(), hinge_count(), rail_supports())
    assert {r.check for r in rules} == set(CHECKS)


def test_a_rule_without_a_source_fails_naming_the_rule(tmp_path: Path) -> None:
    bad = passage(900) | {"id": "no-source"}
    del bad["source"]
    with pytest.raises(DesignRulesError, match="'no-source' has no source"):
        table(tmp_path, bad)


def test_a_blank_quote_counts_as_no_source(tmp_path: Path) -> None:
    with pytest.raises(DesignRulesError, match="'passage' has no source"):
        table(tmp_path, passage(900) | {"source": SOURCE | {"quote": " "}})


@pytest.mark.parametrize(("change", "message"), [
    ({"check": "made_up"}, "unknown check 'made_up'"),
    ({"source": SOURCE | {"publication": "elsewhere"}}, "neither in guideline_sources.yaml nor an owner note"),
    ({"applies_to": "piece"}, "applies to a placement"),
    ({"params": {"min_mm": 900, "extra": 1}}, "parameters"),
])
def test_a_bad_rule_names_its_id(tmp_path: Path, change: dict, message: str) -> None:
    with pytest.raises(DesignRulesError, match=f"rule 'passage'.*{message}"):
        table(tmp_path, passage(900) | change)


def test_an_owner_note_is_an_accepted_source(tmp_path: Path) -> None:
    note = "owner:11111111-2222-3333-4444-555555555555"
    assert table(tmp_path, passage(900) | {"source": SOURCE | {"publication": note}})


# --- placement checks ---------------------------------------------------------------------


def test_front_clearance_measures_the_free_run_to_the_opposite_wall(tmp_path: Path) -> None:
    findings = evaluate(table(tmp_path, passage(2000)), "placement", room_context())
    assert [f.measurement.value for f in findings] == ["1700 mm"]
    assert evaluate(table(tmp_path, passage(1700)), "placement", room_context()) == []


def test_a_door_swing_overlap_is_a_breach_and_a_clear_door_is_not(tmp_path: Path) -> None:
    rules = table(tmp_path, swing())
    assert [f.measurement.limit for f in evaluate(rules, "placement", room_context(door_wall=1))] == ["no overlap"]
    assert evaluate(rules, "placement", room_context(door_wall=2)) == []


# --- piece checks -------------------------------------------------------------------------


def test_height_range_and_shelf_span_measure_the_derived_spec(tmp_path: Path) -> None:
    spec = desk()
    found = evaluate(table(tmp_path, height(), span(900)), "piece", spec)
    by_rule = {f.rule.id: f.measurement for f in found}
    assert by_rule["top"].value == "1450 mm" and by_rule["top"].limit == "700 to 1000 mm"
    assert by_rule["span"].value == "964 mm" and by_rule["span"].limit == "at most 900 mm"
    assert evaluate(table(tmp_path, span(964)), "piece", spec) == []


def test_dividers_bring_the_shelf_span_within_the_limit(tmp_path: Path) -> None:
    spec = desk()
    spec["modules"][0]["dividers"] = 2
    assert evaluate(table(tmp_path, span(900)), "piece", spec) == []
    (found,) = evaluate(table(tmp_path, span(300)), "piece", spec)
    assert found.measurement.value == "309 mm" and "bay 1" in found.measurement.what


def test_unequal_bays_measure_the_widest_and_name_it(tmp_path: Path) -> None:
    spec = desk()
    spec["modules"][0].update(dividers=1, divider_positions_mm=[400])
    (found,) = evaluate(table(tmp_path, span(500)), "piece", spec)
    assert found.measurement.value == "546 mm" and "bay 2" in found.measurement.what


def test_an_outside_fold_widens_the_shelf_span(tmp_path: Path) -> None:
    spec = desk()
    spec["envelope"] = {"width": 3000, "height": 2000, "depth": 400}
    spec["modules"][0].update(
        width=800, height=800, depth=400, shelves=1, shelf_positions_mm=[518], fronts=[],
        side_folds=[{"side": "left", "from_mm": 100, "along": "height", "angle_deg": 45, "towards": "outside"}],
    )
    (found,) = evaluate(table(tmp_path, span(900)), "piece", spec)
    assert found.measurement.value == "1200 mm"


def test_an_inside_fold_keeps_the_unbent_inner_width_as_the_span(tmp_path: Path) -> None:
    spec = desk()
    spec["modules"][0].update(
        width=800, height=2000, depth=400, shelves=1, fronts=[],
        side_folds=[{"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}],
    )
    (found,) = evaluate(table(tmp_path, span(700)), "piece", spec)
    assert found.measurement.value == "764 mm"


def test_a_board_thinner_than_every_table_entry_is_not_judged(tmp_path: Path) -> None:
    thin = rule("span", "shelf_span_mm_for_thickness", {"table": [{"thickness_mm": 25, "max_span_mm": 100}]},
                applies_to="piece")
    assert evaluate(table(tmp_path, thin), "piece", desk()) == []


# --- in the tools ---------------------------------------------------------------------------


def test_a_piece_warning_reaches_the_confirmation_summary(tmp_path: Path, make_ctx, tool_state) -> None:
    tool_state.design_rules = table(tmp_path, span(900))
    shown = preview({"package_id": "hall-bench", "spec": desk()}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "Design-rule warnings: span: shelf span in module 'cabinet' (18 mm board) is 964 mm" in shown.summary
    assert "limit at most 900 mm (asr-a1-2, 5.1)" in shown.summary


def test_a_piece_refusal_skips_the_pause_and_creates_nothing(tmp_path: Path, make_ctx, tool_state) -> None:
    tool_state.design_rules = table(tmp_path, span(900, "refuse"))
    arguments = {"package_id": "hall-bench", "spec": desk()}
    refused = preview(arguments, make_ctx())
    assert isinstance(refused, str) and refused.startswith("refused by a design rule: span:")
    assert isinstance(run(arguments, replace(make_ctx(), approved=True)), str)
    from app.blender import storage

    assert storage.versions(tool_state.settings.render_root, "hall-bench") == []


def test_a_revision_is_checked_too(tmp_path: Path, make_ctx, tool_state) -> None:
    run({"package_id": "hall-bench", "spec": desk()}, replace(make_ctx(), approved=True))
    from app.blender import storage

    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 1))
    tool_state.design_rules = table(tmp_path, span(900))
    shown = revise_preview({"package_id": "hall-bench", "changes": {"name": "Wall desk"}}, make_ctx())
    assert isinstance(shown, Confirmation) and "Design-rule warnings: span:" in shown.summary


def test_room_fit_names_a_placement_warning_and_refuses_on_a_refuse_rule(
    tmp_path: Path, make_ctx, tool_deps, tool_state
) -> None:
    run({"package_id": "hall-bench", "spec": desk()}, replace(make_ctx(), approved=True))
    from app.blender import storage

    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 1))
    with tool_deps.session() as session:
        house_file.upsert_room(session, "Hall", [[0, 0], [3000, 0], [3000, 2000], [0, 2000]], 2500)
        session.commit()
    arguments = {"room_name": "Hall", "package_id": "hall-bench", "wall": 0, "offset_mm": 1000}

    tool_state.design_rules = table(tmp_path, passage(2000))
    warned = room_fit_run(arguments, make_ctx())
    assert "fits in Hall" in warned
    assert "Design-rule warnings: passage: clear passage in front of the piece is 1700 mm, limit at least 2000 mm" in warned

    tool_state.design_rules = table(tmp_path, passage(2000, "refuse"))
    refused = room_fit_run(arguments, make_ctx())
    assert refused.startswith("refused by a design rule: passage:") and "fits in" not in refused


def test_without_rules_nothing_changes(make_ctx) -> None:
    shown = preview({"package_id": "hall-bench", "spec": desk()}, make_ctx())
    assert isinstance(shown, Confirmation) and "Design-rule" not in shown.summary
    assert partition([]) == ([], [])


# --- bracket rules and adjustable shelves (cabinet-hardware-calculator) -----------------------


def bracket_count(rule_id: str = "bracket-count") -> dict:
    return rule(rule_id, "shelf_bracket_count_for_length",
                {"table": [{"max_length_mm": 1200, "min_brackets": 2}]}, applies_to="piece")


def test_two_rules_on_one_bracket_check_fail_naming_both(tmp_path: Path) -> None:
    with pytest.raises(DesignRulesError, match="'bracket-count' and 'other-count'"):
        table(tmp_path, bracket_count(), bracket_count("other-count"))


def test_the_span_check_counts_adjustable_shelves_too(tmp_path: Path) -> None:
    spec = desk()
    spec["modules"][0]["shelves"] = 0
    spec["modules"][0]["adjustable_shelves"] = 2
    (finding,) = evaluate(table(tmp_path, span(900)), "piece", spec)
    assert finding.measurement.value == "964 mm" and finding.rule.id == "span"
    spec["modules"][0]["adjustable_shelves"] = 0
    assert evaluate(table(tmp_path, span(900)), "piece", spec) == []


# --- count checks (guideline-hardware-counts) ---------------------------------------------------


def pin_count(rule_id: str = "pin-count", **params: object) -> dict:
    return rule(rule_id, "shelf_pin_count_for_width",
                {"table": [{"max_width_mm": 914, "pins": 4}], "beyond": 5} | params, applies_to="piece")


def hinge_count(rule_id: str = "hinge-count", **params: object) -> dict:
    return rule(rule_id, "hinge_count_for_height", {
        "table": [{"max_height_mm": 1016, "hinges": 2}, {"max_height_mm": 1524, "hinges": 3}], "beyond": 4,
    } | params, applies_to="piece")


def test_a_count_table_parses(tmp_path: Path) -> None:
    pins, hinges = table(tmp_path, pin_count(), hinge_count())
    assert [(row.max_width_mm, row.pins) for row in pins.params.table] == [(914, 4)] and pins.params.beyond == 5
    assert [(row.max_height_mm, row.hinges) for row in hinges.params.table] == [(1016, 2), (1524, 3)]


@pytest.mark.parametrize("hinges", ["4-5", 4.5, 0, 65])
def test_a_count_that_is_not_one_whole_number_is_refused(tmp_path: Path, hinges: object) -> None:
    bad = hinge_count(table=[{"max_height_mm": 1016, "hinges": hinges}])
    with pytest.raises(DesignRulesError, match="rule 'hinge-count': parameters"):
        table(tmp_path, bad)


@pytest.mark.parametrize("rows", [
    [{"max_width_mm": 914, "pins": 4}, {"max_width_mm": 600, "pins": 3}],
    [{"max_width_mm": 914, "pins": 4}, {"max_width_mm": 914, "pins": 5}],
])
def test_a_count_table_that_does_not_rise_is_refused(tmp_path: Path, rows: list) -> None:
    with pytest.raises(DesignRulesError, match="rule 'pin-count': parameters"):
        table(tmp_path, pin_count(table=rows))


def test_a_count_rule_raises_no_finding(tmp_path: Path) -> None:
    spec = desk()
    spec["modules"][0]["adjustable_shelves"] = 3
    spec["modules"][0]["fronts"] = [{"type": "door", "count": 2, "opening": "hinge", "height": 1200}]
    assert evaluate(table(tmp_path, pin_count(), hinge_count()), "piece", spec) == []


@pytest.mark.parametrize("make", [pin_count, hinge_count])
def test_two_rules_on_one_count_check_fail_naming_both(tmp_path: Path, make) -> None:
    with pytest.raises(DesignRulesError, match="'first' and 'second'"):
        table(tmp_path, make("first"), make("second"))


def test_the_shipped_count_rules_cite_the_owner_notes() -> None:
    shipped = {r.id: r for r in load_rules()}
    pins, hinges = shipped["shelf-pin-count"], shipped["hinge-count"]
    assert pins.source.publication == "owner:7cf8c9ef-e98f-4d3d-af6c-f0384a17ffdd" and "36 inches" in pins.source.quote
    assert [(row.max_width_mm, row.pins) for row in pins.params.table] == [(914, 4)] and pins.params.beyond == 5
    assert hinges.source.publication == "owner:a8147011-0f73-4e5e-a5f2-e3a9f8fd9852" and "101.6 cm" in hinges.source.quote
    assert [(row.max_height_mm, row.hinges) for row in hinges.params.table] == [(1016, 2), (1524, 3), (2032, 4)]
    assert hinges.params.beyond == 5


# --- rail-support count (hardware-catalog) --------------------------------------------------------


def rail_supports(rule_id: str = "rail-supports") -> dict:
    return rule(rule_id, "rail_support_count_for_length",
                {"table": [{"max_length_mm": 1000, "supports": 2}], "beyond": 3}, applies_to="piece")


def test_a_rail_support_table_parses_and_judges_nothing(tmp_path: Path) -> None:
    (supports,) = table(tmp_path, rail_supports())
    assert [(row.max_length_mm, row.supports) for row in supports.params.table] == [(1000, 2)]
    assert supports.params.beyond == 3


def test_a_second_rail_support_rule_is_refused(tmp_path: Path) -> None:
    """Scenario: Second rail-support rule refused."""
    with pytest.raises(DesignRulesError, match="'rail-supports' and 'rail-supports-2' both name"):
        table(tmp_path, rail_supports(), rail_supports("rail-supports-2"))


def test_no_rail_support_rule_ships() -> None:
    assert not [r for r in load_rules() if r.check == "rail_support_count_for_length"]
