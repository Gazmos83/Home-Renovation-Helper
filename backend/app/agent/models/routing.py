"""Per-agent model routing from a configuration file (CLAUDE.md §4).

The routing file maps each of the seven agent slots to exactly one registry
slug. There is no backup or fallback slot. Loaded once at startup into a frozen
`Routing` object on `app.state`; agents read a slot by name with
`routing.model_for("designer")`.

Developer-panel overrides live in `operator_settings` under `routing:<slot>`
(design.md decision 3); the loader resolves `override ?? file`, so step 7 adds
endpoints only. Every failure — a missing slot, an unknown slug, a key the
schema does not define (including `backup`/`fallback`), a duplicate slot, or the
Reviewer routed to a text-only model — stops startup by name.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.agent.models.registry import (
    available_ids,
    is_available,
    is_known,
    supports_images,
)
from app.config import ConfigurationError
from app.db.models import OperatorSetting
from app.unique_yaml import load_unique

logger = logging.getLogger("app")

# Exactly these seven slots, in escalation/read order (CLAUDE.md §3-4).
SLOTS: Final[tuple[str, ...]] = (
    "foreman",
    "intake",
    "designer",
    "builder",
    "lighting",
    "reviewer",
    "researcher",
)

# Slots whose agent sends images and so must route to an image-capable model.
IMAGE_SLOTS: Final[frozenset[str]] = frozenset({"intake", "reviewer"})

_OVERRIDE_PREFIX: Final = "routing:"

# The default routing file shipped with the backend.
DEFAULT_ROUTING_PATH: Final = Path(__file__).resolve().parents[3] / "config" / "models.yaml"


class RoutingError(ConfigurationError):
    """The routing file or its overrides cannot produce a usable mapping."""


@dataclass(frozen=True, slots=True)
class Routing:
    """The resolved slot → slug mapping. Frozen; built by `load_routing`."""

    _slots: Mapping[str, str]

    def model_for(self, slot: str) -> str:
        try:
            return self._slots[slot]
        except KeyError:
            raise RoutingError(f"no model is routed for the slot {slot!r}") from None

    def items(self) -> list[tuple[str, str]]:
        """Each slot with its slug, in canonical slot order (startup summary)."""
        return [(slot, self._slots[slot]) for slot in SLOTS]

    def distinct_slugs(self) -> list[str]:
        """The unique routed slugs, for the startup probe."""
        return sorted({self._slots[slot] for slot in SLOTS})

    def image_slugs(self) -> set[str]:
        """The routed slugs reached from an image slot (probed with an image)."""
        return {self._slots[slot] for slot in IMAGE_SLOTS}


def read_routing_overrides(engine: Engine) -> dict[str, str]:
    """Per-slot overrides saved by the developer panel, `slot -> slug`.

    An unreadable store degrades to no overrides rather than failing startup;
    the file's routing then stands on its own.
    """
    try:
        with Session(engine) as session:
            rows = session.scalars(
                select(OperatorSetting).where(
                    OperatorSetting.key.startswith(_OVERRIDE_PREFIX)
                )
            ).all()
    except Exception as error:  # noqa: BLE001 - a startup read must not crash the app
        logger.warning(
            "routing overrides unreadable at startup",
            extra={"context": {"error_type": type(error).__name__}},
        )
        return {}
    return {row.key.removeprefix(_OVERRIDE_PREFIX): row.value for row in rows}


def write_routing_override(engine: Engine, slot: str, slug: str) -> None:
    from datetime import UTC, datetime

    key = _OVERRIDE_PREFIX + slot
    with Session(engine) as session:
        row = session.get(OperatorSetting, key)
        now = datetime.now(UTC)
        if row is None:
            session.add(OperatorSetting(key=key, value=slug, updated_at=now))
        else:
            row.value = slug
            row.updated_at = now
        session.commit()


def delete_routing_override(engine: Engine, slot: str) -> None:
    with Session(engine) as session:
        row = session.get(OperatorSetting, _OVERRIDE_PREFIX + slot)
        if row is not None:
            session.delete(row)
            session.commit()


def load_routing(
    path: Path = DEFAULT_ROUTING_PATH,
    *,
    overrides: Mapping[str, str] | None = None,
) -> Routing:
    """Build the `Routing` from the file, with `overrides` resolved over it."""
    try:
        raw = load_unique(path.read_text(encoding="utf-8"), lambda key: RoutingError(f"routing file names the slot {key!r} more than once"))
    except FileNotFoundError as error:
        raise RoutingError(f"routing file not found: {path}") from error
    except yaml.YAMLError as error:
        raise RoutingError(f"routing file is not valid YAML: {path}") from error

    if not isinstance(raw, Mapping) or not isinstance(raw.get("agents"), Mapping):
        raise RoutingError("routing file must have an 'agents' mapping of slot to slug")

    agents = dict(raw["agents"])
    for slot, slug in (overrides or {}).items():
        agents[slot] = slug

    unexpected = sorted(set(agents) - set(SLOTS))
    if unexpected:
        raise RoutingError(
            f"routing file defines unsupported key(s): {', '.join(unexpected)}; "
            f"only these slots are allowed and no backup/fallback: {', '.join(SLOTS)}"
        )

    missing = [slot for slot in SLOTS if slot not in agents]
    if missing:
        raise RoutingError(f"routing file is missing slot(s): {', '.join(missing)}")

    resolved: dict[str, str] = {}
    for slot in SLOTS:
        slug = agents[slot]
        if not isinstance(slug, str) or not is_known(slug):
            raise RoutingError(
                f"slot {slot!r} is routed to an unknown model: {slug!r}; "
                f"known models are {', '.join(available_ids())}"
            )
        if not is_available(slug):
            raise RoutingError(f"slot {slot!r} is routed to an unavailable model: {slug!r}")
        if slot in IMAGE_SLOTS and not supports_images(slug):
            raise RoutingError(
                f"slot {slot!r} needs image input but {slug!r} is text-only"
            )
        resolved[slot] = slug

    return Routing(resolved)
