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
    assert "as already in the house file" in shown.summary


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
