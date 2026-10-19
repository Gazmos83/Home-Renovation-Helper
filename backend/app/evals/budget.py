"""The eval run's own token cap, enforced in code from the usage the gateway reports.

Separate from the agents' daily ceilings: no `UsageRecorder` is attached to an
eval model, so `model_usage` and every agent slot's totals stay as they were.
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.observability.usage import _token_counts


class BudgetExhausted(RuntimeError):
    """The next model call would cross the run's token ceiling."""


class RunBudget:
    """Tokens used so far in one run, against its ceiling.

    A call in flight holds its output cap as a reservation, so calls that a
    metric starts together (Ragas asks for several completions at once) cannot
    jointly pass the ceiling.
    """

    def __init__(self, ceiling: int) -> None:
        self.ceiling = ceiling
        self.used = 0
        self._reserved = 0

    def meter(self, output_cap: int) -> RunMeter:
        """The callback for one model whose calls are capped at `output_cap` output tokens."""
        return RunMeter(self, output_cap)

    def reserve(self, output_cap: int) -> None:
        if self.used + self._reserved + output_cap > self.ceiling:
            raise BudgetExhausted(
                f"the next call could use up to {output_cap} output tokens; "
                f"{self.used} of the run's {self.ceiling} tokens are used"
            )
        self._reserved += output_cap

    def settle(self, output_cap: int, response: LLMResult | None) -> None:
        self._reserved -= output_cap
        if response is None:
            return
        input_tokens, output_tokens = _token_counts(response)
        if input_tokens is None and output_tokens is None:
            # Not reported: count the cap rather than nothing, so the ceiling still holds.
            self.used += output_cap
            return
        self.used += (input_tokens or 0) + (output_tokens or 0)


class RunMeter(BaseCallbackHandler):
    """Refuses a call before it starts when it could cross the ceiling, and counts it after."""

    raise_error = True

    def __init__(self, budget: RunBudget, output_cap: int) -> None:
        self.budget = budget
        self.output_cap = output_cap

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any, **kwargs: Any) -> None:
        self.budget.reserve(self.output_cap)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.budget.settle(self.output_cap, response)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self.budget.settle(self.output_cap, None)
