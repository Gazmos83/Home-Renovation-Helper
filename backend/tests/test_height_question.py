"""simple-height-question-reply: a plain expected-height question gets one fixed reply."""

from __future__ import annotations

import pytest

from app.agent.foreman import last_reply
from app.engineering.chat import HEIGHT_REPLY, height_question
from tests.graph_helpers import fake_models, make_harness


@pytest.mark.parametrize(
    "text",
    [
        "What's expected height",
        "what is the maximum height?",
        "Expected height?",
        "  what are the highest height ",
        "Tell me the target height.",
        "What’s the expected piece height",
    ],
)
def test_the_short_height_question_matches(text: str) -> None:
    assert height_question(text)


@pytest.mark.parametrize(
    "text",
    [
        "What's the expected depth",
        "What's the maximum height this cabinet can safely carry?",
        "What's the expected height of the wall cabinet",
        "What is the maximum height for the drawer runner",
        "What's the expected height and how wide is it?",
        "Make the expected height 2238",
        "",
    ],
)
def test_anything_longer_or_with_an_engineering_word_does_not(text: str) -> None:
    assert not height_question(text)


def test_the_reply_is_fixed_whatever_the_model_flagged_and_no_specialist_runs(tool_state) -> None:
    models = fake_models(
        foreman={
            "decisions": [
                {"specialist": "researcher", "reason": "height limit", "engineering_question": True}
            ]
        },
    )
    harness = make_harness(tool_state, models)
    state = harness.turn("What's expected height")
    assert last_reply(state) == "The height is not verified. What should the height be?" == HEIGHT_REPLY
    assert models["researcher"].calls == 0
    assert models["designer"].calls == 0
    assert models["intake"].calls == 0
