"""llm-gateway: one gateway, capability-constrained routing, contained secrets.

The routing constraint is asserted on the wire rather than on the client's
attributes. `extra_body` versus `model_kwargs` is a silent difference — the
wrong one produces a client that looks correctly configured and sends nothing —
so these tests read the JSON the transport actually received.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx2
import openai
import pytest

from app.agent.models.openrouter_client import (
    OPENROUTER_BASE_URL,
    GatewayError,
    build_chat_model,
    gateway_errors,
)
from app.config import Settings

SETTINGS_KEY = "sk-or-v1-fromsettings-deadbeef"
MODEL = "deepseek/deepseek-v4-pro-0813"


def _completion(content: str = "ok") -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _recording_client(sink: dict[str, Any]) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        sink["url"] = str(request.url)
        sink["body"] = json.loads(request.content)
        sink["authorization"] = request.headers.get("authorization", "")
        return httpx2.Response(200, json=_completion())

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def _failing_client(fail: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(fail))


@pytest.fixture
def gateway_settings(settings: Settings) -> Settings:
    """Rebuilt rather than `model_copy`-ed: a copy skips validation, so the key
    would stay a plain string and never become the `SecretStr` the client reads."""
    return Settings(
        database_url=str(settings.database_url),
        openrouter_api_key=SETTINGS_KEY,
        cors_origins="http://localhost:5173",
        owner_email="owner@example.com",
        owner_password="an-initial-owner-password",
        _env_file=None,
    )


# --- configuration -----------------------------------------------------------


def test_client_targets_the_openrouter_gateway(gateway_settings: Settings) -> None:
    sink: dict[str, Any] = {}
    build_chat_model(
        gateway_settings, model_id=MODEL, http_client=_recording_client(sink)
    ).invoke("hi")
    assert sink["url"].startswith(OPENROUTER_BASE_URL)
    assert sink["body"]["model"] == MODEL


def test_key_comes_from_settings_not_the_ambient_environment(
    gateway_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ambient OPENAI_API_KEY would mean calling a gateway we did not configure."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ambient-must-not-be-used")
    sink: dict[str, Any] = {}
    build_chat_model(
        gateway_settings, model_id=MODEL, http_client=_recording_client(sink)
    ).invoke("hi")
    assert sink["authorization"] == f"Bearer {SETTINGS_KEY}"


def test_no_generation_parameter_is_sent_by_default(gateway_settings: Settings) -> None:
    sink: dict[str, Any] = {}
    build_chat_model(
        gateway_settings, model_id=MODEL, http_client=_recording_client(sink)
    ).invoke("hi")
    assert "temperature" not in sink["body"]
    assert "max_tokens" not in sink["body"]
    assert "max_completion_tokens" not in sink["body"]


# --- routing -----------------------------------------------------------------


def test_provider_routing_reaches_the_request_body(gateway_settings: Settings) -> None:
    sink: dict[str, Any] = {}
    build_chat_model(
        gateway_settings, model_id=MODEL, http_client=_recording_client(sink)
    ).invoke("hi")
    assert sink["body"]["provider"] == {"require_parameters": True}


def test_provider_routing_survives_tool_binding(gateway_settings: Settings) -> None:
    from langchain_core.tools import tool

    @tool
    def sample(query: str) -> str:
        """A tool, so the request carries a tools array."""
        return query

    sink: dict[str, Any] = {}
    model = build_chat_model(gateway_settings, model_id=MODEL, http_client=_recording_client(sink))
    model.bind_tools([sample]).invoke("hi")

    assert sink["body"]["tools"], "the request must actually offer tools"
    assert sink["body"]["provider"] == {"require_parameters": True}


# --- failure handling --------------------------------------------------------


def _raise_status(status: int) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        # A body shaped like a provider's, to prove none of it escapes.
        return httpx2.Response(
            status,
            json={"error": {"message": f"upstream said {SETTINGS_KEY} was involved"}},
        )

    return handler


@pytest.mark.parametrize(
    ("status", "expected_class"),
    [
        (429, "rate_limited"),
        (401, "unauthorized"),
        (403, "forbidden"),
        (404, "refused"),
    ],
)
def test_status_failures_map_to_a_class(
    gateway_settings: Settings, status: int, expected_class: str
) -> None:
    model = build_chat_model(
        gateway_settings, model_id=MODEL, http_client=_failing_client(_raise_status(status)),
        max_retries=0,
    )
    with pytest.raises(GatewayError) as caught, gateway_errors(operation="test"):
        model.invoke("hi")
    assert caught.value.error_class == expected_class
    assert caught.value.reason


def test_a_timeout_maps_to_timeout(gateway_settings: Settings) -> None:
    def time_out(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.TimeoutException("too slow", request=request)

    model = build_chat_model(
        gateway_settings, model_id=MODEL, http_client=_failing_client(time_out), max_retries=0
    )
    with pytest.raises(GatewayError) as caught, gateway_errors(operation="test"):
        model.invoke("hi")
    assert caught.value.error_class == "timeout"


def test_failure_carries_no_credential_and_no_provider_payload(
    gateway_settings: Settings,
) -> None:
    model = build_chat_model(
        gateway_settings, model_id=MODEL, http_client=_failing_client(_raise_status(429)),
        max_retries=0,
    )
    with pytest.raises(GatewayError) as caught, gateway_errors(operation="test"):
        model.invoke("hi")

    rendered = f"{caught.value.reason} {caught.value!s} {caught.value.error_class}"
    assert SETTINGS_KEY not in rendered
    assert "upstream said" not in rendered, "the provider's body must not escape"


def test_failure_log_record_names_the_class_and_leaks_nothing(
    gateway_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    model = build_chat_model(
        gateway_settings, model_id=MODEL, http_client=_failing_client(_raise_status(429)),
        max_retries=0,
    )
    with (
        caplog.at_level(logging.WARNING, logger="app"),
        pytest.raises(GatewayError),
        gateway_errors(operation="probe_designer"),
    ):
        model.invoke("hi")

    records = [r for r in caplog.records if r.message == "model call failed"]
    assert len(records) == 1
    context = records[0].context
    assert context["error_class"] == "rate_limited"
    assert context["operation"] == "probe_designer"
    assert SETTINGS_KEY not in repr(context)
    assert "upstream said" not in repr(context)


def test_a_successful_call_raises_nothing(gateway_settings: Settings) -> None:
    sink: dict[str, Any] = {}
    with gateway_errors(operation="test"):
        reply = build_chat_model(
            gateway_settings, model_id=MODEL, http_client=_recording_client(sink)
        ).invoke("hi")
    assert reply.content == "ok"


def test_non_gateway_errors_are_not_swallowed() -> None:
    with pytest.raises(ValueError), gateway_errors(operation="test"):
        raise ValueError("a bug in our own code")


def test_openai_errors_outside_the_map_still_become_gateway_errors() -> None:
    with pytest.raises(GatewayError) as caught, gateway_errors(operation="test"):
        raise openai.OpenAIError("something unclassified")
    assert caught.value.error_class == "gateway_error"
