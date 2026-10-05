"""The closed set of models the application may route to.

One gateway, one key (CLAUDE.md §2, §4). Adding a model is an entry here, never
a new client and never a second secret. A slug outside the registry is refused
by name wherever a model is chosen.

An entry is either `available` or `unavailable`. An unavailable entry stays
listed so a later probe failure can record why a slug cannot be chosen, but it
is never routed to and never invoked (llm-gateway). Capability fields record
what the gateway's public catalogue stated on `validated_on`.

No prices. §5a treats the build guide's figures as a point-in-time reference
and reads live pricing from OpenRouter's models endpoint; a hardcoded price
goes stale silently while still looking authoritative.

The four slugs blocked by the owner's OpenRouter guardrail on 2026-10-05 are
NOT entries here, so they can never be selected:
  anthropic/claude-sonnet-5.5, anthropic/claude-opus-5.5,
  google/gemini-3.5-flash, z-ai/glm-5.3-flash.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

Availability = Literal["available", "unavailable"]

_VALIDATED: Final = date(2026, 10, 5)


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """One registry model, described well enough to route between them."""

    model_id: str
    display_name: str
    context_window: int
    availability: Availability
    availability_reason: str | None
    supports_temperature: bool
    supports_images: bool
    max_output_tokens_limit: int
    validated_on: date


# The five slugs the gateway probe passed on 2026-10-05 (CLAUDE.md §4,
# design.md decision 4). `deepseek/deepseek-v4.1-flash` is the only one that
# accepts image input — the Reviewer slot requires it.
MODELS: Final[tuple[ModelEntry, ...]] = (
    ModelEntry(
        "openai/gpt-5.6-luna", "GPT-5.6 Luna", 400_000,
        "available", None, True, False, 128_000, _VALIDATED,
    ),
    ModelEntry(
        # A reasoning model: the catalogue lists no temperature parameter.
        "openai/gpt-5.6-sol", "GPT-5.6 Sol", 400_000,
        "available", None, False, False, 128_000, _VALIDATED,
    ),
    ModelEntry(
        "deepseek/deepseek-v4-pro-0813", "DeepSeek V4 Pro 0813", 1_310_720,
        "available", None, True, False, 262_144, _VALIDATED,
    ),
    ModelEntry(
        "deepseek/deepseek-v4.1-flash", "DeepSeek V4.1 Flash", 1_310_720,
        "available", None, True, True, 262_144, _VALIDATED,
    ),
    ModelEntry(
        # Image input is not enabled for this slot's use; the only image-routed
        # slot (Reviewer) uses deepseek-v4.1-flash, probed with an image.
        "anthropic/claude-haiku-4.5", "Claude Haiku 4.5", 200_000,
        "available", None, True, False, 64_000, _VALIDATED,
    ),
)

BY_ID: Final[dict[str, ModelEntry]] = {entry.model_id: entry for entry in MODELS}


def is_known(model_id: str) -> bool:
    return model_id in BY_ID


def known_ids() -> list[str]:
    return [entry.model_id for entry in MODELS]


def is_available(model_id: str) -> bool:
    entry = BY_ID.get(model_id)
    return entry is not None and entry.availability == "available"


def available_ids() -> list[str]:
    return [entry.model_id for entry in MODELS if entry.availability == "available"]


def supports_images(model_id: str) -> bool:
    entry = BY_ID.get(model_id)
    return entry is not None and entry.supports_images
