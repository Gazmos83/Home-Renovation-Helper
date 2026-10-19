"""design-agents: the Designer's `revise_package` — confirm, decline, refuse."""

from __future__ import annotations

import json
from dataclasses import replace

from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.tools.base import Confirmation
from app.agent.tools.create_piece import run as create_run
from app.agent.tools.revise_package import preview, rebuild_preview, rebuild_run, run
from app.blender import storage
from tests.api_helpers import desk
from tests.conftest import wait_for_status

SHELVES = {"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"shelves": 3}}}}


def make_piece(make_ctx, tool_state) -> int:
    document = desk()
    shelves = document["modules"][0]["shelves"]
    create_run({"package_id": "hall-bench", "spec": document}, replace(make_ctx(), approved=True))
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 1))
    return shelves


def test_a_revision_is_previewed_as_change_lines(make_ctx, tool_state) -> None:
    before = make_piece(make_ctx, tool_state)
    shown = preview(SHELVES, make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.subject == "revise"
    assert f"cabinet: shelves {before} → 3" in shown.summary
    assert shown.proposal["revised_from"] == 1


def test_yes_creates_the_next_version_revised_from_the_latest(make_ctx, tool_deps, tool_state) -> None:
    before = make_piece(make_ctx, tool_state)
    root = tool_state.settings.render_root
    v1_input = (storage.version_dir(root, "hall-bench", 1) / "input.json").read_text(encoding="utf-8")

    output = run(SHELVES, replace(make_ctx(), approved=True))
    assert "version 2" in output.text
    wait_for_status(storage.version_dir(root, "hall-bench", 2))

    # Version 1 is untouched.
    assert (storage.version_dir(root, "hall-bench", 1) / "input.json").read_text(encoding="utf-8") == v1_input
    with tool_deps.session() as session:
        piece = {p["package_id"]: p for p in house_file.pieces(session, root)}["hall-bench"]
    second = piece["versions"][1]
    assert second["version"] == 2 and second["revised_from"] == 1
    assert second["changes"] == [f"cabinet: shelves {before} → 3"]


def test_a_revision_records_the_slot_and_model_that_made_it(make_ctx, tool_deps, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    ctx = replace(make_ctx(), approved=True, slot="designer", model="~deepseek/deepseek-v4-flash-latest")
    run(SHELVES, ctx)
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 2))
    with tool_deps.session() as session:
        first = house_file.version_row(session, "hall-bench", 1)
        second = house_file.version_row(session, "hall-bench", 2)
        assert (first.slot, first.model) == (None, None)
        assert (second.slot, second.model) == ("designer", "~deepseek/deepseek-v4-flash-latest")


def test_a_revision_that_changes_nothing_is_refused_and_creates_nothing(make_ctx, tool_state) -> None:
    shelves = make_piece(make_ctx, tool_state)
    same = {"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"shelves": shelves}}}}
    shown = preview(same, make_ctx())
    assert isinstance(shown, str)
    assert shown.startswith("nothing would change: every requested value equals version 1")
    assert run(same, replace(make_ctx(), approved=True)) == shown
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_declining_is_the_graphs_job_so_previewing_alone_creates_nothing(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    preview(SHELVES, make_ctx())
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_without_approval_nothing_is_created(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    assert "confirmation" in run(SHELVES, make_ctx())
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_an_unknown_module_is_refused_naming_it_and_listing_the_known_ones(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    refused = preview(
        {"package_id": "hall-bench", "changes": {"modules": {"drawers": {"shelves": 1}}}}, make_ctx()
    )
    assert isinstance(refused, str)
    assert "'drawers'" in refused and "cabinet" in refused


def test_an_unknown_field_is_recorded_and_refused(make_ctx, tool_deps, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    ctx = make_ctx(last_message="make the front edge bevelled")
    refused = preview(
        {"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"bevel_mm": 3}}}}, ctx
    )
    assert isinstance(refused, str) and "bevel_mm" in refused
    with tool_deps.session() as session:
        found = house_file.open_extension_requests(session)
    assert [(r.field, r.package_id) for r in found] == [("modules.cabinet.bevel_mm", "hall-bench")]
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_a_piece_that_does_not_exist_is_refused(make_ctx) -> None:
    refused = preview(SHELVES, make_ctx())
    assert isinstance(refused, str) and "no piece" in refused


def test_a_package_made_through_the_routes_can_be_revised(make_ctx, tool_deps, tool_state) -> None:
    # No pieces row: made directly.
    from app.packages import service

    root = tool_state.settings.render_root
    service.create_version(root, "direct", desk(), lambda version: None)
    out = run(
        {"package_id": "direct", "changes": {"modules": {"cabinet": {"shelves": 4}}}},
        replace(make_ctx(), approved=True),
    )
    assert "version 2" in out.text
    with tool_deps.session() as session:
        piece = {p["package_id"]: p for p in house_file.pieces(session, root)}["direct"]
    assert piece["versions"][0]["revised_from"] == 1


# --- rebuild_piece (piece-versions-and-chat-delete) ------------------------------------------------


def test_a_rebuild_is_previewed_naming_the_next_version(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    shown = rebuild_preview({"package_id": "hall-bench"}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.subject == "rebuild"
    assert shown.summary.startswith("Rebuild hall-bench as version 2, unchanged from version 1")
    assert shown.proposal == {"package_id": "hall-bench", "revised_from": 1, "version": 2}
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_yes_rebuilds_the_same_design_as_the_next_version_and_binds_the_thread(
    make_ctx, tool_deps, tool_state
) -> None:
    make_piece(make_ctx, tool_state)
    root = tool_state.settings.render_root
    v1 = storage.version_dir(root, "hall-bench", 1)
    v1_input = (v1 / "input.json").read_text(encoding="utf-8")
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "rebuild")
        session.commit()
        thread_id = thread.id

    output = rebuild_run({"package_id": "hall-bench"}, replace(make_ctx(thread_id=thread_id), approved=True))
    assert output.text == "Created hall-bench version 2 (rebuilt unchanged from version 1). The build has started."
    v2 = storage.version_dir(root, "hall-bench", 2)
    wait_for_status(v2)

    assert (v1 / "input.json").read_text(encoding="utf-8") == v1_input
    assert json.loads((v2 / "input.json").read_text(encoding="utf-8")) == json.loads(v1_input)
    with tool_deps.session() as session:
        piece = {p["package_id"]: p for p in house_file.pieces(session, root)}["hall-bench"]
        bound = house_file.get_thread(session, thread_id).package_id
    second = piece["versions"][1]
    assert (second["version"], second["revised_from"], second["changes"]) == (
        2, 1, ["rebuilt unchanged from version 1"],
    )
    assert bound == "hall-bench"


def test_a_rebuild_without_approval_or_declined_creates_nothing(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    assert "confirmation" in rebuild_run({"package_id": "hall-bench"}, make_ctx())
    rebuild_preview({"package_id": "hall-bench"}, make_ctx())
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_a_rebuild_of_an_unknown_piece_is_refused(make_ctx) -> None:
    refused = rebuild_preview({"package_id": "no-such-piece"}, make_ctx())
    assert isinstance(refused, str) and "no piece 'no-such-piece'" in refused


def test_the_preview_warns_about_owner_brackets_and_still_lets_the_owner_confirm(make_ctx, tool_state) -> None:
    from app.guidelines.rules import load_rules

    make_piece(make_ctx, tool_state)
    tool_state.design_rules = load_rules()
    shelf = {
        "id": "wall-shelf-1", "name": "Wall shelf", "x": 0, "z": 1500, "length": 1500, "depth": 250,
        "material": "carcass", "bracket": "bracket-white", "bracket_positions_mm": [150, 1350],
    }
    shown = preview({"package_id": "hall-bench", "changes": {"add_wall_shelves": [shelf]}}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "shelf-bracket-count" in shown.summary and "wall-shelf-1" in shown.summary
    assert "2 brackets" in shown.summary and "at least 3" in shown.summary
    assert "topnotch-shelf-brackets" in shown.summary
    assert "shelf-bracket-spacing" not in shown.summary  # 150 mm from each end is inside 100 to 200 mm

    output = run({"package_id": "hall-bench", "changes": {"add_wall_shelves": [shelf]}}, replace(make_ctx(), approved=True))
    assert "version 2" in output.text
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 2))


# --- the owner's measurements, checked by code (app-check-2026-10-09) ---------------------


def _said(make_ctx, *texts: str):
    from langchain_core.messages import HumanMessage

    return make_ctx(history=tuple(HumanMessage(text) for text in texts))


def _wider(width: int, *requested: dict) -> dict:
    return {
        "package_id": "hall-bench",
        "changes": {"modules": {"cabinet": {"width": width}}},
        "requested": list(requested),
    }


def test_an_absolute_width_the_owner_gave_is_confirmed(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    ctx = _said(make_ctx, "make the cabinet 90 cm wide")
    shown = preview(_wider(900, {"quote": "90 cm wide", "target": "cabinet", "field": "width", "value_mm": 900}), ctx)
    assert isinstance(shown, Confirmation)
    assert "cabinet: width 1000 → 900" in shown.summary


def test_an_invented_value_is_refused_with_no_confirmation(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    ctx = _said(make_ctx, "make the cabinet 90 cm wide")
    refused = preview(_wider(850, {"quote": "90 cm wide", "target": "cabinet", "field": "width", "value_mm": 900}), ctx)
    assert isinstance(refused, str)
    assert "'90 cm wide'" in refused and "900 mm expected" in refused and "set 850 mm" in refused
    assert run(_wider(850, {"quote": "90 cm wide", "target": "cabinet", "field": "width", "value_mm": 900}),
               replace(ctx, approved=True)) == refused
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_a_relative_width_is_resolved_against_the_latest_version(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    ctx = _said(make_ctx, "5 cm wider please")
    shown = preview(_wider(1050, {"quote": "5 cm wider", "target": "cabinet", "field": "width", "value_mm": 1050}), ctx)
    assert isinstance(shown, Confirmation)
    assert "cabinet: width 1000 → 1050" in shown.summary


def test_a_length_left_out_is_refused_naming_it(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    ctx = _said(make_ctx, "90 cm wide and 35 cm deep")
    refused = preview(_wider(900, {"quote": "90 cm wide", "target": "cabinet", "field": "width", "value_mm": 900}), ctx)
    assert isinstance(refused, str) and "'35 cm' is not covered" in refused


def test_no_requested_list_is_refused_when_the_owner_gave_a_length(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    refused = preview(_wider(900), _said(make_ctx, "make it 90 cm wide"))
    assert isinstance(refused, str) and "'90 cm' is not covered" in refused


def test_a_quote_the_owner_did_not_write_is_refused(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    ctx = _said(make_ctx, "make it a bit wider")
    refused = preview(_wider(900, {"quote": "90 cm", "target": "cabinet", "field": "width", "value_mm": 900}), ctx)
    assert isinstance(refused, str) and "'90 cm' is not in the owner's messages" in refused


# --- the version limit (version-cleanup-and-inspection) ---------------------------------------


def _hold(tool_state, count: int) -> None:
    """Copy the built version 1 into versions 2..count, so the piece holds `count` versions."""
    import shutil

    root = tool_state.settings.render_root
    for number in range(2, count + 1):
        shutil.copytree(storage.version_dir(root, "hall-bench", 1), storage.version_dir(root, "hall-bench", number))


def test_a_revision_at_fifteen_versions_is_refused_before_any_confirmation(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    _hold(tool_state, 15)
    refused = preview(SHELVES, make_ctx())
    assert isinstance(refused, str)
    assert "hall-bench has 15 versions" in refused
    assert "Pieces page" in refused and "Piece panel" in refused
    assert run(SHELVES, replace(make_ctx(), approved=True)) == refused
    rebuilt = rebuild_preview({"package_id": "hall-bench"}, make_ctx())
    assert rebuilt == refused
    assert len(storage.versions(tool_state.settings.render_root, "hall-bench")) == 15


def test_a_revision_making_the_thirteenth_version_carries_the_heads_up(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    _hold(tool_state, 12)
    shown = preview(SHELVES, make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.summary.endswith("This will be version 13 of 15 the piece can hold.")
    rebuilt = rebuild_preview({"package_id": "hall-bench"}, make_ctx())
    assert "This will be version 13 of 15 the piece can hold." in rebuilt.summary


def test_an_early_revision_has_no_limit_line(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    _hold(tool_state, 4)
    shown = preview(SHELVES, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "of 15" not in shown.summary


def test_a_rebuild_after_the_highest_version_was_deleted_names_a_new_number(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    _hold(tool_state, 3)
    storage.remove_version(tool_state.settings.render_root, "hall-bench", 3)
    shown = rebuild_preview({"package_id": "hall-bench"}, make_ctx())
    assert shown.summary.startswith("Rebuild hall-bench as version 4, unchanged from version 2")


# partial-and-folded-dividers: the two questions; revision-confirm-highlight-cuts: change lines only.
TOP_SPAN = [{"from_board": 2, "to_board": "top"}]


def test_a_new_divider_without_a_position_is_asked_not_previewed(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    change = {"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"dividers": 1, "divider_spans": TOP_SPAN}}}}
    answer = preview(change, make_ctx())
    assert isinstance(answer, str) and answer.startswith("No version proposed: a new divider needs its position")
    assert "[473] mm from the left side's inner face" in answer and "No shelf-span limit is configured" in answer
    assert run(change, replace(make_ctx(), approved=True)) == answer
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_a_positioned_divider_is_previewed_with_change_lines_only(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    change = {
        "package_id": "hall-bench",
        "changes": {"modules": {"cabinet": {"dividers": 1, "divider_positions_mm": [473], "divider_spans": TOP_SPAN}}},
    }
    shown = preview(change, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "Cut list:" not in shown.summary
    assert "Hardware:" not in shown.summary
    assert shown.proposal["changes"] == [
        "cabinet: dividers None → 1",
        "cabinet: divider_positions_mm not set → [473]",
        "cabinet: divider_spans full height → divider 1 from shelf 2 to the top",
    ]
    for line in shown.proposal["changes"]:
        assert line in shown.summary


def test_a_divider_on_an_adjustable_shelf_asks_to_fix_it(make_ctx, tool_state) -> None:
    make_piece(make_ctx, tool_state)
    change = {
        "package_id": "hall-bench",
        "changes": {
            "modules": {
                "cabinet": {
                    "shelves": 0, "adjustable_shelves": 2, "dividers": 1,
                    "divider_positions_mm": [473], "divider_spans": TOP_SPAN,
                }
            }
        },
    }
    answer = preview(change, make_ctx())
    assert isinstance(answer, str) and "Only a fixed shelf can hold a divider" in answer
    assert "ask whether to fix shelf 2" in answer and "Confirmat screw 7×50 mm" in answer


def test_create_piece_asks_for_a_new_dividers_position(make_ctx) -> None:
    from app.agent.tools.create_piece import preview as create_preview

    document = desk()
    document["modules"][0] |= {"dividers": 1}
    answer = create_preview({"package_id": "divided-desk", "spec": document}, make_ctx())
    assert isinstance(answer, str) and "[473] mm from the left side's inner face" in answer


# --- auto-fit-protruding-shelves ---------------------------------------------------------------

DEEPER = {
    "package_id": "hall-bench",
    "changes": {"modules": {"cabinet": {"shelf_depths_mm": [None, 400], "shelf_depth_align": "back"}}},
    "requested": [
        {"quote": "second shelf 40 cm deep", "target": "cabinet", "field": "shelf_depths_mm", "value_mm": 400}
    ],
}


def make_boxed_piece(make_ctx, tool_state, thread) -> None:
    document = desk()
    document["envelope"] = {"width": 1000, "height": 1450, "depth": 300}
    create_run({"package_id": "hall-bench", "spec": document}, replace(make_ctx(), approved=True))
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 1))
    with Session(tool_state.engine) as session:
        house_file.add_build(session, thread, "hall-bench")
        house_file.write_owner_summary(session, thread, "- **Doors:** flap", "hall-bench")
        session.commit()


def _bound_thread(tool_state):
    with Session(tool_state.engine) as session:
        thread = house_file.create_thread(session, "test", package_id="hall-bench")
        session.commit()
        return thread.id


def _note(tool_state, thread) -> str | None:
    with Session(tool_state.engine) as session:
        return house_file.read_summary(session, thread, "hall-bench")[0]


def test_the_fit_is_shown_in_the_confirmation_and_the_row_follows_the_yes(make_ctx, tool_state) -> None:
    thread = _bound_thread(tool_state)
    make_boxed_piece(make_ctx, tool_state, thread)
    ctx = replace(make_ctx(thread_id=thread, package_id="hall-bench"), history=(HumanMessage("second shelf 40 cm deep"),))
    shown = preview(DEEPER, ctx)
    assert isinstance(shown, Confirmation)
    assert "cabinet: y 0 → 112 mm" in shown.summary and "envelope depth 300 → 412 mm" in shown.summary
    assert "Protruding shelf fit" not in (_note(tool_state, thread) or "")  # nothing before the yes

    run(DEEPER, replace(ctx, approved=True))
    note = _note(tool_state, thread) or ""
    assert note.startswith("- **Doors:** flap\n- **Protruding shelf fit:**") and "envelope depth 300 → 412 mm" in note


def test_a_declined_or_unapproved_revision_writes_no_row(make_ctx, tool_state) -> None:
    thread = _bound_thread(tool_state)
    make_boxed_piece(make_ctx, tool_state, thread)
    ctx = replace(make_ctx(thread_id=thread, package_id="hall-bench"), history=(HumanMessage("second shelf 40 cm deep"),))
    preview(DEEPER, ctx)
    run(DEEPER, ctx)  # not approved
    assert _note(tool_state, thread) == "- **Doors:** flap"


def test_a_revision_without_a_fit_writes_no_row(make_ctx, tool_state) -> None:
    thread = _bound_thread(tool_state)
    make_boxed_piece(make_ctx, tool_state, thread)
    run(SHELVES, replace(make_ctx(thread_id=thread, package_id="hall-bench"), approved=True))
    assert _note(tool_state, thread) == "- **Doors:** flap"


# --- auto-fit-protruding-shelves: a side fold changes only on the owner's request ----------------

BEND = {"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}


def make_folded_piece(make_ctx, tool_state) -> None:
    from tests.test_shelf_depths import _build

    document = _build(shelves=3, side_folds=[BEND])
    document["envelope"] = {"width": 800, "height": 1600, "depth": 400}
    create_run({"package_id": "hall-bench", "spec": document}, replace(make_ctx(), approved=True))
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 1))


def test_a_fold_cleared_without_a_request_is_refused_and_creates_nothing(make_ctx, tool_state) -> None:
    make_folded_piece(make_ctx, tool_state)
    ctx = make_ctx(history=(HumanMessage("make the top shelf 550 mm deep"),))
    arguments = {
        "package_id": "hall-bench",
        "changes": {
            "modules": {
                "cabinet": {"shelf_depths_mm": [None, None, 550], "shelf_depth_align": "back", "side_folds": []}
            }
        },
        "requested": [
            {"quote": "550 mm deep", "target": "cabinet", "field": "shelf_depths_mm", "value_mm": 550}
        ],
    }
    refused = preview(arguments, ctx)
    assert isinstance(refused, str)
    assert "cabinet" in refused and "side_folds" in refused and "ask the owner" in refused
    assert run(arguments, replace(ctx, approved=True)) == refused
    assert storage.versions(tool_state.settings.render_root, "hall-bench") == [1]


def test_a_fold_changed_at_the_owners_request_is_confirmed(make_ctx, tool_state) -> None:
    make_folded_piece(make_ctx, tool_state)
    ctx = make_ctx(history=(HumanMessage("make the left bend 30°"),))
    arguments = {
        "package_id": "hall-bench",
        "changes": {"modules": {"cabinet": {"side_folds": [{**BEND, "angle_deg": 30}]}}},
        "requested": [{"quote": "make the left bend 30°", "target": "cabinet", "field": "side_folds", "value_mm": 0}],
    }
    shown = preview(arguments, ctx)
    assert isinstance(shown, Confirmation), shown
    assert "side_folds" in shown.summary and "30°" in shown.summary


def test_a_revision_that_leaves_the_fold_alone_needs_no_fold_entry(make_ctx, tool_state) -> None:
    make_folded_piece(make_ctx, tool_state)
    ctx = make_ctx(history=(HumanMessage("make the top shelf 550 mm deep"),))
    arguments = {
        "package_id": "hall-bench",
        "changes": {"modules": {"cabinet": {"shelf_depths_mm": [None, None, 550], "shelf_depth_align": "back"}}},
        "requested": [
            {"quote": "550 mm deep", "target": "cabinet", "field": "shelf_depths_mm", "value_mm": 550}
        ],
    }
    shown = preview(arguments, ctx)
    assert isinstance(shown, Confirmation), shown
    assert "side_folds" not in shown.summary
    assert "cabinet: y 0 → 162 mm" in shown.summary and "envelope depth 400 → 562 mm" in shown.summary


# --- door slats (door-slats) -------------------------------------------------------------


def test_a_handle_over_slats_is_warned_about_before_confirming(make_ctx, tool_state) -> None:
    document = desk()
    document["materials"]["slats"] = {"material": "12 mm MDF", "thickness_mm": 12}
    door = {"type": "door", "count": 2, "opening": "hinge", "slats": {"count": 8, "width": 30, "material": "slats", "leaves": [2]}}
    document["modules"][0]["fronts"] = [door]
    create_run({"package_id": "hall-bench", "spec": document}, replace(make_ctx(), approved=True))
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 1))

    knobs = door | {"handle": {"kind": "knob"}}
    shown = preview({"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"fronts": [knobs]}}}}, make_ctx())

    assert isinstance(shown, Confirmation)
    assert "8 vertical slats 30 mm on door 2" in shown.summary
    assert "\nSlat-handle warnings: the handle on door 2 of cabinet-door-1 is mounted over the slats" in shown.summary
    assert "door 1 of" not in shown.summary


# --- door leaf materials (door-leaf-materials) ------------------------------------------------------


def test_the_confirmation_says_when_the_front_layout_changes(make_ctx, tool_state) -> None:
    document = desk()
    document["materials"]["black_paint"] = {"material": "18 mm black painted MDF", "thickness_mm": 18}
    pair = {"type": "door", "count": 2, "opening": "hinge"}
    document["modules"][0]["fronts"] = [pair]
    create_run({"package_id": "hall-bench", "spec": document}, replace(make_ctx(), approved=True))
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 1))

    black = pair | {"leaf_materials": {"2": "black_paint"}}
    shown = preview({"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"fronts": [black]}}}}, make_ctx())
    assert isinstance(shown, Confirmation), shown
    assert "2 doors (hinge, door 2 black_paint)" in shown.summary
    assert "front layout changes" not in shown.summary

    single = {"type": "door", "count": 1, "opening": "hinge"}
    shown = preview({"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"fronts": [single, single]}}}}, make_ctx())
    assert isinstance(shown, Confirmation), shown
    assert "cabinet: front layout changes from 1 entry of 2 doors side by side to 2 entries stacked top to bottom" in shown.summary


def test_a_revision_whose_record_fails_leaves_no_folder_and_starts_no_build(make_ctx, tool_state, monkeypatch) -> None:
    make_piece(make_ctx, tool_state)
    root = tool_state.settings.render_root

    def broken(*_args, **_kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(house_file, "record_version", broken)
    started: list[int] = []
    monkeypatch.setattr(type(make_ctx().deps), "start_build", lambda _self, _id, version: started.append(version))
    try:
        run(SHELVES, replace(make_ctx(), approved=True))
    except RuntimeError:
        pass
    assert not storage.version_dir(root, "hall-bench", 2).exists()
    assert storage.versions(root, "hall-bench") == [1]
    assert started == []
