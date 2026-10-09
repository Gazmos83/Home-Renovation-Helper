"""design-agents: `cut_list` derives parts and hardware with no process."""

from __future__ import annotations

from dataclasses import replace

from app.agent.tools.create_piece import run as create_run
from app.agent.tools.cut_list import run
from app.blender import storage
from app.blender.custom_build import derive as custom_derive
from tests.api_helpers import desk
from tests.conftest import wait_for_status


def test_it_lists_the_fold_down_desks_rows_and_starts_no_process(make_ctx, tool_state) -> None:
    root = tool_state.settings.render_root
    create_run({"package_id": "desk", "spec": desk()}, replace(make_ctx(), approved=True))
    wait_for_status(storage.version_dir(root, "desk", 1))
    launched_before = len(tool_state.launched)

    text = run({"package_id": "desk"}, make_ctx())

    parts, hardware, _ = custom_derive.derive(desk())
    assert text.startswith("Cut list for desk version 1:")
    for part in parts:
        assert f"- {part['id']}: {part['qty']} × {part['l']} × {part['w']} × {part['t']} mm" in text
    assert f"Parts: {len(parts)} rows, {sum(p['qty'] for p in parts)} pieces in all" in text
    assert f"Hardware: {len(hardware)} lines" in text
    assert len(tool_state.launched) == launched_before


def test_a_missing_package_or_version_is_a_stated_refusal(make_ctx) -> None:
    assert "no package" in run({"package_id": "ghost"}, make_ctx())


def test_a_version_that_does_not_exist_is_refused(make_ctx, tool_state) -> None:
    from app.packages import service

    service.create_version(tool_state.settings.render_root, "desk", desk(), lambda version: None)
    assert "has no version 7" in run({"package_id": "desk", "version": 7}, make_ctx())


# --- drilling (cabinet-hardware-calculator) ---------------------------------------------------


def _version(tool_state, package_id: str, spec: dict, inputs: dict | None) -> None:
    from app.packages import service

    service.create_version(tool_state.settings.render_root, package_id, spec, lambda version: None, inputs=inputs)


def test_an_incomplete_drilling_list_names_the_missing_value(make_ctx, tool_state) -> None:
    from tests.drill_helpers import build, inputs, module, sheet

    spec = build(modules=[module(fronts=[{"type": "door", "count": 1, "opening": "hinge"}])])
    hinge = sheet("hinge", {"end_distance_mm": {"value": 100}, "cup_diameter_mm": {"value": 35}, "cup_depth_mm": {"value": 13}})
    _version(tool_state, "cab", spec, inputs({"hinge-concealed-110": hinge}))
    text = run({"package_id": "cab"}, make_ctx())
    assert "Drilling (INCOMPLETE):" in text
    assert "Warning: drilling positions missing: cup edge distance" in text
    assert "Drilling work: 2 hinge cup borings" in text


def test_ranged_bracket_ends_are_reported_as_the_cited_range(make_ctx, tool_state) -> None:
    from tests.drill_helpers import build, inputs, rules, wall_shelf

    spec = build(wall_shelves=[wall_shelf(length=1500)])
    _version(tool_state, "shelf", spec, inputs(rule_set=rules(end={"min": 100, "max": 200})))
    text = run({"package_id": "shelf"}, make_ctx())
    assert "Drilling (complete):" in text
    assert "100–200 mm from each end" in text and "bracket 2 evenly spaced between them" in text
    assert "Warning" not in text


def test_a_hardware_line_with_no_quantity_is_listed_and_left_out_of_the_total(make_ctx, tool_state) -> None:
    from tests.drill_helpers import build, inputs, module

    _version(tool_state, "pins", build(modules=[module(adjustable_shelves=2)]), inputs())
    text = run({"package_id": "pins"}, make_ctx())
    assert "(shelf-pin): no quantity" in text and "Hardware with no quantity" in text


def test_an_old_version_says_drilling_was_not_calculated(make_ctx, tool_state) -> None:
    _version(tool_state, "old", desk(), None)
    text = run({"package_id": "old"}, make_ctx())
    assert "Drilling: not calculated for this version." in text
    assert "Warning" not in text
