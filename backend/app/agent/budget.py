"""Every model request is counted and fitted before it is sent (token-budget).

The budget trims the request copy only. `state["messages"]` is never modified.
Images are counted at a fixed cost. A request whose mandatory part does not fit,
or that would pass the day's ceiling, is refused before the call.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langchain_core.tools import BaseTool

from app.agent.models.registry import BY_ID

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

ROLE_TITLES: Final = {
    "foreman": "Foreman",
    "intake": "Intake",
    "designer": "Designer",
    "builder": "Builder",
    "researcher": "Researcher",
    "reviewer": "Reviewer",
    "lighting": "Lighting",
}


class BudgetRefused(Exception):
    """The call is not made. `kind` is `input_too_large` or `daily_limit`."""

    def __init__(self, kind: RefusalKind, needed: int, usable: int) -> None:
        self.kind = kind
        self.needed = needed
        self.usable = usable
        super().__init__(kind)


def refusal_message(role: str, error: BudgetRefused) -> str:
    title = ROLE_TITLES.get(role, role.capitalize())
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
) -> list[BaseMessage]:
    """The request to send. Raises `BudgetRefused` when the mandatory part does not fit."""
    earlier, current = _split_current(history)
    mandatory = count([*system, *current], tools)
    usable = budget.usable
    if mandatory > usable:
        raise BudgetRefused("input_too_large", mandatory, usable)

    if not earlier:
        return [*system, *current]
    if mandatory + count(earlier) <= usable:
        return [*system, *earlier, *current]

    note_cost = count([SystemMessage(HISTORY_OMITTED_NOTE.format(count=len(earlier)))])
    remaining = max(0, usable - mandatory - note_cost)
    kept = (
        trim_messages(
            earlier,
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
    dropped = earlier[: len(earlier) - len(kept)]
    omitted = sum(1 for message in dropped if isinstance(message, HumanMessage))
    note = SystemMessage(HISTORY_OMITTED_NOTE.format(count=max(omitted, 1)))
    return [*system, note, *kept, *current]


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
) -> tuple[list[BaseMessage], int]:
    """Fit the request, then refuse if it would pass the day's ceiling.

    Returns the messages to send and the counted estimate (input + output reserve).
    """
    fitted = fit(budget, [SystemMessage(system)], history, tools=tools)
    counted = count(fitted, tools)
    needed = counted + budget.output_reserve
    check_daily(used_today, needed, daily_ceiling)
    return fitted, counted
