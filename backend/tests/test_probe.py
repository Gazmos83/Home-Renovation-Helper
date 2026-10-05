"""llm-gateway: the startup probe of every routed model.

A fake transport stands in for the gateway: every routed slug answers, one slug
is blocked with a guardrail response, and the disabled path contacts nothing.
"""

from __future__ import annotations

from typing import Any

import httpx2
import pytest

from app.agent.models.probe import probe_models
from app.agent.models.routing import load_routing
from app.config import ConfigurationError, Settings


def _settings() -> Settings:
    return Settings(
        database_url="postgresql://u:p@localhost:5432/d",
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email="owner@example.com",
        owner_password="an-initial-owner-password",
        _env_file=None,
    )


def _completion(slug: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl",
        "object": "chat.completion",
        "created": 0,
        "model": slug,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _client(*, blocked: set[str] | None = None) -> httpx2.Client:
    blocked = blocked or set()

    def handler(request: httpx2.Request) -> httpx2.Response:
        import json

        model = json.loads(request.content)["model"]
        if model in blocked:
            return httpx2.Response(403, json={"error": {"message": "blocked by guardrail"}})
        return httpx2.Response(200, json=_completion(model))

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_all_routed_models_answer_the_probe() -> None:
    routing = load_routing()
    probed = probe_models(_settings(), routing, http_client=_client())
    assert set(probed) == set(routing.distinct_slugs())


def test_a_guardrail_block_fails_startup_naming_the_slug_and_slot() -> None:
    routing = load_routing()
    with pytest.raises(ConfigurationError) as caught:
        probe_models(
            _settings(),
            routing,
            http_client=_client(blocked={"deepseek/deepseek-v4.1-flash"}),
        )
    message = str(caught.value)
    assert "deepseek/deepseek-v4.1-flash" in message
    # The slug serves two image slots; the message names one of them.
    assert "intake" in message or "reviewer" in message
    assert "blocked" in message


def test_the_disabled_path_contacts_nothing_and_logs_probe_skipped(
    migrated_database: str, capsys
) -> None:
    """With the probe off, the lifespan contacts no gateway and says so.

    `capsys`, not `caplog`: `configure_logging()` (run inside `create_app`)
    replaces the root logger's handlers with its own JSON-to-stdout one.
    """
    import json

    from fastapi.testclient import TestClient

    from app.main import create_app
    from conftest import OWNER_EMAIL, OWNER_PASSWORD

    settings = Settings(
        database_url=migrated_database,
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        gateway_probe_enabled=False,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200

    messages = [
        json.loads(line).get("message")
        for line in capsys.readouterr().out.strip().splitlines()
        if line.startswith("{")
    ]
    assert "gateway probe skipped" in messages
