"""llm-gateway: every gateway call is recorded with its tokens, owner-only.

No network here: `LLMResult` is built by hand in each of the two shapes a real
provider can return, exactly as `_token_counts` must tell apart.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.accounts import ensure_owner
from app.db.models import ModelUsage
from app.db.session import make_engine
from app.observability import usage
from app.observability.usage import UsageRecorder, operation
from conftest import OWNER_PASSWORD, UNREACHABLE_DSN


def _result_with_usage_metadata(input_tokens: int, output_tokens: int) -> LLMResult:
    message = AIMessage(
        content="hi",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    )
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def _result_with_token_usage_fallback(prompt: int, completion: int) -> LLMResult:
    message = AIMessage(content="hi")
    return LLMResult(
        generations=[[ChatGeneration(message=message)]],
        llm_output={"token_usage": {"prompt_tokens": prompt, "completion_tokens": completion}},
    )


def _result_with_no_usage() -> LLMResult:
    return LLMResult(generations=[[ChatGeneration(message=AIMessage(content="hi"))]])


@pytest.fixture
def domain(db_session: Session) -> Session:
    db_session.execute(text("TRUNCATE TABLE model_usage, users CASCADE"))
    db_session.commit()
    return db_session


def _owner(domain: Session):
    record = ensure_owner(domain, "owner@example.com", OWNER_PASSWORD)
    domain.commit()
    return record.id


def test_usage_metadata_is_recorded(domain: Session) -> None:
    owner_id = _owner(domain)
    recorder = UsageRecorder(
        domain.get_bind(), model_id="openai/gpt-5.6-luna", owner_user_id=owner_id  # type: ignore[arg-type]
    )
    with operation("probe_foreman"):
        recorder.on_llm_end(_result_with_usage_metadata(12, 34), run_id=uuid4())

    row = domain.execute(select(ModelUsage)).scalar_one()
    assert row.model_id == "openai/gpt-5.6-luna"
    assert row.operation == "probe_foreman"
    assert row.input_tokens == 12
    assert row.output_tokens == 34
    assert row.user_id == owner_id
    assert row.trace_id is None


def test_the_turns_trace_is_stored_with_the_call(domain: Session) -> None:
    owner_id = _owner(domain)
    recorder = UsageRecorder(
        domain.get_bind(),  # type: ignore[arg-type]
        model_id="openai/gpt-5.6-luna",
        owner_user_id=owner_id,
        trace_id="0d7d2fdc6b9f9e5d655420d4ca531ac4",
    )
    recorder.on_llm_end(_result_with_usage_metadata(5, 6), run_id=uuid4())
    row = domain.execute(select(ModelUsage)).scalar_one()
    assert row.trace_id == "0d7d2fdc6b9f9e5d655420d4ca531ac4"


def test_token_usage_fallback_is_recorded(domain: Session) -> None:
    owner_id = _owner(domain)
    recorder = UsageRecorder(
        domain.get_bind(), model_id="openai/gpt-5.6-luna", owner_user_id=owner_id  # type: ignore[arg-type]
    )
    with operation("draft_response"):
        recorder.on_llm_end(_result_with_token_usage_fallback(7, 3), run_id=uuid4())
    row = domain.execute(select(ModelUsage)).scalar_one()
    assert row.input_tokens == 7
    assert row.output_tokens == 3


def test_no_usage_at_all_is_recorded_as_null_not_zero(domain: Session) -> None:
    owner_id = _owner(domain)
    recorder = UsageRecorder(
        domain.get_bind(), model_id="openai/gpt-5.6-luna", owner_user_id=owner_id  # type: ignore[arg-type]
    )
    recorder.on_llm_end(_result_with_no_usage(), run_id=uuid4())
    row = domain.execute(select(ModelUsage)).scalar_one()
    assert row.input_tokens is None
    assert row.output_tokens is None
    assert row.operation == usage.UNKNOWN_OPERATION


def test_a_storage_failure_is_one_warning_and_never_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = make_engine(UNREACHABLE_DSN, connect_args={"connect_timeout": 1})
    recorder = UsageRecorder(engine, model_id="x/y", owner_user_id=uuid4())
    with caplog.at_level(logging.WARNING, logger="app"):
        recorder.on_llm_end(_result_with_usage_metadata(1, 1), run_id=uuid4())
    assert [r for r in caplog.records if "usage.unrecorded" in r.message]
    engine.dispose()
