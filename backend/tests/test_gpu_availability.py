"""render-gpu-availability: the stock sampler and the availability history."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import GpuStockSample, RenderPodSession
from app.db.session import make_engine
from app.render import benchmark_store as store
from app.render.offload.availability import StockSampler, history
from app.render.offload.runpod import RunPodClient
from tests.offload_fakes import FakeRunPod

NOW = datetime(2026, 10, 15, 16, 0, tzinfo=UTC)
A4500, R4090 = "NVIDIA RTX A4500", "NVIDIA GeForce RTX 4090"


@pytest.fixture
def engine(migrated_database: str) -> Iterator:
    engine = make_engine(migrated_database)

    def clear() -> None:
        with Session(engine) as session:
            session.execute(text("DELETE FROM gpu_stock_samples"))
            session.execute(text("DELETE FROM render_pod_sessions"))
            session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'offload:%'"))
            session.commit()

    clear()
    yield engine
    clear()
    engine.dispose()


def sampler(fake: FakeRunPod, engine, now=NOW) -> StockSampler:
    return StockSampler(
        client=RunPodClient(SecretStr("rpa_SECRETKEYVALUE"), transport=fake.transport),
        gpu_types=(A4500, R4090), volume_id="vol123", engine=engine, now=lambda: now,
    )


def rows(engine) -> list[tuple[str, str, str]]:
    with Session(engine) as session:
        return sorted(
            (r.data_center, r.gpu_type, r.availability) for r in session.scalars(select(GpuStockSample))
        )


# --- sampling ----------------------------------------------------------------------------------------------


def test_a_sample_stores_one_row_per_type_with_none_for_unlisted(engine) -> None:
    fake = FakeRunPod(catalog={R4090: {"EU-RO-1": "LOW"}})
    assert asyncio.run(sampler(fake, engine).sample_once()) == 2
    assert rows(engine) == [("EU-RO-1", R4090, "LOW"), ("EU-RO-1", A4500, "NONE")]
    assert fake.created == [] and fake.deleted == []  # a sample only reads


def test_sampling_is_on_by_default_and_off_stores_nothing(engine) -> None:
    assert store.read_stock_sampling(engine) is True
    store.write_stock_sampling(engine, False)
    fake = FakeRunPod(catalog={R4090: {"EU-RO-1": "LOW"}})
    assert asyncio.run(sampler(fake, engine).sample_once()) == 0
    assert rows(engine) == [] and fake.requests == []


def test_a_failed_read_stores_nothing_and_the_next_interval_samples(engine) -> None:
    fake = FakeRunPod(catalog={R4090: {"EU-RO-1": "LOW"}}, catalog_status=500)
    taker = sampler(fake, engine)
    assert asyncio.run(taker.sample_once()) == 0 and rows(engine) == []
    fake.catalog_status = 200
    assert asyncio.run(taker.sample_once()) == 2


def test_rows_older_than_90_days_are_removed(engine) -> None:
    with Session(engine) as session:
        session.add(GpuStockSample(taken_at=NOW - timedelta(days=91), data_center="EU-RO-1", gpu_type=A4500, availability="LOW"))
        session.add(GpuStockSample(taken_at=NOW - timedelta(days=89), data_center="EU-RO-1", gpu_type=A4500, availability="LOW"))
        session.commit()
    asyncio.run(sampler(FakeRunPod(catalog={}), engine).sample_once())
    with Session(engine) as session:
        ages = sorted((NOW - r.taken_at).days for r in session.scalars(select(GpuStockSample)))
    assert ages == [0, 0, 89]


def test_the_loop_samples_every_15_minutes_and_survives_a_failure(engine) -> None:
    slept: list[float] = []
    fake = FakeRunPod(catalog={R4090: {"EU-RO-1": "LOW"}}, catalog_status=500)

    async def scenario():
        taker = sampler(fake, engine)

        async def sleep(seconds: float) -> None:
            slept.append(seconds)
            fake.catalog_status = 200
            if len(slept) == 2:
                raise asyncio.CancelledError

        taker._sleep = sleep
        with pytest.raises(asyncio.CancelledError):
            await taker.run()

    asyncio.run(scenario())
    assert slept == [900.0, 900.0] and len(rows(engine)) == 2


# --- history ------------------------------------------------------------------------------------------------


def add_session(engine, *, minutes_ago: int, startup: int | None, outcome: str, gpu: str = A4500) -> None:
    created = NOW - timedelta(minutes=minutes_ago)
    with Session(engine) as session:
        session.add(RenderPodSession(
            pod_id=f"p{minutes_ago}", gpu_type=gpu, created_at=created, outcome=outcome,
            ready_at=created + timedelta(seconds=startup) if startup is not None else None,
        ))
        session.commit()


def test_start_history_counts_starts_share_median_and_failures(engine) -> None:
    add_session(engine, minutes_ago=10, startup=60, outcome="deleted_idle")
    add_session(engine, minutes_ago=20, startup=90, outcome="deleted_idle", gpu=R4090)
    add_session(engine, minutes_ago=30, startup=150, outcome="deleted_shutdown")
    add_session(engine, minutes_ago=40, startup=None, outcome="start_failed")
    add_session(engine, minutes_ago=50, startup=None, outcome="orphaned")  # not this run's start
    add_session(engine, minutes_ago=60 * 24 * 8, startup=30, outcome="deleted_idle")  # outside 7 days
    with Session(engine) as session:
        week = history(session, 7, now=NOW)
        month = history(session, 30, now=NOW)
    assert (week["starts"], week["started_share"], week["median_startup_seconds"], week["failed_starts"]) == (4, 0.75, 90, 1)
    assert week["placed"] == {A4500: 2, R4090: 1}
    assert month["starts"] == 5


def test_stock_history_counts_sample_times_with_any_gpu_in_stock(engine) -> None:
    with Session(engine) as session:
        for i in range(100):
            taken = NOW - timedelta(minutes=15 * i)
            session.add(GpuStockSample(taken_at=taken, data_center="EU-RO-1", gpu_type=A4500,
                                       availability="LOW" if i < 50 else "NONE"))
            session.add(GpuStockSample(taken_at=taken, data_center="EU-RO-1", gpu_type=R4090,
                                       availability="LOW" if 38 <= i < 62 else "NONE"))
        session.commit()
        week = history(session, 7, now=NOW)
    assert week["samples"] == 100 and week["any_in_stock_share"] == 0.62
    assert week["per_type_share"] == {R4090: 0.24, A4500: 0.5}
    assert week["last_sample_at"] == NOW.isoformat()


def test_nothing_recorded_yet_reads_as_none(engine) -> None:
    with Session(engine) as session:
        week = history(session, 7, now=NOW)
    assert week["starts"] == 0 and week["started_share"] is None and week["median_startup_seconds"] is None
    assert week["samples"] == 0 and week["any_in_stock_share"] is None and week["last_sample_at"] is None
