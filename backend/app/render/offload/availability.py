"""How often a render GPU was available (render-gpu-availability design decisions 3 and 5).

`StockSampler` reads RunPod's live pod stock for the configured GPU types in the network
volume's data centre every 15 minutes and stores one row per type, all with the same
time. It only reads: nothing is created or billed. Rows older than 90 days are removed
at each sample. A failed read stores nothing and the next interval tries again.

`history` turns the pod sessions and the samples into the developer panel's figures.
"""

from __future__ import annotations

import asyncio
import logging
import statistics
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.db.models import GpuStockSample, RenderPodSession
from app.render import benchmark_store
from app.render.offload.runpod import RunPodClient, RunPodError

logger = logging.getLogger("app")

SAMPLE_SECONDS: Final = 900.0
KEEP_DAYS: Final = 90
VOLUME_CACHE_SECONDS: Final = 3600.0
PERIODS: Final = (7, 30)


def _now() -> datetime:
    return datetime.now(UTC)


class StockSampler:
    def __init__(
        self,
        *,
        client: RunPodClient,
        gpu_types: Sequence[str],
        volume_id: str,
        engine: Engine,
        now: Callable[[], datetime] = _now,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self.client = client
        self.gpu_types = tuple(gpu_types)
        self.volume_id = volume_id
        self.engine = engine
        self._now = now
        self._sleep = sleep
        self._data_center: str | None = None
        self._data_center_read_at: datetime | None = None
        self._task: asyncio.Task | None = None

    async def _volume_data_center(self) -> str:
        now = self._now()
        fresh = self._data_center_read_at and (now - self._data_center_read_at).total_seconds() < VOLUME_CACHE_SECONDS
        if self._data_center is None or not fresh:
            volume = await self.client.get_network_volume(self.volume_id)
            self._data_center, self._data_center_read_at = volume.data_center_id, now
        return self._data_center

    async def sample_once(self) -> int:
        """Store one sample when sampling is on; the number of rows stored."""
        if not benchmark_store.read_stock_sampling(self.engine):
            return 0
        try:
            data_center = await self._volume_data_center()
            levels = await self.client.gpu_stock(self.gpu_types, data_center)
        except RunPodError as error:
            logger.warning("offload.stock_sample_failed", extra={"context": {"reason": error.reason}})
            return 0
        taken_at = self._now()
        with Session(self.engine) as session:
            for gpu_type, level in levels.items():
                session.add(
                    GpuStockSample(taken_at=taken_at, data_center=data_center, gpu_type=gpu_type, availability=level)
                )
            session.execute(
                delete(GpuStockSample).where(GpuStockSample.taken_at < taken_at - timedelta(days=KEEP_DAYS))
            )
            session.commit()
        return len(levels)

    async def run(self) -> None:
        while True:
            try:
                await self.sample_once()
            except Exception as error:  # noqa: BLE001 - the sampler must outlive any one failure
                logger.warning("offload.stock_sampler_error", extra={"context": {"error_type": type(error).__name__}})
            await self._sleep(SAMPLE_SECONDS)

    def start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def history(session: Session, days: int, *, now: datetime | None = None) -> dict[str, Any]:
    """The panel's figures for the last `days` days (design decision 5)."""
    since = (now or _now()) - timedelta(days=days)
    starts = session.scalars(
        select(RenderPodSession).where(
            RenderPodSession.created_at >= since, RenderPodSession.outcome != "orphaned"
        )
    ).all()
    started = [row for row in starts if row.ready_at is not None]
    samples = session.scalars(select(GpuStockSample).where(GpuStockSample.taken_at >= since)).all()
    by_time: dict[datetime, list[GpuStockSample]] = defaultdict(list)
    for row in samples:
        by_time[row.taken_at].append(row)
    per_type: dict[str, list[bool]] = defaultdict(list)
    for row in samples:
        per_type[row.gpu_type].append(row.availability != "NONE")
    any_in_stock = sum(1 for rows in by_time.values() if any(r.availability != "NONE" for r in rows))
    return {
        "starts": len(starts),
        "started_share": _share(len(started), len(starts)),
        "median_startup_seconds": (
            round(statistics.median((r.ready_at - r.created_at).total_seconds() for r in started))
            if started
            else None
        ),
        "placed": dict(Counter(row.gpu_type for row in started)),
        "failed_starts": sum(1 for row in starts if row.outcome == "start_failed"),
        "samples": len(by_time),
        "any_in_stock_share": _share(any_in_stock, len(by_time)),
        "per_type_share": {gpu: _share(sum(flags), len(flags)) for gpu, flags in sorted(per_type.items())},
        "last_sample_at": max(by_time).astimezone(UTC).isoformat() if by_time else None,
    }
