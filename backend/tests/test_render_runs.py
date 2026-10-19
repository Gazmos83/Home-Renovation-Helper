"""feedback-capture: every guarded render records where it came from."""

from __future__ import annotations

import time
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import RenderRun
from app.feedback import runs as feedback_runs
from app.render.benchmark_store import Benchmark
from app.render.guard import authorise
from app.render.tiers import load_tiers
from tests.blender_fakes import fake_failure_launch
from tests.test_builder_tools import wait_job
from tests.test_renders_api import (  # noqa: F401 - fixtures
    BASE,
    client,
    launched,
    render,
)


def runs_of(engine) -> list[RenderRun]:
    with Session(engine) as session:
        return list(session.scalars(select(RenderRun).order_by(RenderRun.started_at)))


def wait_for_outcome(engine, wanted: str, seconds: float = 10.0) -> RenderRun:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = [run for run in runs_of(engine) if run.outcome == wanted]
        if found:
            return found[-1]
        time.sleep(0.05)
    raise AssertionError(f"no render run reached {wanted!r}; have {[r.outcome for r in runs_of(engine)]}")


def agent_ctx(make_ctx, **fields):
    return make_ctx(
        package_id="bench",
        thread_id=uuid4(),
        last_message="show me it from all sides",
        trace_id="trace-123",
        slot="builder",
        model="deepseek/deepseek-v4-pro-0813",
        **fields,
    )


def test_an_agent_started_render_records_thread_trace_prompt_slot_and_model(make_ctx, tool_state) -> None:
    """The Builder renders rooms only (rooms-only-renders); a piece run started by an agent (the
    Lighting detail pass) records its origin from the tool context."""
    ticket = authorise(
        package_id="bench", version=1, kind="turntable", tier="draft", tiers=load_tiers(),
        benchmark=Benchmark(2.5, "t"),
    )
    ctx = agent_ctx(make_ctx)
    run_id = feedback_runs.record_run(tool_state.engine, ticket.quote, feedback_runs.origin_from(ctx))
    feedback_runs.finish_run(tool_state.engine, run_id, "succeeded")
    [run] = runs_of(tool_state.engine)
    assert (run.package_id, run.version, run.render_key, run.tier) == ("bench", 1, "turntable", "draft")
    assert run.thread_id == ctx.thread_id and run.trace_id == "trace-123"
    assert run.prompt == "show me it from all sides"
    assert (run.slot, run.model) == ("builder", "deepseek/deepseek-v4-pro-0813")
    assert run.outcome == "succeeded" and run.finished_at is not None


def test_a_render_started_over_http_records_no_origin(client, launched) -> None:  # noqa: F811
    with Session(client.app.state.engine) as session:
        session.execute(delete(RenderRun))
        session.commit()
    assert render(client, kind="still", tier="draft").status_code == 202
    [run] = runs_of(client.app.state.engine)
    assert (run.package_id, run.version, run.render_key, run.tier) == ("hall-bench", 1, "still", "draft")
    assert run.outcome == "succeeded" and run.finished_at is not None
    assert (run.thread_id, run.trace_id, run.prompt, run.slot, run.model) == (None,) * 5


def test_a_failed_render_is_recorded_as_failed(client, launched) -> None:  # noqa: F811
    with Session(client.app.state.engine) as session:
        session.execute(delete(RenderRun))
        session.commit()
    client.app.state.blender_launch = fake_failure_launch
    assert render(client, kind="turntable", tier="draft").status_code == 202
    run = wait_for_outcome(client.app.state.engine, "failed")
    assert run.render_key == "turntable" and run.finished_at is not None


def test_a_database_failure_does_not_stop_the_render(client, launched, render_root, monkeypatch) -> None:  # noqa: F811
    with Session(client.app.state.engine) as session:
        session.execute(delete(RenderRun))
        session.commit()

    def broken(*_args, **_kwargs):
        raise ConnectionError("database down")

    monkeypatch.setattr(feedback_runs, "Session", broken)
    assert render(client, kind="turntable", tier="draft").status_code == 202
    wait_job(render_root / "hall-bench" / "v1", "turntable")
    monkeypatch.undo()
    assert runs_of(client.app.state.engine) == []


def test_a_shell_render_is_not_recorded(tool_state) -> None:
    ticket = authorise(
        package_id="flat", version=1, kind="still", tier="draft", tiers=load_tiers(),
        benchmark=Benchmark(2.5, "t"), record="shell",
    )
    assert feedback_runs.record_run(tool_state.engine, ticket.quote) is None
    assert runs_of(tool_state.engine) == []


def test_a_long_prompt_is_cut_to_two_thousand_characters(make_ctx, tool_state) -> None:
    ticket = authorise(
        package_id="bench", version=1, kind="still", tier="draft", tiers=load_tiers(),
        benchmark=Benchmark(2.5, "t"),
    )
    ctx = replace(agent_ctx(make_ctx), last_message="x" * 5000)
    run_id = feedback_runs.record_run(tool_state.engine, ticket.quote, feedback_runs.origin_from(ctx))
    assert run_id is not None
    [run] = runs_of(tool_state.engine)
    assert len(run.prompt) == 2000


def test_finishing_an_unknown_or_missing_run_never_raises(tool_state) -> None:
    feedback_runs.finish_run(tool_state.engine, None, "succeeded")
    feedback_runs.finish_run(tool_state.engine, uuid4(), "failed")


@pytest.mark.parametrize("key", ["still", "turntable"])
def test_the_latest_succeeded_run_is_the_one_the_owner_sees(client, launched, render_root, key) -> None:  # noqa: F811
    with Session(client.app.state.engine) as session:
        session.execute(delete(RenderRun))
        session.commit()
    for _ in range(2):
        assert render(client, kind=key, tier="draft").status_code == 202
        wait_job(render_root / "hall-bench" / "v1", key)
        time.sleep(0.2)
    engine = client.app.state.engine
    runs = [r for r in runs_of(engine) if r.outcome == "succeeded"]
    assert len(runs) == 2
    with Session(engine) as session:
        latest = feedback_runs.latest_succeeded_run(session, "hall-bench", 1, key)
        assert latest is not None and latest.id == max(runs, key=lambda r: r.started_at).id
        assert feedback_runs.latest_succeeded_run(session, "hall-bench", 1, "room-still") is None
