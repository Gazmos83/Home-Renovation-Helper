"""Startup probe of every routed model (llm-gateway; design.md decision 5).

At startup, one minimal request is sent through the gateway for each distinct
routed slug — an image request for a slug reached from an image slot, a text
request otherwise — concurrently. A refusal, a guardrail block or an unlisted
model is reported as a `ConfigurationError` naming the slot and slug, never as a
generic model failure, so a blocked Reviewer surfaces at boot rather than
mid-session (CLAUDE.md §1, §4).

The probe is skipped when `GATEWAY_PROBE_ENABLED` is false; the lifespan then
records that it was skipped. Tests pass a fake transport; the `--live` suite
runs it for real.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final

from app.agent.models.openrouter_client import (
    GatewayError,
    build_chat_model,
    gateway_errors,
)
from app.agent.models.routing import Routing
from app.config import ConfigurationError, Settings

logger = logging.getLogger("app")

PROBE_OPERATION: Final = "startup_probe"

# A 1×1 transparent PNG, enough for an image slot's probe to carry a real image
# the gateway can accept without any file on disk.
_PIXEL_DATA_URI: Final = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _text_probe(settings: Settings, slug: str, http_client: Any | None) -> None:
    model = build_chat_model(settings, model_id=slug, http_client=http_client, max_retries=0)
    with gateway_errors(operation=PROBE_OPERATION):
        model.invoke("ping")


def _image_probe(settings: Settings, slug: str, http_client: Any | None) -> None:
    model = build_chat_model(settings, model_id=slug, http_client=http_client, max_retries=0)
    message = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "ping"},
                {"type": "image_url", "image_url": {"url": _PIXEL_DATA_URI}},
            ],
        }
    ]
    with gateway_errors(operation=PROBE_OPERATION):
        model.invoke(message)


def probe_slug(
    settings: Settings,
    slug: str,
    *,
    image: bool = False,
    http_client: Any | None = None,
) -> None:
    """Probe one slug. Raises `ConfigurationError` naming the model on failure."""
    try:
        if image:
            _image_probe(settings, slug, http_client)
        else:
            _text_probe(settings, slug, http_client)
    except GatewayError as error:
        raise ConfigurationError(
            f"model {slug} blocked by gateway: {error.reason}"
        ) from error


def probe_models(
    settings: Settings,
    routing: Routing,
    *,
    http_client: Any | None = None,
    max_workers: int = 4,
) -> list[str]:
    """Probe each distinct routed slug. Returns the probed slugs on success.

    Raises `ConfigurationError` naming the slot, slug and reason on the first
    slug the gateway blocks or cannot serve.
    """
    slugs = routing.distinct_slugs()
    image_slugs = routing.image_slugs()
    # A representative slot per slug, for the error message.
    slug_to_slot: dict[str, str] = {}
    for slot, slug in routing.items():
        slug_to_slot.setdefault(slug, slot)

    def probe(slug: str) -> None:
        if slug in image_slugs:
            _image_probe(settings, slug, http_client)
        else:
            _text_probe(settings, slug, http_client)

    errors: dict[str, GatewayError] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(probe, slug): slug for slug in slugs}
        for future, slug in ((f, futures[f]) for f in futures):
            try:
                future.result()
            except GatewayError as error:
                errors[slug] = error

    if errors:
        # Report the first slug (in canonical order) that failed, so the message
        # is stable across runs.
        slug = next(s for s in slugs if s in errors)
        error = errors[slug]
        slot = slug_to_slot[slug]
        raise ConfigurationError(
            f"routing: {slot} → {slug} blocked by gateway: {error.reason}"
        )

    for slug in slugs:
        logger.info(
            "routed model probed",
            extra={"context": {"slug": slug, "slot": slug_to_slot[slug]}},
        )
    return slugs
