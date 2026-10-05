"""design-agents: the Designer's `revise_package` — confirm, decline, refuse."""

from __future__ import annotations

from dataclasses import replace

from app.agent import house_file
from app.agent.tools.base import Confirmation
from app.agent.tools.create_piece import run as create_run
from app.agent.tools.revise_package import preview, run
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
