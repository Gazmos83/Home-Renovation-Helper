"""llm-gateway: models are routable only from a closed registry."""

from __future__ import annotations

from dataclasses import fields

from app.agent.models.registry import (
    BY_ID,
    MODELS,
    ModelEntry,
    available_ids,
    is_available,
    is_known,
    known_ids,
    supports_images,
)

EXPECTED_IDS = {
    "openai/gpt-5.6-luna",
    "openai/gpt-5.6-sol",
    "deepseek/deepseek-v4-pro-0813",
    "deepseek/deepseek-v4.1-flash",
    "anthropic/claude-haiku-4.5",
    "deepseek/deepseek-v4-flash",
    "~deepseek/deepseek-v4-flash-latest",
}
IMAGE_ID = "deepseek/deepseek-v4.1-flash"
ALIAS_ID = "~deepseek/deepseek-v4-flash-latest"
V4_FLASH_IDS = {"deepseek/deepseek-v4-flash", ALIAS_ID}


def test_the_registry_is_exactly_the_seven_probed_slugs() -> None:
    assert set(known_ids()) == EXPECTED_IDS
    assert set(BY_ID) == EXPECTED_IDS


def test_image_support_is_only_on_the_reviewer_slug() -> None:
    assert supports_images(IMAGE_ID) is True
    for model_id in EXPECTED_IDS - {IMAGE_ID}:
        assert supports_images(model_id) is False, model_id


def test_every_entry_describes_itself_and_was_validated_on_its_probe_date() -> None:
    from datetime import date

    for entry in MODELS:
        assert entry.model_id
        assert entry.display_name
        assert entry.context_window > 0
        assert entry.max_output_tokens_limit > 0
        probed = date(2026, 10, 9) if entry.model_id in V4_FLASH_IDS else date(2026, 10, 5)
        assert entry.validated_on == probed, entry.model_id
        assert entry.availability == "available"
        assert entry.availability_reason is None


def test_only_the_latest_v4_flash_slug_is_an_alias() -> None:
    assert {entry.model_id for entry in MODELS if entry.alias} == {ALIAS_ID}
    for model_id in V4_FLASH_IDS:
        assert supports_images(model_id) is False, model_id


def test_registry_holds_no_price() -> None:
    """§5a: prices are fetched live, never hardcoded here.

    Asserted on the field names so adding a price field later fails this test
    rather than passing unnoticed.
    """
    names = {field.name for field in fields(ModelEntry)}
    assert not {name for name in names if "price" in name or "cost" in name}


def test_all_registered_slugs_are_available() -> None:
    assert set(available_ids()) == EXPECTED_IDS


def test_unknown_slug_is_refused() -> None:
    assert is_known("anthropic/claude-sonnet-5.5") is False
    assert is_known("google/gemini-3.5-flash") is False
    assert is_available("anthropic/claude-sonnet-5.5") is False
