"""A conversation's title, written by the Foreman slot's model (homeowner-chat).

After the first answered turn of an untitled thread, one short, metered call asks
for a three-to-six-word title of the owner's first message. When that call is
refused or fails, or answers nothing usable, the title is the first words of the
message instead. The caller stores it only while the thread still has no title,
so an owner's rename always wins.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Final

from langchain_core.messages import BaseMessage, HumanMessage

from app.agent.prompts import neutralise

logger = logging.getLogger("app")

TITLE_OUTPUT_TOKENS: Final = 24
TITLE_MAX_CHARS: Final = 200
FALLBACK_MAX_CHARS: Final = 60

TITLE_INSTRUCTION: Final = """\
Write a title of three to six words for a home-renovation conversation that \
starts with the owner's message below. Answer with the title only: no quotes, \
no full stop, no other words."""

# `call(system, messages, max_output)` makes one metered model call and returns its text.
SideCall = Callable[[str, list[BaseMessage], int], str]


def fallback_title(message: str) -> str:
    """The message's first words, at most 60 characters, cut at a word boundary."""
    words = " ".join(message.split())
    if len(words) <= FALLBACK_MAX_CHARS:
        return words
    cut = words[: FALLBACK_MAX_CHARS + 1]
    boundary = cut.rfind(" ")
    return (cut[:boundary] if boundary > 0 else cut[:FALLBACK_MAX_CHARS]).rstrip(" ,;:-")


def clean_title(text: str) -> str:
    """One line, no surrounding quotes or full stop, delimiters neutralised, capped."""
    line = " ".join(text.split())
    line = re.sub(r'^["\'“”‘’]+|["\'“”‘’.]+$', "", line).strip()
    return neutralise(line)[:TITLE_MAX_CHARS]


def title_for(call: SideCall, message: str) -> str:
    """A title for a conversation that starts with `message`. Never raises."""
    try:
        written = clean_title(call(TITLE_INSTRUCTION, [HumanMessage(message)], TITLE_OUTPUT_TOKENS))
    except Exception as error:  # noqa: BLE001 - a refused or failed call falls back, never fails the turn
        logger.info("title fell back", extra={"context": {"error_type": type(error).__name__}})
        written = ""
    return written or neutralise(fallback_title(message))
