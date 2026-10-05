"""llm-gateway: per-model generation profiles and their persistence."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.models.profiles import (
    DEFAULT_PROFILE,
    GenerationProfile,
    InvalidGenerationSettings,
    Profiles,
)
from app.db.session import make_engine

TEMPERATURE_MODEL = "deepseek/deepseek-v4-pro-0813"
NO_TEMPERATURE_MODEL = "openai/gpt-5.6-sol"


@pytest.fixture
def engine(migrated_database: str):
    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("TRUNCATE TABLE operator_settings"))
        session.commit()
    yield engine
    engine.dispose()


def test_the_default_profile_sends_no_temperature_or_cap() -> None:
    assert DEFAULT_PROFILE.model_kwargs(TEMPERATURE_MODEL) == {}


def test_a_profile_sends_temperature_and_cap_for_a_supporting_model() -> None:
    profile = GenerationProfile(temperature=0.3, max_output_tokens=512)
    assert profile.model_kwargs(TEMPERATURE_MODEL) == {"temperature": 0.3, "max_tokens": 512}


def test_temperature_is_dropped_for_a_model_without_support() -> None:
    profile = GenerationProfile(temperature=0.3, max_output_tokens=512)
    kwargs = profile.model_kwargs(NO_TEMPERATURE_MODEL)
    assert "temperature" not in kwargs
    assert kwargs["max_tokens"] == 512


def test_an_unknown_model_with_no_profile_sends_the_default(engine) -> None:
    profiles = Profiles(engine)
    assert profiles.profile_for(TEMPERATURE_MODEL) is DEFAULT_PROFILE


def test_a_stored_profile_survives_a_fresh_instance(engine) -> None:
    Profiles(engine).set_generation(
        TEMPERATURE_MODEL, temperature=0.7, max_output_tokens=256, actor="owner"
    )
    reloaded = Profiles(engine)
    profile = reloaded.profile_for(TEMPERATURE_MODEL)
    assert profile.temperature == 0.7
    assert profile.max_output_tokens == 256


def test_a_temperature_on_an_unsupported_model_is_refused(engine) -> None:
    with pytest.raises(InvalidGenerationSettings):
        Profiles(engine).set_generation(
            NO_TEMPERATURE_MODEL, temperature=0.5, max_output_tokens=None, actor="owner"
        )


def test_reset_returns_a_model_to_the_default(engine) -> None:
    profiles = Profiles(engine)
    profiles.set_generation(
        TEMPERATURE_MODEL, temperature=0.4, max_output_tokens=None, actor="owner"
    )
    profiles.reset_generation(TEMPERATURE_MODEL)
    assert Profiles(engine).profile_for(TEMPERATURE_MODEL) is DEFAULT_PROFILE
