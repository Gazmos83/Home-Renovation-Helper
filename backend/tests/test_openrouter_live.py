"""llm-gateway: the real probe, on request only.

Everything else in the suite runs against a fake transport. This is the single
test that proves the gateway is actually reachable and that every routed slug —
including the image Reviewer — answers under `require_parameters` routing.

Skipped unless `--live` is passed. It spends money; run it once.
"""

from __future__ import annotations

import pytest

from app.agent.models.probe import probe_models
from app.agent.models.routing import load_routing
from app.config import load_settings

pytestmark = pytest.mark.live


@pytest.fixture
def live_settings():
    """Real configuration, including the repo-root .env where the key lives."""
    settings = load_settings()
    if settings.openrouter_api_key.get_secret_value().strip() in ("", "change-me", "sk-or-v1-change-me"):
        pytest.skip("OPENROUTER_API_KEY is not set")
    return settings


def test_the_real_probe_passes_for_every_routed_slug(live_settings) -> None:
    routing = load_routing()
    probed = probe_models(live_settings, routing)
    assert set(probed) == set(routing.distinct_slugs())
