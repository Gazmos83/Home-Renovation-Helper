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
    assert seconds == pytest.approx(12 * 0.36 * 1 * 2.5)
    assert describe(seconds) == "about 11 seconds"


def test_a_final_estimate_uses_the_cycles_multiplier() -> None:
    seconds = estimate_seconds(TIERS.get("final"), 2.5, 30)
    assert seconds == pytest.approx(36 * 2.25 * 30 * 2.5)
    assert describe(seconds) == "about 101 minutes"


def test_preview_is_eevee_so_the_multiplier_does_not_apply() -> None:
    assert estimate_seconds(TIERS.get("preview"), 2.0, 99) == pytest.approx(24 * 1.0 * 1 * 2.0)


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
