"""conversation-projects: Intake's `confirm_room` — the room a conversation works in."""

from __future__ import annotations

from dataclasses import replace

from app.agent import house_file
from app.agent.tools.base import Confirmation
from plugins.intake.tool import confirm_room, preview_confirm_room, run_confirm_room

SQUARE = [[0, 0], [3000, 0], [3000, 2000], [0, 2000]]
DOOR = [{"wall": 0, "type": "door", "offset_mm": 500, "width_mm": 900, "height_mm": 2050}]


def _setup(tool_deps):
    with tool_deps.session() as session:
        hall = house_file.upsert_room(session, "Hall", SQUARE, 2500, DOOR)
        wohnen = house_file.upsert_room(session, "Wohnen", [[0, 0], [5000, 0], [5000, 4000], [0, 4000]], 2600)
        thread = house_file.create_thread(session, "Bench")
        house_file.record_piece(session, "shoe-rack", "Shoe rack", room_id=hall.id)
        house_file.touch_thread(session, thread.id, package_id="shoe-rack")
        session.commit()
        return thread.id, hall.id, wohnen.id


def _scope(tool_deps, thread_id):
    with tool_deps.session() as session:
        room, apartment = house_file.thread_scope(session, thread_id)
        return (room.name if room else None), (apartment.name if apartment else None)


def test_the_tool_is_gated(tool_deps) -> None:
    assert confirm_room.gated and confirm_room.name == "confirm_room"


def test_the_stored_measurements_are_shown_and_yes_confirms_the_room(make_ctx, tool_deps) -> None:
    thread_id, *_ = _setup(tool_deps)
    ctx = make_ctx(thread_id=thread_id)

    shown = preview_confirm_room({"room": "Hall"}, ctx)
    assert isinstance(shown, Confirmation)
    assert "Hall: 3000 × 2000 mm, ceiling 2500 mm, 1 opening(s)" in shown.summary
    assert _scope(tool_deps, thread_id) == (None, None)

    output = run_confirm_room({"room": "Hall"}, replace(ctx, approved=True))
    assert "works in Hall" in output
    assert _scope(tool_deps, thread_id) == ("Hall", None)


def test_nothing_is_written_without_approval(make_ctx, tool_deps) -> None:
    thread_id, *_ = _setup(tool_deps)
    run_confirm_room({"room": "Hall"}, make_ctx(thread_id=thread_id))
    assert _scope(tool_deps, thread_id) == (None, None)


def test_switching_the_room_keeps_the_builds_rooms(make_ctx, tool_deps) -> None:
    thread_id, *_ = _setup(tool_deps)
    ctx = replace(make_ctx(thread_id=thread_id), approved=True)
    run_confirm_room({"room": "Hall"}, ctx)
    run_confirm_room({"room": "Wohnen"}, ctx)

    assert _scope(tool_deps, thread_id) == ("Wohnen", None)
    with tool_deps.session() as session:
        assert house_file.piece_room_name(session, "shoe-rack") == "Hall"


def test_a_build_is_moved_and_the_conversation_follows(make_ctx, tool_deps) -> None:
    thread_id, *_ = _setup(tool_deps)
    ctx = make_ctx(thread_id=thread_id)

    shown = preview_confirm_room({"room": "Wohnen", "package_id": "shoe-rack"}, ctx)
    assert "Move shoe-rack from Hall into Wohnen" in shown.summary

    run_confirm_room({"room": "Wohnen", "package_id": "shoe-rack"}, replace(ctx, approved=True))
    assert _scope(tool_deps, thread_id) == ("Wohnen", None)
    with tool_deps.session() as session:
        assert house_file.piece_room_name(session, "shoe-rack") == "Wohnen"


def test_an_apartment_is_confirmed_with_each_rooms_size(make_ctx, tool_deps) -> None:
    thread_id, *_ = _setup(tool_deps)
    with tool_deps.session() as session:
        house_file.upsert_apartment(
            session,
            "Flat",
            2550,
            120,
            [
                {"name": "Living", "corners_mm": [[0, 0], [5200, 0], [5200, 3800], [0, 3800]], "height_mm": None, "openings": []},
                {"name": "Bedroom", "corners_mm": [[5200, 0], [8400, 0], [8400, 3800], [5200, 3800]], "height_mm": None, "openings": []},
            ],
        )
        session.commit()
    ctx = make_ctx(thread_id=thread_id)

    shown = preview_confirm_room({"apartment": "Flat"}, ctx)
    assert "Apartment Flat: 2 room(s)" in shown.summary
    assert "Living: 5200 × 3800 mm" in shown.summary

    run_confirm_room({"apartment": "Flat"}, replace(ctx, approved=True))
    assert _scope(tool_deps, thread_id) == (None, "Flat")


def test_an_unknown_room_is_refused_naming_it_without_a_pause(make_ctx, tool_deps) -> None:
    thread_id, *_ = _setup(tool_deps)
    refusal = preview_confirm_room({"room": "Attic"}, make_ctx(thread_id=thread_id))
    assert isinstance(refusal, str) and "'Attic'" in refusal
    assert _scope(tool_deps, thread_id) == (None, None)


def test_refusals_for_a_build_outside_the_conversation_an_apartment_move_and_bad_arguments(
    make_ctx, tool_deps
) -> None:
    thread_id, *_ = _setup(tool_deps)
    ctx = make_ctx(thread_id=thread_id)
    with tool_deps.session() as session:
        house_file.upsert_apartment(
            session, "Flat", 2550, 120,
            [{"name": "Living", "corners_mm": SQUARE, "height_mm": None, "openings": []}],
        )
        session.commit()

    outside = preview_confirm_room({"room": "Hall", "package_id": "murphy-bed"}, ctx)
    assert isinstance(outside, str) and "'murphy-bed'" in outside
    apartment_move = preview_confirm_room({"apartment": "Flat", "package_id": "shoe-rack"}, ctx)
    assert isinstance(apartment_move, str) and "not into a whole apartment" in apartment_move
    both = preview_confirm_room({"room": "Hall", "apartment": "Flat"}, ctx)
    neither = preview_confirm_room({}, ctx)
    assert isinstance(both, str) and isinstance(neither, str)
    assert "exactly one" in both and "exactly one" in neither
    assert _scope(tool_deps, thread_id) == (None, None)
