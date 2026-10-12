"""Application-owned token-usage recording (CLAUDE.md §4; design.md decision 7).

Every chat-model call is recorded as one `model_usage` row by a LangChain
callback that never depends on Langfuse being configured and is attached
alongside (never instead of) `Tracing`'s handler. Storage never fails a turn: a
row that cannot be written costs one warning, exactly like a broken Langfuse
endpoint.

The operation name a row carries is not threaded through every call site as a
new `config` argument. Every gateway call already runs inside
`openrouter_client.gateway_errors(operation=...)`; `usage.operation(name)` below
sets the same name on a context variable for the duration of a call, and
`UsageRecorder.on_llm_end` reads it back.

Ownership is owner-only: this is a single-user product, so every recorded call
names the owner account (CLAUDE.md §1).
"""

from __future__ import annotations

import contextvars
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from sqlalchemy import Engine, case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import ModelUsage

logger = logging.getLogger("app")

UNKNOWN_OPERATION = "unknown"

_current_operation: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "usage_operation", default=None
)


@contextmanager
def operation(name: str) -> Iterator[None]:
    """Mark the operation name for any gateway call made inside the block."""
    token = _current_operation.set(name)
    try:
        yield
    finally:
        _current_operation.reset(token)


def _usage_metadata_counts(response: LLMResult) -> tuple[int | None, int | None]:
    input_tokens: int | None = None
    output_tokens: int | None = None
    for batch in response.generations:
        for generation in batch:
            message = getattr(generation, "message", None)
            usage = getattr(message, "usage_metadata", None) if message is not None else None
            if not usage:
                continue
            input_tokens = (input_tokens or 0) + int(usage.get("input_tokens") or 0)
            output_tokens = (output_tokens or 0) + int(usage.get("output_tokens") or 0)
    return input_tokens, output_tokens


def _token_usage_fallback_counts(response: LLMResult) -> tuple[int | None, int | None]:
    token_usage = (response.llm_output or {}).get("token_usage") or {}
    raw_input = token_usage.get("prompt_tokens", token_usage.get("input_tokens"))
    raw_output = token_usage.get("completion_tokens", token_usage.get("output_tokens"))
    return (
        int(raw_input) if raw_input is not None else None,
        int(raw_output) if raw_output is not None else None,
    )


def _token_counts(response: LLMResult) -> tuple[int | None, int | None]:
    """`usage_metadata` first (LangChain's standardised shape), then the
    provider's raw `llm_output["token_usage"]`, else both unknown — never 0,
    which would misread as "no cost" rather than "not observed"."""
    input_tokens, output_tokens = _usage_metadata_counts(response)
    if input_tokens is not None or output_tokens is not None:
        return input_tokens, output_tokens
    return _token_usage_fallback_counts(response)


class UsageRecorder(BaseCallbackHandler):
    """Records one `model_usage` row per chat-model call this turn makes.

    Built per turn exactly like `Tracing`'s handler: `owner_user_id` names who
    made the call, `project_id` is set only for a project-scoped call. Never
    raises into the turn.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        model_id: str,
        owner_user_id: UUID,
        project_id: UUID | None = None,
        trace_id: str | None = None,
        estimated_tokens: int | None = None,
        thread_id: UUID | None = None,
        private_tracing: Any = None,
    ) -> None:
        self._engine = engine
        self._thread_id = thread_id
        self._model_id = model_id
        self._owner_user_id = owner_user_id
        self._project_id = project_id
        self._trace_id = trace_id
        self._estimated_tokens = estimated_tokens
        self._private_tracing = private_tracing
        self._started = time.monotonic()

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        input_tokens, output_tokens = _token_counts(response)
        if self._private_tracing is not None:
            self._private_tracing.record_engineering_usage(model_id=self._model_id, trace_id=self._trace_id, input_tokens=input_tokens, output_tokens=output_tokens, duration_ms=max(0, int((time.monotonic() - self._started) * 1000)))
        try:
            with Session(self._engine) as session:
                session.add(
                    ModelUsage(
                        id=uuid4(),
                        model_id=self._model_id,
                        operation=_current_operation.get() or UNKNOWN_OPERATION,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        user_id=self._owner_user_id,
                        project_id=self._project_id,
                        trace_id=self._trace_id,
                        estimated_tokens=self._estimated_tokens,
                        thread_id=self._thread_id,
                    )
                )
                session.commit()
        except SQLAlchemyError as error:
            logger.warning(
                "usage.unrecorded",
                extra={"context": {"error_type": type(error).__name__}},
            )


def attach(run_config: dict[str, Any] | None, recorder: UsageRecorder) -> dict[str, Any]:
    """Merge a usage recorder into an optional existing run config.

    `run_config` is what `Tracing.turn` yields — a dict when tracing is
    configured, `None` when it is not. Either way the result carries the
    recorder, so usage recording never depends on tracing being on.
    """
    merged = dict(run_config) if run_config else {}
    merged["callbacks"] = [*(merged.get("callbacks") or []), recorder]
    return merged


@dataclass(frozen=True, slots=True)
class UsageLine:
    """One model's recorded tokens for a project. `calls_without_tokens` counts
    rows where the gateway reported no usage at all, so a caller can say so
    rather than silently reading 0."""

    model_id: str
    input_tokens: int
    output_tokens: int
    calls_without_tokens: int


def tokens_today(engine: Engine, model_id: str, tz: str) -> int:
    """Tokens already recorded for `model_id` since the start of the day in `tz`.

    A row with no token figures counts as its estimated_tokens.
    """
    zone = ZoneInfo(tz)
    start = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    recorded = func.coalesce(ModelUsage.input_tokens, 0) + func.coalesce(ModelUsage.output_tokens, 0)
    estimated = func.coalesce(ModelUsage.estimated_tokens, 0)
    both_missing = ModelUsage.input_tokens.is_(None) & ModelUsage.output_tokens.is_(None)
    amount = func.coalesce(func.sum(case((both_missing, estimated), else_=recorded)), 0)
    with Session(engine) as session:
        total = session.execute(
            select(amount).where(ModelUsage.model_id == model_id, ModelUsage.created_at >= start)
        ).scalar_one()
    return int(total)


def usage_for_project(session: Session, project_id: UUID) -> list[UsageLine]:
    """Every model this project's calls used, with its token totals."""
    rows = session.execute(
        select(
            ModelUsage.model_id,
            func.coalesce(func.sum(ModelUsage.input_tokens), 0),
            func.coalesce(func.sum(ModelUsage.output_tokens), 0),
            func.count().filter(
                ModelUsage.input_tokens.is_(None), ModelUsage.output_tokens.is_(None)
            ),
        )
        .where(ModelUsage.project_id == project_id)
        .group_by(ModelUsage.model_id)
        .order_by(ModelUsage.model_id)
    ).all()
    return [
        UsageLine(
            model_id=model_id,
            input_tokens=int(input_total),
            output_tokens=int(output_total),
            calls_without_tokens=int(missing),
        )
        for model_id, input_total, output_total, missing in rows
    ]
