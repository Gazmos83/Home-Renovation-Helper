"""Per-model token restrictions in `operator_settings` (`budget:<slug>`)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.agent.budget import DEFAULT_CONTEXT_BUDGET, DEFAULT_DAILY_CEILING
from app.agent.models.registry import BY_ID, is_known
from app.db.models import OperatorSetting

logger = logging.getLogger("app")

_PREFIX: Final = "budget:"


class InvalidBudgetSettings(ValueError):
    """A restriction is out of range. The message names the field."""


@dataclass(frozen=True, slots=True)
class TokenRestrictions:
    context_budget_tokens: int = DEFAULT_CONTEXT_BUDGET
    daily_token_ceiling: int = DEFAULT_DAILY_CEILING


DEFAULT_RESTRICTIONS: Final = TokenRestrictions()


def _write(session: Session, key: str, value: str) -> None:
    row = session.get(OperatorSetting, key)
    now = datetime.now(UTC)
    if row is None:
        session.add(OperatorSetting(key=key, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now


class Budgets:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._loaded = self._load()

    def _load(self) -> dict[str, TokenRestrictions]:
        try:
            with Session(self._engine) as session:
                rows = session.scalars(
                    select(OperatorSetting).where(OperatorSetting.key.startswith(_PREFIX))
                ).all()
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "budget settings unreadable at startup",
                extra={"context": {"error_type": type(error).__name__}},
            )
            return {}
        found: dict[str, TokenRestrictions] = {}
        for row in rows:
            slug = row.key.removeprefix(_PREFIX)
            if not is_known(slug):
                continue
            try:
                data = json.loads(row.value)
                found[slug] = TokenRestrictions(
                    context_budget_tokens=int(
                        data.get("context_budget_tokens", DEFAULT_CONTEXT_BUDGET)
                    ),
                    daily_token_ceiling=int(
                        data.get("daily_token_ceiling", DEFAULT_DAILY_CEILING)
                    ),
                )
            except (ValueError, TypeError):
                logger.warning(
                    "stored budget settings unreadable", extra={"context": {"model_id": slug}}
                )
        return found

    def for_model(self, model_id: str) -> TokenRestrictions:
        return self._loaded.get(model_id, DEFAULT_RESTRICTIONS)

    def set_budget(
        self,
        model_id: str,
        *,
        context_budget_tokens: int,
        daily_token_ceiling: int,
    ) -> TokenRestrictions:
        entry = BY_ID[model_id]
        if not 1 <= context_budget_tokens <= entry.context_window:
            raise InvalidBudgetSettings(
                f"context_budget_tokens must be between 1 and {entry.context_window}"
            )
        if daily_token_ceiling < 1:
            raise InvalidBudgetSettings("daily_token_ceiling must be at least 1")
        restrictions = TokenRestrictions(
            context_budget_tokens=context_budget_tokens,
            daily_token_ceiling=daily_token_ceiling,
        )
        value = json.dumps(
            {
                "context_budget_tokens": context_budget_tokens,
                "daily_token_ceiling": daily_token_ceiling,
            }
        )
        with Session(self._engine) as session:
            _write(session, _PREFIX + model_id, value)
            session.commit()
        self._loaded[model_id] = restrictions
        return restrictions

    def reset_budget(self, model_id: str) -> None:
        with Session(self._engine) as session:
            row = session.get(OperatorSetting, _PREFIX + model_id)
            if row is not None:
                session.delete(row)
                session.commit()
        self._loaded.pop(model_id, None)
