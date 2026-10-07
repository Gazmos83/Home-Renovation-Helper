"""render-guard: tier, estimate and actual are recorded; tracing never matters."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.config import Settings
from app.observability.langfuse import Tracing
from app.render.benchmark_store import Benchmark
from app.render.guard import authorise
from app.render.records import log_render_finished, log_render_started
from app.render.tiers import load_tiers


def _quote():
    return authorise(
        package_id="desk", version=2, kind="turntable", tier="draft",
        tiers=load_tiers(), benchmark=Benchmark(2.5, "t"),
    ).quote


def _settings() -> Settings:
    return Settings(
        database_url="postgresql://u:p@localhost:5432/d",
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email="owner@example.com",
        owner_password="an-initial-owner-password",
        langfuse_host="https://langfuse.invalid",
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        _env_file=None,
    )


class FakeClient:
    def __init__(self, *, raises: bool = False) -> None:
        self.events: list[dict[str, Any]] = []
        self._raises = raises

    def create_event(self, **kwargs: Any) -> None:
        if self._raises:
            raise ConnectionError("langfuse unreachable")
        self.events.append(kwargs)

    def flush(self) -> None: ...


def _tracing(client: FakeClient) -> Tracing:
    return Tracing(_settings(), handler_factory=lambda _s: (client, object()))


def test_the_start_and_finish_records_carry_the_required_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    quote = _quote()
    with caplog.at_level(logging.INFO, logger="app"):
        log_render_started(quote)
        log_render_finished(quote, actual_seconds=9.5, outcome="succeeded")
    started, finished = (r.context for r in caplog.records if r.message.startswith("render."))
    for record in (started, finished):
        assert record["package_id"] == "desk" and record["version"] == 2
        assert record["tier"] == "draft" and record["frames"] == 12
        assert record["resolution"] == 600 and record["engine"] == "eevee"
        assert record["estimate_seconds"] == pytest.approx(10.8)
    assert "actual_seconds" not in started
    assert finished["actual_seconds"] == 9.5 and finished["outcome"] == "succeeded"


def test_a_failure_is_recorded_with_its_reason(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app"):
        log_render_finished(_quote(), actual_seconds=1, outcome="failed", error="boom")
    [record] = [r for r in caplog.records if r.message == "render.finished"]
    assert record.context["outcome"] == "failed" and record.context["error"] == "boom"


def test_tracing_receives_the_same_values_as_an_event() -> None:
    client = FakeClient()
    tracing = _tracing(client)
    log_render_started(_quote(), tracing=tracing)
    log_render_finished(_quote(), actual_seconds=3, outcome="succeeded", tracing=tracing)
    started, finished = (e["metadata"] for e in client.events)
    assert started["event"] == "started" and started["tier"] == "draft"
    assert finished["event"] == "finished" and finished["actual_seconds"] == 3
    assert all(e["name"] == "render" for e in client.events)


def test_tracing_off_sends_nothing_and_logs_normally(caplog: pytest.LogCaptureFixture) -> None:
    off = Tracing(Settings(
        database_url="postgresql://u:p@localhost:5432/d", openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173", owner_email="owner@example.com",
        owner_password="an-initial-owner-password", _env_file=None,
    ))
    with caplog.at_level(logging.INFO, logger="app"):
        log_render_started(_quote(), tracing=off)
    assert [r for r in caplog.records if r.message == "render.started"]


def test_a_failing_tracing_client_is_logged_once_and_never_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracing = _tracing(FakeClient(raises=True))
    with caplog.at_level(logging.WARNING, logger="app"):
        for _ in range(3):
            log_render_started(_quote(), tracing=tracing)
    warnings = [r for r in caplog.records if "could not record a render event" in r.message]
    assert len(warnings) == 1
    assert "sk-lf-test" not in repr(warnings[0].context)


# --- where it ran (render-offload) -------------------------------------------------------------------------------


def _final_quote(target: str):
    from app.render.benchmark_store import RemoteBenchmark

    return authorise(
        package_id="desk", version=2, kind="turntable", tier="final", tiers=load_tiers(),
        benchmark=Benchmark(2.5, "t"), approval="yes", target=target,
        remote_benchmark=RemoteBenchmark(0.2, 40.0, "t"),
    ).quote


def test_a_local_draft_names_its_target(caplog: pytest.LogCaptureFixture) -> None:
    quote = _quote()
    with caplog.at_level(logging.INFO, logger="app"):
        log_render_started(quote)
        log_render_finished(quote, actual_seconds=9.5, outcome="succeeded")
    started, finished = (r.context for r in caplog.records if r.message.startswith("render."))
    assert started["target"] == "local" and finished["target"] == "local"
    assert "transfer_seconds" not in finished


def test_a_remote_final_names_its_target_and_the_transfer_seconds(caplog: pytest.LogCaptureFixture) -> None:
    quote = _final_quote("remote")
    with caplog.at_level(logging.INFO, logger="app"):
        log_render_started(quote)
        log_render_finished(quote, actual_seconds=70.0, outcome="succeeded", transfer_seconds=12.3456)
    started, finished = (r.context for r in caplog.records if r.message.startswith("render."))
    assert started["target"] == "remote" and started["tier"] == "final"
    assert started["estimate_seconds"] == pytest.approx(36 * 2.25 * 0.2 + 40)
    assert finished["target"] == "remote" and finished["actual_seconds"] == 70.0
    assert finished["transfer_seconds"] == 12.346


def test_tracing_receives_the_target_and_transfer() -> None:
    client = FakeClient()
    quote = _final_quote("remote")
    log_render_finished(quote, actual_seconds=70.0, outcome="succeeded", transfer_seconds=5.0, tracing=_tracing(client))
    [event] = client.events
    assert event["metadata"]["target"] == "remote" and event["metadata"]["transfer_seconds"] == 5.0
