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
    assert "- desk (piece, desk v1): 1000 × 300 × 700 mm, against wall 2, 2500 mm from the left end" in shown.summary
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


def test_a_floor_layer_rug_under_the_sofa_is_previewed_for_confirmation(make_ctx, room) -> None:
    rug = {"id": "rug", "type": "stand-in", "name": "Rug", "width_mm": 2300, "depth_mm": 1600, "height_mm": 10,
           "colour": "#c8b8a0", "layer": "floor", "placement": {"x_mm": 2500, "y_mm": 2300, "rotation_deg": 0}}
    assert isinstance(preview({"room": "Wohnen", "items": [SOFA, rug]}, make_ctx()), Confirmation)
    without_layer = {key: value for key, value in rug.items() if key != "layer"}
    refused = preview({"room": "Wohnen", "items": [SOFA, without_layer]}, make_ctx())
    assert isinstance(refused, str) and "overlap" in refused


def test_the_tool_tells_the_designer_about_the_floor_layer() -> None:
    from plugins.compose_room.tool import ComposeRoomArgs

    assert "layer 'floor'" in ComposeRoomArgs.model_fields["items"].description


def test_a_ceiling_layer_pendant_over_the_table_is_previewed_for_confirmation(make_ctx, room) -> None:
    table = {"id": "table", "type": "stand-in", "name": "Table", "width_mm": 1600, "depth_mm": 900, "height_mm": 750,
             "colour": "#8a6a48", "placement": {"x_mm": 2500, "y_mm": 1200, "rotation_deg": 0}}
    pendant = {"id": "pendant", "type": "stand-in", "name": "Pendant", "width_mm": 500, "depth_mm": 500,
               "height_mm": 1100, "colour": "#d8c8a8", "layer": "ceiling",
               "placement": {"x_mm": 2500, "y_mm": 1200, "rotation_deg": 0}}
    assert isinstance(preview({"room": "Wohnen", "items": [table, pendant]}, make_ctx()), Confirmation)
    without_layer = {key: value for key, value in pendant.items() if key != "layer"}
    refused = preview({"room": "Wohnen", "items": [table, without_layer]}, make_ctx())
    assert isinstance(refused, str) and "overlap" in refused


def test_the_tool_tells_the_designer_about_the_ceiling_layer() -> None:
    from plugins.compose_room.tool import ComposeRoomArgs

    assert "layer 'ceiling'" in ComposeRoomArgs.model_fields["items"].description


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


# --- an empty room (rooms-page) ------------------------------------------------------------


def test_two_placed_items_are_listed_in_the_confirmations_table(make_ctx, room) -> None:
    """confirmation-summaries: one row per item from the placement checks; the summary is unchanged."""
    bench = {"id": "bench", "type": "stand-in", "name": "Bench", "width_mm": 1200, "depth_mm": 400, "height_mm": 450,
             "colour": "#8a6a48", "placement": {"wall": 2, "offset_mm": 400}}
    shown = preview({"room": "Wohnen", "items": [bench, SOFA]}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.table is not None
    assert shown.table["columns"] == ["Item", "Kind", "Size (mm)", "Placement", "Centre (mm)", "Rotation"]
    first, second = shown.table["rows"]
    assert first[:4] == ["Bench", "stand-in", "1200 × 400 × 450", "wall 3, 3400 mm from the left end"]
    assert second == ["Sofa", "stand-in", "2200 × 950 × 800", "free, 180°", "2500, 2600", "180°"]
    assert shown.summary.splitlines()[0] == "Room Wohnen: 2 item(s)"
    assert "- sofa (stand-in, Sofa): 2200 × 950 × 800 mm, at (2500, 2600) mm turned 180°" in shown.summary


def test_an_empty_room_is_confirmed_as_version_one_and_built(make_ctx, tool_deps, tool_state, room) -> None:
    shown = preview({"room": "Wohnen", "items": []}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.summary.startswith("Room Wohnen: the room only, no items")
    assert shown.table is not None and shown.table["rows"] == []
    output = run({"room": "Wohnen", "items": []}, replace(make_ctx(), approved=True))
    assert "Created Wohnen version 1; its build has started" in output.text
    wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1))


def test_removing_the_last_item_lists_it_and_leaves_an_empty_version(make_ctx, tool_state, room) -> None:
    run({"room": "Wohnen", "items": [SOFA]}, replace(make_ctx(), approved=True))
    wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1))
    shown = preview({"room": "Wohnen", "items": []}, make_ctx())
    assert "Compared with version 1: removed: sofa" in shown.summary
    run({"room": "Wohnen", "items": []}, replace(make_ctx(), approved=True))
    folder = storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 2)
    import json

    assert json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))["items"] == []


def test_an_empty_apartment_is_refused_without_a_pause(make_ctx, tool_deps, room) -> None:
    with tool_deps.session() as session:
        house_file.upsert_apartment(
            session, "Wohnung", 2600, 100,
            [{"name": "Küche", "corners_mm": WOHNEN, "height_mm": None, "openings": []}],
        )
        session.commit()
    refused = preview({"apartment": "Wohnung", "items": []}, make_ctx())
    assert isinstance(refused, str) and "an apartment composition needs at least one item" in refused


# --- hidden items (hidden-room-items) -------------------------------------------------------


def test_a_hidden_sofa_is_marked_in_the_summary_and_hiding_it_is_the_change(make_ctx, tool_state, tool_deps, room) -> None:
    run({"room": "Wohnen", "items": [SOFA]}, replace(make_ctx(), approved=True))
    wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1))
    shown = preview({"room": "Wohnen", "items": [{**SOFA, "hidden": True}]}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "- sofa (stand-in, Sofa): 2200 × 950 × 800 mm, at (2500, 2600) mm turned 180°, hidden" in shown.summary
    assert "Compared with version 1: hidden: sofa" in shown.summary
    run({"room": "Wohnen", "items": [{**SOFA, "hidden": True}]}, replace(make_ctx(), approved=True))
    wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 2))
    assert "Compared with version 2: shown: sofa" in preview({"room": "Wohnen", "items": [SOFA]}, make_ctx()).summary
    with tool_deps.session() as session:
        [listed] = house_file.compositions(session, tool_state.settings.render_root)
    assert listed["items"][0]["hidden"] is True


def test_a_hidden_piece_must_still_be_approved(make_ctx, tool_deps, approved_desk) -> None:
    with tool_deps.session() as session:
        house_file.unapprove_version(session, "desk", 1)
        session.commit()
    refused = preview({"room": "Wohnen", "items": [{**DESK, "hidden": True}]}, make_ctx())
    assert isinstance(refused, str) and "desk version 1 is not approved" in refused


def test_the_tool_tells_the_designer_how_to_hide_an_item() -> None:
    from plugins.compose_room.tool import ComposeRoomArgs

    description = ComposeRoomArgs.model_fields["items"].description
    assert "hidden: true" in description and "compose without the flag" in description


# --- the floor finish (room-floor-finish) ---------------------------------------------------

TILES = {"tile_width_mm": 600, "tile_length_mm": 600, "tile_colour": "#e8e4dc", "grout_colour": "#9a958c",
         "grout_width_mm": 3}


def test_a_floor_finish_is_shown_for_confirmation_and_its_changes_are_listed(make_ctx, tool_state, tool_deps, room) -> None:
    shown = preview({"room": "Wohnen", "items": [SOFA], "floor": TILES}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "Floor: 600 × 600 mm tiles, grid, tile #e8e4dc, grout 3 mm #9a958c" in shown.summary
    run({"room": "Wohnen", "items": [SOFA], "floor": TILES}, replace(make_ctx(), approved=True))
    wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1))
    with tool_deps.session() as session:
        [listed] = house_file.compositions(session, tool_state.settings.render_root)
    assert listed["floor"]["pattern"] == "grid"
    changed = preview({"room": "Wohnen", "items": [SOFA], "floor": {**TILES, "tile_width_mm": 300}}, make_ctx())
    assert "floor: 300 × 600 mm tiles" in changed.summary
    dropped = preview({"room": "Wohnen", "items": [SOFA]}, make_ctx())
    assert "floor finish removed" in dropped.summary


def test_an_unknown_floor_field_is_recorded_as_an_extension_request(make_ctx, room) -> None:
    refused = preview({"room": "Wohnen", "items": [SOFA], "floor": {**TILES, "texture": "marble.png"}}, make_ctx())
    assert isinstance(refused, str) and "texture" in refused


def test_the_tool_describes_the_floor_finish() -> None:
    from plugins.compose_room.tool import ComposeRoomArgs

    description = ComposeRoomArgs.model_fields["floor"].description
    assert "tile_width_mm" in description and "staggered" in description and "restate it" in description


# --- lamp lights (room-lamp-lights) ---------------------------------------------------------


def test_a_lit_pendant_is_shown_for_confirmation(make_ctx, room) -> None:
    pendant = {"id": "pendant", "type": "stand-in", "name": "Pendant", "width_mm": 500, "depth_mm": 500,
               "height_mm": 1100, "colour": "#d8c8a8", "layer": "ceiling",
               "light": {"type": "point", "lumens": 800, "kelvin": 2700},
               "placement": {"x_mm": 2500, "y_mm": 1200, "rotation_deg": 0}}
    shown = preview({"room": "Wohnen", "items": [pendant]}, make_ctx())
    assert isinstance(shown, Confirmation)


def test_the_tool_describes_lamp_lights() -> None:
    from plugins.compose_room.tool import ComposeRoomArgs

    description = ComposeRoomArgs.model_fields["items"].description
    assert "light {type 'point'" in description and "2700 K warm" in description


# --- LED strips (room-led-strips) -----------------------------------------------------------


def test_a_composition_holding_a_strip_is_summarised_with_its_derived_size(make_ctx, room) -> None:
    strip = {"id": "cove", "type": "led-strip", "name": "Cove", "length_mm": 2000, "lumens_per_m": 300,
             "kelvin": 2700, "mount_height_mm": 2200, "facing": "up", "placement": {"wall": 2, "offset_mm": 500}}
    shown = preview({"room": "Wohnen", "items": [strip]}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "- cove (led-strip, Cove): 2000 × 15 × 10 mm, against wall 3, 2500 mm from the left end" in shown.summary
    assert shown.table["rows"][0][:3] == ["Cove", "led-strip", "2000 × 15 × 10"]


def test_the_tool_describes_led_strips() -> None:
    from plugins.compose_room.tool import ComposeRoomArgs

    description = ComposeRoomArgs.model_fields["items"].description
    assert "'led-strip'" in description and "place it again" in description


def test_a_hung_piece_is_previewed_and_stored_with_its_height(make_ctx, tool_state, approved_desk) -> None:
    hung = {**DESK, "placement": {"wall": 1, "offset_mm": 500, "mount_height_mm": 1500}}
    shown = preview({"room": "Wohnen", "items": [hung]}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "against wall 2, 2500 mm from the left end, hung at 1500 mm" in shown.summary
    run({"room": "Wohnen", "items": [hung]}, replace(make_ctx(), approved=True))
    folder = storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1)
    import json

    stored = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    assert stored["items"][0]["placement"]["mount_height_mm"] == 1500
    wait_for_status(folder)


# --- the conversation's piece at its saved place (place-piece-from-owner-words) -------------


def _bound(make_ctx, tool_deps):
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "Desk", package_id="desk")
        house_file.set_thread_room(session, thread.id, house_file.room_by_name(session, "Wohnen"))
        session.commit()
        return make_ctx(thread_id=thread.id, package_id="desk")


def _place(tool_state, wall, offset):
    from app.packages.placements import write_placement

    folder = storage.version_dir(tool_state.settings.render_root, "desk", 1)
    write_placement(folder, "Wohnen", {"wall": wall, "offset_mm": offset, "left_mm": 0})


def test_the_saved_place_adds_the_piece_to_the_rooms_latest_items(make_ctx, tool_deps, tool_state, approved_desk) -> None:
    run({"room": "Wohnen", "items": [SOFA]}, replace(make_ctx(), approved=True))
    wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1))
    _place(tool_state, 1, 500)
    shown = preview({"with_saved_place": True}, _bound(make_ctx, tool_deps))
    assert isinstance(shown, Confirmation)
    assert "- desk (piece, desk v1): 1000 × 300 × 700 mm, against wall 2, 2500 mm from the left end" in shown.summary
    assert "- sofa (stand-in, Sofa)" in shown.summary
    assert "Compared with version 1: added: desk" in shown.summary


def test_the_saved_place_moves_a_piece_already_in_the_room(make_ctx, tool_deps, tool_state, approved_desk) -> None:
    run({"room": "Wohnen", "items": [DESK, SOFA]}, replace(make_ctx(), approved=True))
    wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1))
    _place(tool_state, 1, 1500)
    shown = preview({"with_saved_place": True}, _bound(make_ctx, tool_deps))
    assert "Compared with version 1: moved: desk" in shown.summary
    assert shown.proposal["items"] == 2


def test_the_saved_place_needs_a_stored_placement(make_ctx, tool_deps, approved_desk) -> None:
    refused = preview({"with_saved_place": True}, _bound(make_ctx, tool_deps))
    assert refused == "the piece has no place in Wohnen yet; ask the owner where it goes with ask_placement"


def test_the_saved_place_takes_no_items(make_ctx, tool_deps, approved_desk) -> None:
    refused = preview({"with_saved_place": True, "items": [SOFA]}, _bound(make_ctx, tool_deps))
    assert refused == "pass either with_saved_place or a room with its items, not both"
    assert preview({"room": "Wohnen"}, make_ctx()).startswith("items is required")


def test_the_saved_place_of_an_unapproved_version_points_to_approval(make_ctx, tool_deps, tool_state, approved_desk) -> None:
    with tool_deps.session() as session:
        house_file.unapprove_version(session, "desk", 1)
        session.commit()
    _place(tool_state, 1, 500)
    refused = preview({"with_saved_place": True}, _bound(make_ctx, tool_deps))
    assert isinstance(refused, str) and "Call approve_version to ask the owner" in refused


def test_a_wall_placement_is_shown_in_the_owners_terms(make_ctx, approved_desk) -> None:
    """place-piece-from-owner-words: walls numbered from 1, the distance from the left end."""
    # Wall index 1 is the room's second wall, 4000 mm long; the desk is 1000 mm wide.
    desk = {**DESK, "placement": {"wall": 1, "offset_mm": 3000}}
    shown = preview({"room": "Wohnen", "items": [desk]}, make_ctx())
    assert "against wall 2, 0 mm from the left end" in shown.summary
    assert shown.table["rows"][0][3] == "wall 2, 0 mm from the left end"
    assert "wall 1" not in shown.summary and "3000 mm" not in shown.summary
