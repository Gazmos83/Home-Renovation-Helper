"""room-composition: the Designer's `compose_room` — check, preview, confirm, build."""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import text

from app.agent import house_file
from app.agent.tools.base import Confirmation
from app.blender import storage
from plugins.compose_room.tool import preview, run
from tests.conftest import wait_for_status

WOHNEN = [[0, 0], [5000, 0], [5000, 4000], [0, 4000]]
SOFA = {"id": "sofa", "type": "stand-in", "name": "Sofa", "width_mm": 2200, "depth_mm": 950, "height_mm": 800,
        "colour": "#7a6a58", "placement": {"x_mm": 2500, "y_mm": 2600, "rotation_deg": 180}}


@pytest.fixture
def room(tool_deps):
    with tool_deps.session() as session:
        house_file.upsert_room(
            session, "Wohnen", WOHNEN, 2600,
            openings=[{"wall": 0, "type": "door", "offset_mm": 3800, "width_mm": 900, "height_mm": 2100}],
        )
        session.commit()


@pytest.fixture
def approved_desk(make_ctx, tool_deps, tool_state, room):
    from app.agent.tools.create_piece import run as create_run
    from tests.api_helpers import desk

    create_run({"package_id": "desk", "spec": desk()}, replace(make_ctx(), approved=True))
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "desk", 1))
    with tool_deps.session() as session:
        house_file.approve_version(session, "desk", 1)
        session.commit()


DESK = {"id": "desk", "type": "piece", "package_id": "desk", "version": 1, "placement": {"wall": 1, "offset_mm": 500}}


def test_a_confirmed_composition_creates_version_one_and_builds_it(make_ctx, tool_deps, tool_state, approved_desk) -> None:
    arguments = {"room": "Wohnen", "items": [DESK, SOFA]}
    shown = preview(arguments, make_ctx())
    assert isinstance(shown, Confirmation) and shown.subject == "compose_room"
    assert shown.summary.startswith("Room Wohnen: 2 item(s)")
    assert "- desk (piece, desk v1): 1000 × 300 × 700 mm, against wall 1 at 500 mm" in shown.summary
    assert "- sofa (stand-in, Sofa): 2200 × 950 × 800 mm, at (2500, 2600) mm turned 180°" in shown.summary

    output = run(arguments, replace(make_ctx(), approved=True))
    assert "Created Wohnen version 1; its build has started" in output.text
    folder = storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1)
    wait_for_status(folder)
    with tool_deps.session() as session:
        listed = house_file.compositions(session, tool_state.settings.render_root)
    assert [(c["name"], c["latest_version"], c["status"]) for c in listed] == [("Wohnen", 1, "succeeded")]


def test_a_second_version_lists_what_changed(make_ctx, tool_state, approved_desk) -> None:
    run({"room": "Wohnen", "items": [DESK, SOFA]}, replace(make_ctx(), approved=True))
    wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1))
    moved = {**SOFA, "placement": {"x_mm": 2500, "y_mm": 2500, "rotation_deg": 180}}
    shown = preview({"room": "Wohnen", "items": [moved]}, make_ctx())
    assert "Compared with version 1: removed: desk; moved: sofa" in shown.summary
    assert shown.proposal["revised_from"] == 1


def test_previewing_creates_nothing(make_ctx, tool_state, room) -> None:
    preview({"room": "Wohnen", "items": [SOFA]}, make_ctx())
    assert storage.list_compositions(tool_state.settings.render_root) == []


def test_an_unapproved_piece_is_refused_without_a_pause(make_ctx, tool_deps, approved_desk) -> None:
    with tool_deps.session() as session:
        house_file.unapprove_version(session, "desk", 1)
        session.commit()
    refused = preview({"room": "Wohnen", "items": [DESK]}, make_ctx())
    assert refused == (
        "desk version 1 is not approved (no version of it is approved); the owner approves a built "
        "version on the Pieces page or the project panel first"
    )


def test_a_model_still_being_checked_is_refused(make_ctx, tool_deps, room) -> None:
    import io

    from app.assets.models import Limits, add_model
    from tests import model_fixtures as fx

    with tool_deps.session() as session:
        session.execute(text("DELETE FROM model_assets"))
        model = add_model(session, tool_deps.settings.upload_root, io.BytesIO(fx.glb()), name="Armchair",
                          width_mm=800, depth_mm=700, height_mm=900, original_name="a.glb",
                          limits=Limits(2_000_000, 20, 1_000_000))
        model_id = str(model.id)
    item = {"id": "armchair", "type": "model", "model_id": model_id, "placement": {"x_mm": 1000, "y_mm": 1000, "rotation_deg": 0}}
    refused = preview({"room": "Wohnen", "items": [item]}, make_ctx())
    assert refused == "item armchair: the model 'Armchair' is not ready yet; it is still being checked"


def test_an_invalid_placement_is_returned_without_a_pause(make_ctx, room) -> None:
    blocking = {**SOFA, "placement": {"wall": 0, "offset_mm": 2500}}
    refused = preview({"room": "Wohnen", "items": [blocking]}, make_ctx())
    assert isinstance(refused, str) and "item sofa blocks the door on wall 0 of Wohnen" in refused


def test_an_unknown_room_lists_the_known_ones(make_ctx, room) -> None:
    refused = preview({"room": "Attic", "items": [SOFA]}, make_ctx())
    assert "there is no room 'Attic'" in refused and "the rooms are: Wohnen" in refused


def test_an_unknown_item_field_is_refused_and_recorded(make_ctx, tool_deps, room) -> None:
    refused = preview({"room": "Wohnen", "items": [{**SOFA, "lamp_watts": 60}]}, make_ctx())
    assert "lamp_watts" in refused and "recorded for the workshop" in refused
    with tool_deps.session() as session:
        assert [r.field for r in house_file.open_extension_requests(session)] == ["items[0].lamp_watts"]


def test_it_does_not_run_without_the_owners_yes(make_ctx, tool_state, room) -> None:
    assert "confirmation" in run({"room": "Wohnen", "items": [SOFA]}, make_ctx())
    assert storage.list_compositions(tool_state.settings.render_root) == []
