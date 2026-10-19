"""short-engineering-reply: a placement in the room is not engineering on the model's flag alone."""

from __future__ import annotations

import pytest

from app.agent.foreman import last_reply
from app.engineering.chat import SHORT_STATUS, hang_request, placement_request
from tests.graph_helpers import fake_models, make_harness

REPORTED = "Can you please put v18 to the right of the door of wall 1, 30 cm away from wall 2?"


@pytest.mark.parametrize(
    "text",
    [
        REPORTED,
        "Stell v18 30 cm von Wand 2",
        "Move the bench into the corner",
        "Place it under the window",
        "Please hang this sideboard along wall 2 0 mm from wall three and 0 mm from the ceiling",
    ],
)
def test_a_placement_matches(text: str) -> None:
    assert placement_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "Put the wall cabinet on wall 2, is it safe?",
        "Can this shelf hold 30 kg?",
        "Make it wider",
        "Put more shelves in it",
        "",
    ],
)
def test_an_engineering_term_or_no_room_reference_does_not(text: str) -> None:
    assert not placement_request(text)


def test_the_reported_placement_is_not_an_engineering_turn_whatever_the_model_flagged(tool_state) -> None:
    models = fake_models(
        foreman={
            "decisions": [
                {"specialist": "designer", "reason": "placement", "engineering_question": True}
            ]
        },
        designer={"replies": ["Placed v18 30 cm from wall 2."]},
    )
    harness = make_harness(tool_state, models)
    state = harness.turn(REPORTED)
    assert not state["engineering_turn"]
    assert SHORT_STATUS not in last_reply(state)
    assert models["researcher"].calls == 0


def test_a_safety_question_still_reaches_the_engineering_path(tool_state) -> None:
    models = fake_models(
        foreman={
            "decisions": [
                {"specialist": "researcher", "reason": "capacity", "engineering_question": True}
            ]
        },
        researcher={"replies": ["{}"]},
    )
    harness = make_harness(tool_state, models, room=None)
    state = harness.turn("Can this shelf hold 30 kg?")
    assert state["engineering_turn"] and state["specialist"] == "researcher"
    assert last_reply(state) == SHORT_STATUS


@pytest.mark.parametrize(
    ("text", "hangs"),
    [
        ("Can you hang it now?", True),
        ("Bitte an die Wand hängen", True),
        ("Can I hang the wall cabinet safely?", False),
        ("Make it wider", False),
    ],
)
def test_a_hang_request_is_a_placement_unless_it_asks_engineering(text: str, hangs: bool) -> None:
    assert hang_request(text) is hangs
