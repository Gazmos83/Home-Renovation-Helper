"""render-guard: the estimate, its wording, and calibration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import make_engine
from app.render import benchmark_store as store
from app.render.estimate import (
    DEFAULT_CYCLES_MULTIPLIER,
    calibrated_multiplier,
    describe,
    estimate_seconds,
)
from app.render.tiers import load_tiers

TIERS = load_tiers()


def test_a_draft_estimate_matches_the_spec_example() -> None:
    seconds = estimate_seconds(TIERS.get("draft"), 2.5)
    assert seconds == pytest.approx(12 * 0.64 * 1 * 2.5)
    assert describe(seconds) == "about 19 seconds"


def test_a_final_estimate_uses_the_cycles_multiplier() -> None:
    seconds = estimate_seconds(TIERS.get("final"), 2.5, 30)
    assert seconds == pytest.approx(36 * 2.25 * 30 * 2.5)
    assert describe(seconds) == "about 101 minutes"


def test_draft_is_eevee_so_the_multiplier_does_not_apply() -> None:
    assert estimate_seconds(TIERS.get("draft"), 2.0, 99) == pytest.approx(12 * 0.64 * 1 * 2.0)


@pytest.mark.parametrize(
    ("seconds", "words"),
    [(0.2, "about 1 second"), (1, "about 1 second"), (11.4, "about 11 seconds"),
     (59.9, "about 1 minute"), (60, "about 1 minute"), (100, "about 2 minutes"),
     (6075, "about 101 minutes")],
)
def test_the_wording(seconds: float, words: str) -> None:
    assert describe(seconds) == words


def test_calibration_inverts_the_formula() -> None:
    final = TIERS.get("final")
    actual = estimate_seconds(final, 2.5, 18.0)
    assert calibrated_multiplier(final, actual, 2.5) == pytest.approx(18.0)


def test_calibration_refuses_nonsense() -> None:
    with pytest.raises(ValueError):
        calibrated_multiplier(TIERS.get("final"), 0, 2.5)


@pytest.fixture
def engine(migrated_database: str) -> Iterator:
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'render:%'"))
        session.commit()
    yield engine
    engine.dispose()


def test_no_benchmark_until_one_is_stored(engine) -> None:
    assert store.read_benchmark(engine) is None
    saved = store.write_benchmark(engine, 2.4, blender_version="5.2.1 LTS")
    read = store.read_benchmark(engine)
    assert read == saved and read.seconds_per_megapixel == 2.4 and read.measured_at


def test_a_new_benchmark_replaces_the_old(engine) -> None:
    store.write_benchmark(engine, 2.4)
    store.write_benchmark(engine, 3.1)
    assert store.read_benchmark(engine).seconds_per_megapixel == 3.1


def test_a_non_positive_benchmark_is_refused(engine) -> None:
    with pytest.raises(ValueError):
        store.write_benchmark(engine, 0)


def test_the_multiplier_defaults_to_30_and_can_be_stored(engine) -> None:
    assert store.read_cycles_multiplier(engine) == DEFAULT_CYCLES_MULTIPLIER == 30.0
    assert store.stored_cycles_multiplier(engine) is None
    store.write_cycles_multiplier(engine, 18.5)
    assert store.read_cycles_multiplier(engine) == 18.5
    assert store.stored_cycles_multiplier(engine) == 18.5


# --- the render server (render-offload) ----------------------------------------------------------------


def test_a_remote_final_adds_the_servers_overhead_to_its_render_time() -> None:
    from app.render.estimate import remote_estimate_seconds
    from app.render.tiers import load_tiers

    final = load_tiers().get("final")
    assert remote_estimate_seconds(final, 0.2, 40) == pytest.approx(36 * 2.25 * 0.2 + 40)
    assert remote_estimate_seconds(final, 0.2, 40, frames=1) == pytest.approx(2.25 * 0.2 + 40)


def _remote_quote(**overrides):
    from app.render.benchmark_store import Benchmark, RemoteBenchmark
    from app.render.guard import quote
    from app.render.tiers import load_tiers

    args = {
        "package_id": "desk", "version": 1, "kind": "turntable", "tier": "final", "tiers": load_tiers(),
        "benchmark": Benchmark(2.5, "t"), "target": "remote",
        "remote_benchmark": RemoteBenchmark(0.2, 40.0, "t"),
    }
    return quote(**{**args, **overrides})


def test_a_remote_final_is_priced_from_the_remote_benchmark_and_worded_for_the_server() -> None:
    priced = _remote_quote()
    assert priced.target == "remote"
    assert priced.estimate_seconds == pytest.approx(36 * 2.25 * 0.2 + 40)
    assert priced.estimate_text == "about 56 seconds"
    assert "on the render server" in priced.summary and "tier final" in priced.summary


def test_a_remote_final_needs_no_local_benchmark() -> None:
    assert _remote_quote(benchmark=None).estimate_seconds == pytest.approx(36 * 2.25 * 0.2 + 40)


def test_a_remote_final_without_a_remote_benchmark_is_refused() -> None:
    from app.render.guard import RenderRefused

    with pytest.raises(RenderRefused, match="remote benchmark must be run first") as caught:
        _remote_quote(remote_benchmark=None)
    assert caught.value.failure_class == "benchmark_missing"


def test_only_a_final_can_go_to_the_server() -> None:
    from app.render.guard import RenderRefused

    with pytest.raises(RenderRefused, match="only a final") as caught:
        _remote_quote(tier="draft")
    assert caught.value.field == "tier"


def test_an_unknown_target_is_refused_by_name() -> None:
    from app.render.guard import RenderRefused

    with pytest.raises(RenderRefused) as caught:
        _remote_quote(target="cloud")
    assert caught.value.field == "target"


def test_a_local_quote_is_unchanged_by_the_new_target() -> None:
    priced = _remote_quote(target="local")
    assert priced.target == "local" and "render server" not in priced.summary
    assert priced.estimate_seconds == pytest.approx(36 * 2.25 * 30 * 2.5)


def test_a_remote_still_is_one_frame_plus_overhead() -> None:
    assert _remote_quote(kind="still").estimate_seconds == pytest.approx(2.25 * 0.2 + 40)
