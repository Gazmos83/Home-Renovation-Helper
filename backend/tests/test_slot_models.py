"""llm-gateway / design-agents: each loop slot gets its routed model and profile."""

from __future__ import annotations

from app.agent.models.profiles import GenerationProfile
from app.agent.models.routing import load_routing
from app.agent.models.slots import LOOP_SLOTS, build_slot_models, model_provider
from app.config import Settings


class StubProfiles:
    def __init__(self, profiles: dict[str, GenerationProfile] | None = None) -> None:
        self._profiles = profiles or {}

    def profile_for(self, model_id: str) -> GenerationProfile:
        return self._profiles.get(model_id, GenerationProfile())


def test_each_slot_gets_its_routed_slug(settings: Settings) -> None:
    routing = load_routing()
    models = build_slot_models(settings, routing, StubProfiles())
    assert set(models) == set(LOOP_SLOTS)
    for slot in LOOP_SLOTS:
        assert models[slot].model_name == routing.model_for(slot)


def test_a_stored_profiles_temperature_reaches_the_client(settings: Settings) -> None:
    routing = load_routing()
    designer = routing.model_for("designer")
    profiles = StubProfiles({designer: GenerationProfile(temperature=0.3, max_output_tokens=777)})
    models = build_slot_models(settings, routing, profiles)
    assert models["designer"].temperature == 0.3
    assert models["designer"].max_tokens == 777
    assert models["intake"].temperature is None


def test_the_provider_returns_the_slots_model_and_refuses_an_unknown_slot(settings: Settings) -> None:
    models = build_slot_models(settings, load_routing(), StubProfiles())
    provide = model_provider(models)
    assert provide("builder") is models["builder"]
    try:
        provide("lighting")
    except KeyError as error:
        assert "lighting" in str(error)
    else:  # pragma: no cover
        raise AssertionError("an unbuilt slot must be refused")
