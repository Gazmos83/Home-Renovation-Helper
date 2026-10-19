"""Every model request is counted and fitted before it is sent (token-budget).

The budget trims the request copy only. `state["messages"]` is never modified.
Images are counted at a fixed cost. A request whose mandatory part does not fit,
or that would pass the day's ceiling, is refused before the call. Exchanges
trimmed from a request are replaced by a summary of them when a `summarize`
callback gives one that fits, else by a note that history was shortened
(studio-chat-polish).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langchain_core.tools import BaseTool

from app.agent.models.registry import BY_ID
from app.agent.prompts import wrap_summary

SAFETY_FACTOR: Final = 1.2
IMAGE_TOKENS: Final = 1100
DEFAULT_OUTPUT_RESERVE: Final = 2_048
DEFAULT_CONTEXT_BUDGET: Final = 32_000
DEFAULT_DAILY_CEILING: Final = 2_000_000

HISTORY_OMITTED_NOTE: Final = (
    "{count} earlier exchange(s) of this conversation are not included in this "
    "request to keep it within its size limit. Facts saved to the house file are "
    "still provided separately; if the question depends on something said earlier "
    "that is not shown, ask the owner to restate it."
)

RefusalKind = Literal["input_too_large", "daily_limit"]

# Given the exchanges a request drops (oldest first), their summary or `None`.
Summarize = Callable[[list[BaseMessage]], str | None]

# How the owner reads each agent's name in texts the application writes (meet-the-crew);
# prompts keep the role names.
PERSONA_NAMES: Final = {
    "foreman": "Little Homey",
    "intake": "Lil' Worm",
    "designer": "Lil' Glitty",
    "builder": "Muscles",
    "researcher": "Money Bags",
    "reviewer": "Mr. Lookback",
    "lighting": "Bulbs",
}


class BudgetRefused(Exception):
    """The call is not made. `kind` is `input_too_large` or `daily_limit`."""

    def __init__(self, kind: RefusalKind, needed: int, usable: int) -> None:
        self.kind = kind
        self.needed = needed
        self.usable = usable
        super().__init__(kind)


def refusal_message(role: str, error: BudgetRefused) -> str:
    title = PERSONA_NAMES.get(role, role.capitalize())
    if error.kind == "daily_limit":
        reason = "today's limit is reached; it resets at midnight"
    else:
        reason = "the message is too long; please shorten it"
    return f"{title} can't take this on right now: {reason}."


@dataclass(frozen=True, slots=True)
class RequestBudget:
    limit: int
    output_reserve: int

    @property
    def usable(self) -> int:
        return max(0, self.limit - self.output_reserve)

    @classmethod
    def for_model(
        cls,
        model_id: str,
        *,
        context_budget_tokens: int,
        max_output_tokens: int | None,
    ) -> RequestBudget:
        entry = BY_ID.get(model_id)
        window = entry.context_window if entry is not None else context_budget_tokens
        limit = min(window, context_budget_tokens)
        reserve = max_output_tokens if max_output_tokens is not None else DEFAULT_OUTPUT_RESERVE
        return cls(limit=limit, output_reserve=reserve)


def _image_blocks(content: Any) -> int:
    if not isinstance(content, list):
        return 0
    return sum(1 for block in content if isinstance(block, dict) and block.get("type") == "image_url")


def _countable(tool: Any) -> BaseTool | dict[str, Any]:
    if isinstance(tool, (BaseTool, dict)):
        return tool
    return {
        "type": "function",
        "function": {
            "name": str(getattr(tool, "name", "")),
            "description": str(getattr(tool, "description", "")),
        },
    }


def count(messages: Sequence[BaseMessage], tools: Sequence[Any] | None = None) -> int:
    countable = [_countable(tool) for tool in tools] if tools else None
    approx = count_tokens_approximately(list(messages), tools=countable)
    images = sum(_image_blocks(getattr(message, "content", None)) for message in messages)
    return math.ceil(approx * SAFETY_FACTOR) + IMAGE_TOKENS * images


def _split_current(history: Sequence[BaseMessage]) -> tuple[list[BaseMessage], list[BaseMessage]]:
    for index in range(len(history) - 1, -1, -1):
        if isinstance(history[index], HumanMessage):
            return list(history[:index]), list(history[index:])
    return [], list(history)


def fit(
    budget: RequestBudget,
    system: Sequence[BaseMessage],
    history: Sequence[BaseMessage],
    *,
    tools: Sequence[Any] | None = None,
    summarize: Summarize | None = None,
    trigger_percent: int = 100,
    keep_turns: int = 0,
    covered_through: str | None = None,
    recent_inputs: int = 0,
) -> list[BaseMessage]:
    """The request to send. Raises `BudgetRefused` when the mandatory part does not fit.

    Pure given `summarize`: the dropped exchanges go to it once, and its answer is
    sent in their place when it fits in the note's space plus what the trim freed.
    Compression starts once the earlier history passes `trigger_percent` of the usable
    budget; the last `keep_turns` turns are sent in full while the whole request still
    fits; exchanges up to `covered_through` (the stored note's last message) are always
    replaced by the note (conversation-memory-settings). With `recent_inputs` above 0, every
    exchange before the Nth most recent owner input is replaced by the note as well, however
    much room is left (conversation-recent-inputs). The defaults are the behaviour before
    those settings.
    """
    earlier, current = _split_current(history)
    mandatory = count([*system, *current], tools)
    usable = budget.usable
    if mandatory > usable:
        raise BudgetRefused("input_too_large", mandatory, usable)

    if not earlier:
        return [*system, *current]
    covered = _covered(earlier, covered_through)
    if recent_inputs > 0:
        covered = max(covered, kept_turns_start(earlier, recent_inputs))
    threshold = usable * trigger_percent // 100
    if not covered and mandatory + count(earlier) <= threshold:
        return [*system, *earlier, *current]

    forced, rest = earlier[:covered], earlier[covered:]
    note_cost = count([SystemMessage(HISTORY_OMITTED_NOTE.format(count=len(earlier)))])
    start = kept_turns_start(rest, keep_turns)
    pool, protected = rest[:start], rest[start:]
    if protected and mandatory + note_cost + count(protected) > usable:
        pool, protected = rest, []
    remaining = max(0, threshold - mandatory - note_cost - (count(protected) if protected else 0))
    kept = (
        trim_messages(
            pool,
            max_tokens=remaining,
            token_counter=lambda messages, **_kwargs: count(messages),
            strategy="last",
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
        if remaining > 0
        else []
    )
    dropped = [*forced, *pool[: len(pool) - len(kept)]]
    kept = [*kept, *protected]
    if summarize is not None and dropped:
        summary = summarize(list(dropped))
        if summary and summary.strip():
            summarised = SystemMessage(wrap_summary(summary.strip()))
            freed = remaining - (count(kept[: len(kept) - len(protected)]) if len(kept) > len(protected) else 0)
            if count([summarised]) <= note_cost + freed:
                return [*system, summarised, *kept, *current]
    omitted = sum(1 for message in dropped if isinstance(message, HumanMessage))
    note = SystemMessage(HISTORY_OMITTED_NOTE.format(count=max(omitted, 1)))
    return [*system, note, *kept, *current]


def _covered(earlier: Sequence[BaseMessage], through: str | None) -> int:
    """How many leading messages a stored note covers: up to and including `through`, else none."""
    if not through:
        return 0
    for index, message in enumerate(earlier):
        if message.id == through:
            return index + 1
    return 0


def kept_turns_start(messages: Sequence[BaseMessage], keep_turns: int) -> int:
    """The index where the last `keep_turns` owner-started turns begin; `len(messages)` for none."""
    if keep_turns <= 0:
        return len(messages)
    starts = [index for index, message in enumerate(messages) if isinstance(message, HumanMessage)]
    return starts[-keep_turns] if len(starts) >= keep_turns else 0


def check_daily(used_today: int, needed: int, ceiling: int) -> None:
    if used_today + needed > ceiling:
        raise BudgetRefused("daily_limit", used_today + needed, ceiling)


def prepare(
    budget: RequestBudget,
    system: str,
    history: Sequence[BaseMessage],
    *,
    tools: Sequence[Any] | None = None,
    used_today: int = 0,
    daily_ceiling: int = DEFAULT_DAILY_CEILING,
    summarize: Summarize | None = None,
    trigger_percent: int = 100,
    keep_turns: int = 0,
    covered_through: str | None = None,
    recent_inputs: int = 0,
) -> tuple[list[BaseMessage], int]:
    """Fit the request, then refuse if it would pass the day's ceiling.

    Returns the messages to send and the counted estimate (input + output reserve).
    """
    fitted = fit(
        budget, [SystemMessage(system)], history, tools=tools, summarize=summarize,
        trigger_percent=trigger_percent, keep_turns=keep_turns, covered_through=covered_through,
        recent_inputs=recent_inputs,
    )
    counted = count(fitted, tools)
    needed = counted + budget.output_reserve
    check_daily(used_today, needed, daily_ceiling)
    return fitted, counted
