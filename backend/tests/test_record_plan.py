"""design-agents: Intake's `record_plan` — a whole apartment, confirmed once."""

from __future__ import annotations

from dataclasses import replace

from app.agent import house_file
from app.agent.tools.base import Confirmation
from plugins.intake.tool import preview_plan as preview
from plugins.intake.tool import record_plan
from plugins.intake.tool import run_plan as run

PLAN = {
    "apartment_name": "Flat",
    "ceiling_height_mm": 2550,
    "wall_thickness_mm": 120,
    "scale_note": "the 5.2 m dimension line under the living room",
    "assumptions": ["wall thickness 120 mm"],
    "rooms": [
        {
            "name": "Living room",
            "corners_mm": [[0, 0], [5200, 0], [5200, 3800], [0, 3800]],
            "printed_area_m2": 19.76,
            "openings": [
                {"wall": 0, "type": "window", "offset_mm": 800, "width_mm": 1800, "height_mm": 1350, "sill_mm": 900},
                {"wall": 1, "type": "door", "offset_mm": 1200, "width_mm": 900, "height_mm": 2050},
            ],
        },
        {"name": "Bedroom", "corners_mm": [[5200, 0], [8400, 0], [8400, 3800], [5200, 3800]]},
    ],
}


def test_the_confirmation_lists_each_room_with_size_and_area(make_ctx) -> None:
    shown = preview(PLAN, make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.subject == "plan"
    assert "Apartment Flat: ceiling 2550 mm, walls 120 mm, 2 room(s), 1 shared wall(s)" in shown.summary
    assert "- Living room: 5200 × 3800 mm, 19.76 m², 2 opening(s)" in shown.summary
    assert "- Bedroom: 3200 × 3800 mm, 12.16 m², 0 opening(s)" in shown.summary
    assert "Scale: the 5.2 m dimension line under the living room" in shown.summary
    assert "Assumed: wall thickness 120 mm" in shown.summary
    assert shown.proposal["rooms"][0] == {"name": "Living room", "area_m2": 19.76, "openings": 2}


def test_nothing_is_written_before_yes(make_ctx, tool_deps) -> None:
    preview(PLAN, make_ctx())
    with tool_deps.session() as session:
        assert house_file.apartment_by_name(session, "Flat") is None
        assert house_file.room_by_name(session, "Living room") is None


def test_yes_writes_the_apartment_and_both_rooms(make_ctx, tool_deps) -> None:
    output = run(PLAN, replace(make_ctx(), approved=True))
    assert "apartment Flat with 2 room(s)" in output.text
    with tool_deps.session() as session:
        apartment = house_file.apartment_by_name(session, "Flat")
        rooms = house_file.rooms_of(session, apartment)
        assert [r.name for r in rooms] == ["Bedroom", "Living room"]
        assert apartment.notes == "wall thickness 120 mm"


def test_the_tool_does_not_run_without_approval(make_ctx, tool_deps) -> None:
    assert "confirmation" in run(PLAN, make_ctx())
    with tool_deps.session() as session:
        assert house_file.apartment_by_name(session, "Flat") is None


def test_a_failing_room_is_refused_naming_it_with_no_pause(make_ctx) -> None:
    bad = {**PLAN, "rooms": [{
        "name": "Hall", "corners_mm": [[0, 0], [2000, 0], [2000, 2000], [0, 2000]],
        "openings": [{"wall": 0, "type": "door", "offset_mm": 0, "width_mm": 900, "height_mm": 2050, "sill_mm": 50}],
    }]}
    refused = preview(bad, make_ctx())
    assert isinstance(refused, str)
    assert "room 'Hall'" in refused and "must not have a sill" in refused


def test_overlapping_rooms_are_refused_naming_both(make_ctx) -> None:
    overlapping = {**PLAN, "rooms": [
        PLAN["rooms"][0],
        {"name": "Bedroom", "corners_mm": [[5000, 0], [8400, 0], [8400, 3800], [5000, 3800]]},
    ]}
    refused = preview(overlapping, make_ctx())
    assert isinstance(refused, str)
    assert "'Living room' and 'Bedroom' overlap" in refused


def test_an_area_that_disagrees_with_the_plan_is_a_warning_not_a_refusal(make_ctx) -> None:
    off = {**PLAN, "rooms": [{**PLAN["rooms"][0], "printed_area_m2": 32.3}, PLAN["rooms"][1]]}
    shown = preview(off, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "Check: Living room: the outline gives 19.76 m² but the plan prints 32.30 m²" in shown.summary
    assert shown.proposal["warnings"]


def test_a_read_again_is_checked_among_its_own_rooms_only(make_ctx) -> None:
    run(PLAN, replace(make_ctx(), approved=True))
    # The study covers part of the stored living room, which this read leaves out.
    study = {**PLAN, "rooms": [{"name": "Study", "corners_mm": [[4000, 0], [6000, 0], [6000, 3800], [4000, 3800]]}]}
    shown = preview(study, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "Removed: Living room; no pieces in it" in shown.summary


def test_the_tool_is_gated(make_ctx) -> None:
    assert record_plan.gated and record_plan.name == "record_plan"


def test_yes_makes_the_apartment_the_conversations_confirmed_scope(make_ctx, tool_deps) -> None:
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "Flat")
        session.commit()
        thread_id = thread.id
    run(PLAN, replace(make_ctx(thread_id=thread_id), approved=True))
    with tool_deps.session() as session:
        room, apartment = house_file.thread_scope(session, thread_id)
        assert room is None and apartment.name == "Flat"


# --- a plan read again (app-check-2026-10-09) --------------------------------------------

WOHNUNG = {
    "apartment_name": "Wohnung",
    "ceiling_height_mm": 2600,
    "scale_note": "the printed room areas",
    "rooms": [
        {"name": "Wohnen", "corners_mm": [[0, 0], [5200, 0], [5200, 4000], [0, 4000]]},
        {"name": "Küche", "corners_mm": [[5200, 0], [8000, 0], [8000, 4000], [5200, 4000]]},
        {"name": "Bad", "corners_mm": [[0, 4000], [2500, 4000], [2500, 6000], [0, 6000]]},
    ],
}
READ_AGAIN = {
    **WOHNUNG,
    "rooms": [
        {"name": "Wohnen", "corners_mm": [[0, 0], [5100, 0], [5100, 4000], [0, 4000]]},
        WOHNUNG["rooms"][1],
    ],
}


def _stored_wohnung(make_ctx, tool_deps) -> None:
    run(WOHNUNG, replace(make_ctx(), approved=True))
    with tool_deps.session() as session:
        bad = house_file.room_by_name(session, "Bad")
        house_file.record_piece(session, "towel-rack", "Towel rack", room_id=bad.id)
        session.commit()


def test_a_plan_read_again_shows_what_it_replaces(make_ctx, tool_deps) -> None:
    _stored_wohnung(make_ctx, tool_deps)
    shown = preview(READ_AGAIN, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "Replaces the stored apartment Wohnung" in shown.summary
    assert "- Wohnen: 5100 × 4000 mm (stored 5200 × 4000 mm)" in shown.summary
    assert 'Removed: Bad; towel-rack becomes "No room"' in shown.summary
    assert shown.proposal["replaces"]["removed"][0]["name"] == "Bad"
    with tool_deps.session() as session:
        assert house_file.room_by_name(session, "Bad") is not None


def test_a_new_room_in_a_read_again_is_marked_new(make_ctx, tool_deps) -> None:
    _stored_wohnung(make_ctx, tool_deps)
    flur = {"name": "Flur", "corners_mm": [[5200, 4000], [8000, 4000], [8000, 5000], [5200, 5000]]}
    shown = preview({**READ_AGAIN, "rooms": [*READ_AGAIN["rooms"], flur]}, make_ctx())
    assert "- Flur: 2800 × 1000 mm (new)" in shown.summary


def test_yes_to_a_read_again_deletes_the_removed_room(make_ctx, tool_deps) -> None:
    from app.db.models import Piece

    _stored_wohnung(make_ctx, tool_deps)
    output = run(READ_AGAIN, replace(make_ctx(), approved=True))
    assert "Removed: Bad." in output.text
    with tool_deps.session() as session:
        flat = house_file.apartment_by_name(session, "Wohnung")
        assert [r.name for r in house_file.rooms_of(session, flat)] == ["Küche", "Wohnen"]
        assert house_file.room_by_name(session, "Bad") is None
        assert session.get(Piece, "towel-rack").room_id is None


def test_a_read_again_is_refused_while_a_removed_rooms_composition_builds(make_ctx, tool_deps) -> None:
    from app.blender import storage

    _stored_wohnung(make_ctx, tool_deps)
    with tool_deps.session() as session:
        composition = house_file.record_composition(session, "room", "Bad")
        house_file.record_composition_version(session, composition, 1, None, [])
        session.commit()
    folder = storage.composition_version_dir(tool_deps.render_root, "bad", 1)
    folder.mkdir(parents=True)
    storage.write_status(folder, status="running")
    refused = preview(READ_AGAIN, make_ctx())
    assert isinstance(refused, str)
    assert "Bad is building or rendering; read the plan again once that has finished" in refused
    with tool_deps.session() as session:
        assert house_file.room_by_name(session, "Bad") is not None
