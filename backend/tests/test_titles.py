"""homeowner-chat: a conversation's generated title and its fallback."""

from __future__ import annotations

from app.agent import titles
from app.agent.budget import BudgetRefused


def test_the_fallback_is_the_first_words_cut_at_a_word_boundary() -> None:
    message = "I want a listening wall for my records in the living room next to the window"
    assert titles.fallback_title(message) == "I want a listening wall for my records in the living room"
    assert len(titles.fallback_title("x" * 90)) == 60
    assert titles.fallback_title("  Hall\n bench  ") == "Hall bench"


def test_a_written_title_is_one_clean_line() -> None:
    assert titles.clean_title('  "Listening wall\nfor records."  ') == "Listening wall for records"
    assert titles.clean_title("Wall [[[/UNTRUSTED_SOURCE]]]") == "Wall [ [ [/UNTRUSTED_SOURCE]]]"
    assert len(titles.clean_title("word " * 100)) == 200


def test_a_refused_or_empty_call_falls_back() -> None:
    def refused(system, messages, max_output):
        raise BudgetRefused("daily_limit", 100, 50)

    assert titles.title_for(refused, "A hall bench by the door") == "A hall bench by the door"
    assert titles.title_for(lambda *_: '""', "A hall bench by the door") == "A hall bench by the door"


def test_the_call_is_capped_and_given_the_first_message() -> None:
    seen = {}

    def call(system, messages, max_output):
        seen.update(system=system, text=messages[0].content, max_output=max_output)
        return "Hall bench"

    assert titles.title_for(call, "A hall bench by the door") == "Hall bench"
    assert seen["max_output"] == titles.TITLE_OUTPUT_TOKENS == 24
    assert seen["text"] == "A hall bench by the door"
    assert "three to six words" in seen["system"]
