"""The stored benchmark and Cycles multiplier (render-guard design decision 3).

Both live in `operator_settings`: `render:benchmark` (JSON) and
`render:cycles_multiplier`. Absent multiplier means the default of 30. No
migration: the table is generic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.models import OperatorSetting
from app.render.estimate import DEFAULT_CYCLES_MULTIPLIER

BENCHMARK_KEY: Final = "render:benchmark"
MULTIPLIER_KEY: Final = "render:cycles_multiplier"
# render-offload: the render server's own numbers and the developer's choices.
REMOTE_BENCHMARK_KEY: Final = "offload:benchmark"
TARGET_KEY: Final = "offload:final_target"
HOURLY_RATE_KEY: Final = "offload:hourly_rate_eur"
TARGETS: Final = ("local", "remote")


@dataclass(frozen=True, slots=True)
class Benchmark:
    seconds_per_megapixel: float
    measured_at: str
    blender_version: str | None = None


@dataclass(frozen=True, slots=True)
class RemoteBenchmark:
    """Seconds per megapixel of a Cycles frame on the render server, plus the fixed
    time a job spends not rendering (upload, start-up, download)."""

    seconds_per_megapixel: float
    overhead_seconds: float
    measured_at: str
    calibrated: bool = False


def _put(session: Session, key: str, value: str) -> None:
    row = session.get(OperatorSetting, key)
    now = datetime.now(UTC)
    if row is None:
        session.add(OperatorSetting(key=key, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now


def read_benchmark(engine: Engine) -> Benchmark | None:
    with Session(engine) as session:
        row = session.get(OperatorSetting, BENCHMARK_KEY)
        if row is None:
            return None
        try:
            data = json.loads(row.value)
            seconds = float(data["seconds_per_megapixel"])
        except (ValueError, KeyError, TypeError):
            return None
        if seconds <= 0:
            return None
        return Benchmark(seconds, str(data.get("measured_at", "")), data.get("blender_version"))


def write_benchmark(
    engine: Engine, seconds_per_megapixel: float, *, blender_version: str | None = None
) -> Benchmark:
    if seconds_per_megapixel <= 0:
        raise ValueError("the benchmark must be a positive number of seconds per megapixel")
    measured_at = datetime.now(UTC).isoformat()
    with Session(engine) as session:
        _put(
            session,
            BENCHMARK_KEY,
            json.dumps(
                {
                    "seconds_per_megapixel": seconds_per_megapixel,
                    "measured_at": measured_at,
                    "blender_version": blender_version,
                }
            ),
        )
        session.commit()
    return Benchmark(seconds_per_megapixel, measured_at, blender_version)


def read_cycles_multiplier(engine: Engine) -> float:
    return stored_cycles_multiplier(engine) or DEFAULT_CYCLES_MULTIPLIER


def stored_cycles_multiplier(engine: Engine) -> float | None:
    """The calibrated multiplier, or `None` while it is still the default."""
    with Session(engine) as session:
        row = session.get(OperatorSetting, MULTIPLIER_KEY)
        if row is None:
            return None
        try:
            value = float(row.value)
        except ValueError:
            return None
        return value if value > 0 else None


def write_cycles_multiplier(engine: Engine, multiplier: float) -> None:
    if multiplier <= 0:
        raise ValueError("the Cycles multiplier must be positive")
    with Session(engine) as session:
        _put(session, MULTIPLIER_KEY, repr(float(multiplier)))
        session.commit()


def read_remote_benchmark(engine: Engine) -> RemoteBenchmark | None:
    with Session(engine) as session:
        row = session.get(OperatorSetting, REMOTE_BENCHMARK_KEY)
        if row is None:
            return None
        try:
            data = json.loads(row.value)
            seconds = float(data["seconds_per_megapixel"])
            overhead = float(data["overhead_seconds"])
        except (ValueError, KeyError, TypeError):
            return None
        if seconds <= 0 or overhead < 0:
            return None
        return RemoteBenchmark(
            seconds, overhead, str(data.get("measured_at", "")), bool(data.get("calibrated", False))
        )


def write_remote_benchmark(
    engine: Engine,
    seconds_per_megapixel: float,
    overhead_seconds: float,
    *,
    calibrated: bool = False,
    measured_at: str | None = None,
) -> RemoteBenchmark:
    if seconds_per_megapixel <= 0 or overhead_seconds < 0:
        raise ValueError("the remote benchmark needs positive seconds per megapixel and a non-negative overhead")
    stamp = measured_at or datetime.now(UTC).isoformat()
    with Session(engine) as session:
        _put(
            session,
            REMOTE_BENCHMARK_KEY,
            json.dumps(
                {
                    "seconds_per_megapixel": seconds_per_megapixel,
                    "overhead_seconds": overhead_seconds,
                    "measured_at": stamp,
                    "calibrated": calibrated,
                }
            ),
        )
        session.commit()
    return RemoteBenchmark(seconds_per_megapixel, overhead_seconds, stamp, calibrated)


def read_final_target(engine: Engine) -> str:
    """Where `final` renders run: `local` unless the developer chose `remote`."""
    with Session(engine) as session:
        row = session.get(OperatorSetting, TARGET_KEY)
    return row.value if row is not None and row.value in TARGETS else "local"


def write_final_target(engine: Engine, target: str) -> None:
    if target not in TARGETS:
        raise ValueError(f"the final target must be one of {', '.join(TARGETS)}")
    with Session(engine) as session:
        _put(session, TARGET_KEY, target)
        session.commit()


def read_hourly_rate(engine: Engine) -> float | None:
    with Session(engine) as session:
        row = session.get(OperatorSetting, HOURLY_RATE_KEY)
    if row is None:
        return None
    try:
        value = float(row.value)
    except ValueError:
        return None
    return value if value >= 0 else None


def write_hourly_rate(engine: Engine, euros: float) -> None:
    if euros < 0:
        raise ValueError("the hourly rate must not be negative")
    with Session(engine) as session:
        _put(session, HOURLY_RATE_KEY, repr(float(euros)))
        session.commit()
