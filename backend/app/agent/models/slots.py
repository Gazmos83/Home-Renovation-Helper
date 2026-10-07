"""One chat model per agent slot, built once (agent-loop design decision 3).

A slot's model comes from routing and its generation profile; nothing here picks
a model, and there is no fallback. The graph asks for a slot by name through
`model_provider`, so a test passes a fake per slot instead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from app.agent.models.openrouter_client import build_chat_model
from app.agent.models.profiles import Profiles
from app.agent.models.routing import Routing
from app.config import Settings

LOOP_SLOTS: Final[tuple[str, ...]] = (
    "foreman", "intake", "designer", "builder", "lighting", "reviewer", "researcher",
)

ModelProvider = Callable[[str], Any]


def build_slot_models(
    settings: Settings, routing: Routing, profiles: Profiles
) -> dict[str, Any]:
    """The chat model for each loop slot, with its profile's parameters."""
    models: dict[str, Any] = {}
    for slot in LOOP_SLOTS:
        slug = routing.model_for(slot)
        models[slot] = build_chat_model(
            settings, model_id=slug, **profiles.profile_for(slug).model_kwargs(slug)
        )
    return models


def model_provider(models: dict[str, Any]) -> ModelProvider:
    def provide(slot: str) -> Any:
        try:
            return models[slot]
        except KeyError:
            raise KeyError(f"no model is built for the slot {slot!r}") from None

    return provide
