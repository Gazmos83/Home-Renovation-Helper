"""design-agents: Intake's `record_brief` — preview, confirmation, refusal."""

from __future__ import annotations

from dataclasses import replace

from app.agent import house_file
from app.agent.tools.base import Confirmation
from app.agent.tools.record_brief import preview, record_brief, run

HALL = {
    "room_name": "Hall",
    "corners_mm": [[0, 0], [1200, 0], [1200, 3000], [0, 3000]],
    "ceiling_height_mm": 2400,
    "purpose": "a bench by the front door",
    "style": "light oak",
    "budget_eur": 400,
}


def test_the_confirmation_summarises_the_numbers(make_ctx) -> None:
    shown = preview(HALL, make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.subject == "brief"
    assert "Room Hall: 1200 × 3000 mm, ceiling 2400 mm" in shown.summary
    assert "Style: light oak" in shown.summary
    assert "Budget: 400 EUR" in shown.summary
    assert shown.proposal["brief"]["budget_eur"] == 400


def test_nothing_is_written_before_yes(make_ctx, tool_deps) -> None:
    preview(HALL, make_ctx())
    with tool_deps.session() as session:
        assert house_file.room_by_name(session, "Hall") is None
        assert house_file.preferences(session) == {}


def test_yes_writes_the_room_the_preferences_and_the_brief(make_ctx, tool_deps) -> None:
    output = run(HALL, replace(make_ctx(), approved=True))
    assert output.update["brief"] == {
        "room": "Hall",
        "purpose": "a bench by the front door",
        "style": "light oak",
        "budget_eur": 400,
    }
    with tool_deps.session() as session:
        room = house_file.room_by_name(session, "Hall")
        assert room is not None and room.height_mm == 2400
        assert house_file.preferences(session) == {"style": "light oak", "budget_eur": "400"}


def test_the_tool_does_not_run_without_approval(make_ctx, tool_deps) -> None:
    result = run(HALL, make_ctx())
    assert "confirmation" in result
    with tool_deps.session() as session:
        assert house_file.room_by_name(session, "Hall") is None


def test_a_room_refused_by_name_skips_the_pause(make_ctx) -> None:
    refused = preview(
        {
            **HALL,
            "openings": [
                {"wall": 0, "type": "door", "offset_mm": 0, "width_mm": 900, "height_mm": 2100, "sill_mm": 40}
            ],
        },
        make_ctx(),
    )
    assert isinstance(refused, str)
    assert "openings[0] is a door and must not have a sill" in refused


def test_an_existing_room_can_be_named_without_its_measurements(make_ctx, tool_deps) -> None:
    run(HALL, replace(make_ctx(), approved=True))
    shown = preview(
        {"room_name": "Hall", "purpose": "a coat rack", "budget_eur": 90}, make_ctx()
    )
    assert isinstance(shown, Confirmation)
    assert "Room Hall: 1200 × 3000 mm, ceiling 2400 mm, 0 opening(s)" in shown.summary


def test_an_unknown_room_without_measurements_asks_for_them(make_ctx) -> None:
    refused = preview({"room_name": "Attic", "purpose": "a shelf"}, make_ctx())
    assert isinstance(refused, str)
    assert "not in the house file" in refused


def test_the_tool_is_gated_and_named(make_ctx) -> None:
    assert record_brief.name == "record_brief"
    assert record_brief.gated


def test_an_l_shaped_room_can_be_proposed(make_ctx) -> None:
    shown = preview(
        {
            **HALL,
            "room_name": "L-room",
            "corners_mm": [[0, 0], [4000, 0], [4000, 2000], [2000, 2000], [2000, 4000], [0, 4000]],
        },
        make_ctx(),
    )
    assert isinstance(shown, Confirmation)
    assert shown.proposal["room"]["corners_mm"][3] == [2000, 2000]


PIECE_ONLY = {
    "purpose": "a listening wall about 2200 mm wide and 2200 mm tall",
    "max_piece_height_mm": 2200,
    "style": "light oak",
    "budget_eur": 900,
}


def test_a_brief_without_a_room_previews_with_the_room_not_given(make_ctx) -> None:
    shown = preview(PIECE_ONLY, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "Room: not given yet" in shown.summary
    assert "Style: light oak" in shown.summary
    assert shown.proposal["room"] is None
    assert "room" not in shown.proposal["brief"]


def test_yes_without_a_room_stores_the_brief_and_preferences_and_no_room(make_ctx, tool_deps) -> None:
    output = run(PIECE_ONLY, replace(make_ctx(), approved=True))
    assert output.update["brief"] == {
        "purpose": "a listening wall about 2200 mm wide and 2200 mm tall",
        "max_piece_height_mm": 2200,
        "style": "light oak",
        "budget_eur": 900,
    }
    with tool_deps.session() as session:
        assert house_file.rooms(session) == []
        assert house_file.preferences(session) == {"style": "light oak", "budget_eur": "900"}


def test_a_blank_room_name_counts_as_no_room(make_ctx) -> None:
    shown = preview({**PIECE_ONLY, "room_name": "  "}, make_ctx())
    assert isinstance(shown, Confirmation)
    assert "Room: not given yet" in shown.summary


def test_measurements_without_a_room_name_are_refused(make_ctx) -> None:
    refused = preview(
        {**PIECE_ONLY, "corners_mm": [[0, 0], [1200, 0], [1200, 3000], [0, 3000]], "ceiling_height_mm": 2400},
        make_ctx(),
    )
    assert isinstance(refused, str)
    assert "a room needs a name" in refused


def _thread_room(tool_deps, thread_id) -> str | None:
    with tool_deps.session() as session:
        room, _ = house_file.thread_scope(session, thread_id)
        return room.name if room else None


def _new_thread(tool_deps):
    with tool_deps.session() as session:
        thread = house_file.create_thread(session, "Bench")
        session.commit()
        return thread.id


def test_yes_with_a_room_confirms_it_for_the_conversation(make_ctx, tool_deps) -> None:
    thread_id = _new_thread(tool_deps)
    assert _thread_room(tool_deps, thread_id) is None
    run(HALL, replace(make_ctx(thread_id=thread_id), approved=True))
    assert _thread_room(tool_deps, thread_id) == "Hall"


def test_a_brief_without_a_room_writes_no_room(make_ctx, tool_deps) -> None:
    thread_id = _new_thread(tool_deps)
    ctx = make_ctx(thread_id=thread_id)
    shown = preview({"purpose": "a listening wall", "budget_eur": 900}, ctx)
    assert isinstance(shown, Confirmation)
    assert "Room: not given yet" in shown.summary
    output = run({"purpose": "a listening wall", "budget_eur": 900}, replace(ctx, approved=True))
    assert "room" not in output.update["brief"]
    assert _thread_room(tool_deps, thread_id) is None
    with tool_deps.session() as session:
        assert house_file.rooms(session) == []


def test_a_brief_takes_the_conversations_confirmed_room(make_ctx, tool_deps) -> None:
    thread_id = _new_thread(tool_deps)
    run(HALL, replace(make_ctx(thread_id=thread_id), approved=True))
    ctx = make_ctx(thread_id=thread_id)
    shown = preview({"purpose": "a coat rack"}, ctx)
    assert "Room Hall: 1200 × 3000 mm" in shown.summary
    output = run({"purpose": "a coat rack"}, replace(ctx, approved=True))
    assert output.update["brief"]["room"] == "Hall"


def test_a_stored_room_named_in_a_brief_is_confirmed_by_yes(make_ctx, tool_deps) -> None:
    run(HALL, replace(make_ctx(), approved=True))
    thread_id = _new_thread(tool_deps)
    ctx = make_ctx(thread_id=thread_id)
    shown = preview({"room_name": "Hall", "purpose": "a coat rack"}, ctx)
    assert "Room Hall: 1200 × 3000 mm, ceiling 2400 mm" in shown.summary
    assert _thread_room(tool_deps, thread_id) is None
    run({"room_name": "Hall", "purpose": "a coat rack"}, replace(ctx, approved=True))
    assert _thread_room(tool_deps, thread_id) == "Hall"


def test_correcting_an_apartment_room_keeps_it_in_its_apartment(make_ctx, tool_deps) -> None:
    kitchen = {"name": "Küche", "corners_mm": [[0, 0], [3000, 0], [3000, 2800], [0, 2800]]}
    with tool_deps.session() as session:
        house_file.upsert_apartment(session, "Wohnung", 2600, 100, [kitchen])
        session.commit()
    run(
        {"room_name": "Küche", "ceiling_height_mm": 2450, "purpose": "a spice shelf"},
        replace(make_ctx(), approved=True),
    )
    with tool_deps.session() as session:
        room = house_file.room_by_name(session, "Küche")
        assert room.height_mm == 2450
        assert room.apartment_id == house_file.apartment_by_name(session, "Wohnung").id
