"""split-project-panel: the brief's settings are part of the facts the Foreman and the specialists get."""

from __future__ import annotations

from app.agent.foreman import brief_line
from tests.graph_helpers import fake_models, make_harness

BRIEF = {"room": "Hall", "purpose": "a bench by the door", "max_piece_height_mm": 900.0, "style": "oak", "budget_eur": 900}


def test_the_brief_line_lists_only_the_settings_that_are_set() -> None:
    assert brief_line({}) == ""
    assert brief_line(BRIEF) == (
        "room: Hall; purpose: a bench by the door; highest the piece may be: 900 mm; style: oak; budget: 900 EUR"
    )
    assert brief_line({"purpose": "a shelf", "budget_eur": 0}) == "purpose: a shelf; budget: 0 EUR"


def test_an_edited_brief_shows_in_the_next_foreman_and_specialist_prompts(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [{"specialist": "designer", "reason": "t"}]},
        designer={"replies": ["ok"]},
    )
    harness = make_harness(tool_state, models)
    harness.start()
    harness.graph.update_state(harness.config, {"brief": BRIEF})
    harness.turn("how much may it cost?")
    for prompt in (models["foreman"].decision_prompts[-1], models["designer"].prompts[-1]):
        text = "\n".join(str(m.content) for m in prompt)
        assert "Brief: room: Hall; purpose: a bench by the door" in text and "budget: 900 EUR" in text
