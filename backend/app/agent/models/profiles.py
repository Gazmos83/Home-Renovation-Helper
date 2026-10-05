"""Per-model generation profiles (llm-gateway; CLAUDE.md §4).

Each registry slug may have a saved generation profile — temperature where the
model supports it, a maximum output cap bounded by the model's own limit and an
application ceiling. A call for that slug sends the profile's values; an absent
profile sends neither temperature nor a cap, so the gateway's own defaults
apply.

Profiles live in `operator_settings` under `generation:<slug>` (design.md
decision 6), loaded once at construction and cached in process; every change
writes through so a restart picks up the same values. An unreadable store at
startup degrades to the defaults rather than failing.

The developer panel (step 7) edits these; this change ships the defaults, their
bounds and their persistence. `select_model`, prompt keys and pricing checks
from the predecessor's `operator_config` are deliberately not ported.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.agent.models.registry import BY_ID, is_known
from app.db.models import OperatorSetting

logger = logging.getLogger("app")

_GENERATION_PREFIX: Final = "generation:"

# Application bounds, applied on top of each model's own limits.
MIN_TEMPERATURE: Final = 0.0
MAX_TEMPERATURE: Final = 2.0
APPLICATION_MAX_OUTPUT_TOKENS: Final = 16_384


class InvalidGenerationSettings(ValueError):
    """A generation setting is unsupported by the model or out of bounds."""


@dataclass(frozen=True, slots=True)
class GenerationProfile:
    """One model's saved generation settings; `None` means the provider default."""

    temperature: float | None = None
    max_output_tokens: int | None = None
    updated_by: str | None = None
    updated_at: str | None = None

    def model_kwargs(self, model_id: str) -> dict[str, Any]:
        """Only the parameters the model supports, and only those that are set."""
        entry = BY_ID[model_id]
        kwargs: dict[str, Any] = {}
        if self.temperature is not None and entry.supports_temperature:
            kwargs["temperature"] = self.temperature
        if self.max_output_tokens is not None:
            kwargs["max_tokens"] = self.max_output_tokens
        return kwargs


DEFAULT_PROFILE: Final = GenerationProfile()


def output_token_limit(model_id: str) -> int:
    return min(BY_ID[model_id].max_output_tokens_limit, APPLICATION_MAX_OUTPUT_TOKENS)


def _write(session: Session, key: str, value: str) -> datetime:
    row = session.get(OperatorSetting, key)
    now = datetime.now(UTC)
    if row is None:
        session.add(OperatorSetting(key=key, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now
    return now


def _delete(session: Session, key: str) -> None:
    row = session.get(OperatorSetting, key)
    if row is not None:
        session.delete(row)


class Profiles:
    """The service's one view of per-model generation profiles."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._profiles = self._load()

    def _load(self) -> dict[str, GenerationProfile]:
        try:
            with Session(self._engine) as session:
                rows = session.scalars(
                    select(OperatorSetting).where(
                        OperatorSetting.key.startswith(_GENERATION_PREFIX)
                    )
                ).all()
        except Exception as error:  # noqa: BLE001 - a startup read must not crash the app
            logger.warning(
                "generation settings unreadable at startup",
                extra={"context": {"error_type": type(error).__name__}},
            )
            return {}
        profiles: dict[str, GenerationProfile] = {}
        for row in rows:
            model_id = row.key.removeprefix(_GENERATION_PREFIX)
            if not is_known(model_id):
                continue
            try:
                data = json.loads(row.value)
                profiles[model_id] = GenerationProfile(
                    temperature=data.get("temperature"),
                    max_output_tokens=data.get("max_output_tokens"),
                    updated_by=data.get("updated_by"),
                    updated_at=data.get("updated_at"),
                )
            except (ValueError, TypeError, AttributeError):
                logger.warning(
                    "stored generation settings unreadable",
                    extra={"context": {"model_id": model_id}},
                )
        return profiles

    def profile_for(self, model_id: str) -> GenerationProfile:
        return self._profiles.get(model_id, DEFAULT_PROFILE)

    def set_generation(
        self,
        model_id: str,
        *,
        temperature: float | None,
        max_output_tokens: int | None,
        actor: str | None,
    ) -> GenerationProfile:
        """Save one model's settings; a refused write changes nothing."""
        entry = BY_ID[model_id]
        if temperature is not None:
            if not entry.supports_temperature:
                raise InvalidGenerationSettings(
                    f"{model_id} does not support a temperature setting; "
                    "the provider default is used"
                )
            if not MIN_TEMPERATURE <= temperature <= MAX_TEMPERATURE:
                raise InvalidGenerationSettings(
                    f"temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}"
                )
        limit = output_token_limit(model_id)
        if max_output_tokens is not None and not 1 <= max_output_tokens <= limit:
            raise InvalidGenerationSettings(
                f"max output tokens must be between 1 and {limit} for {model_id}"
            )
        now = datetime.now(UTC).isoformat()
        profile = GenerationProfile(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            updated_by=actor,
            updated_at=now,
        )
        value = json.dumps(
            {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "updated_by": actor,
                "updated_at": now,
            }
        )
        with Session(self._engine) as session:
            _write(session, _GENERATION_PREFIX + model_id, value)
            session.commit()
        self._profiles[model_id] = profile
        logger.info(
            "operator changed generation settings",
            extra={
                "context": {
                    "event": "generation_settings_updated",
                    "model_id": model_id,
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens,
                }
            },
        )
        return profile

    def reset_generation(self, model_id: str) -> None:
        """Return one model to its provider defaults."""
        with Session(self._engine) as session:
            _delete(session, _GENERATION_PREFIX + model_id)
            session.commit()
        self._profiles.pop(model_id, None)
        logger.info(
            "operator reset generation settings",
            extra={"context": {"event": "generation_settings_reset", "model_id": model_id}},
        )
