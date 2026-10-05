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


@dataclass(frozen=True, slots=True)
class Benchmark:
    seconds_per_megapixel: float
    measured_at: str
    blender_version: str | None = None


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
