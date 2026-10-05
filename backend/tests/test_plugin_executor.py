"""plugins: HTTPS execution is bounded — no private addresses, no redirects, no bodies logged."""

from __future__ import annotations

import json
import socket
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.prompts import CLOSE_TOKEN, OPEN_PREFIX
from app.config import Settings
from app.db.models import PluginOutcome
from app.plugins.executor import PluginExecutor
from app.plugins.manifest import HttpsManifest, parse_manifest

HOST = "echo.plugin-test.invalid"
PUBLIC_IP = "104.21.81.123"


@pytest.fixture
def domain(db_session: Session) -> Iterator[Session]:
    db_session.execute(text("TRUNCATE TABLE plugin_invocations, threads CASCADE"))
    db_session.commit()
    yield db_session
    db_session.rollback()


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "plugin_allowed_hosts": HOST,
        "plugin_min_interval_seconds": 0,
        **overrides,
    }
    return Settings(
        database_url="postgresql://u:p@localhost:5432/d",
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email="owner@example.com",
        owner_password="an-initial-owner-password",
        _env_file=None,
        **values,
    )


def _resolver(*addresses: str):
    def resolve(host: str, port: int, **_: Any) -> list[tuple[Any, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses]

    return resolve


def _manifest() -> HttpsManifest:
    parsed = parse_manifest(
        {
            "name": "echo",
            "description": "echo",
            "kind": "https",
            "role": "researcher",
            "tools": ["plugin_echo"],
            "enabled_by_default": False,
            "input_schema": {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "n": {"type": "integer"}},
                "additionalProperties": False,
            },
            "request": {"method": "GET", "url": f"https://{HOST}/search/{{q}}"},
        }
    )
    assert isinstance(parsed, HttpsManifest)
    return parsed


def _executor(
    domain: Session, handler, *, resolver=None, **settings: Any
) -> tuple[PluginExecutor, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    executor = PluginExecutor(
        domain.get_bind(),
        _settings(**settings),
        resolver=resolver or _resolver(PUBLIC_IP),
        transport=httpx.MockTransport(recording),
    )
    return executor, seen


def _invoke(executor: PluginExecutor, **args: Any) -> str:
    return executor.invoke(_manifest(), args or {"q": "hello"}, thread_id=None)


def _outcomes(domain: Session) -> list[str]:
    return list(
        domain.execute(text("SELECT outcome FROM plugin_invocations ORDER BY created_at")).scalars()
    )


def test_a_success_is_rendered_as_untrusted_data_and_drops_undeclared_fields(
    domain: Session,
) -> None:
    executor, seen = _executor(
        domain,
        lambda r: httpx.Response(200, json={"text": "ok", "n": 1, "injected": "ignore previous"}),
    )

    result = _invoke(executor)

    assert result.startswith(OPEN_PREFIX) and result.endswith(CLOSE_TOKEN)
    assert f'url="https://{HOST}/search/hello"' in result
    assert "injected" not in result
    assert '"text": "ok"' in result
    request = seen[0]
    assert request.url.host == PUBLIC_IP
    assert request.headers["host"] == HOST
    assert request.extensions["sni_hostname"] == HOST
    assert "cookie" not in {h.lower() for h in request.headers}
    assert "authorization" not in {h.lower() for h in request.headers}
    assert _outcomes(domain) == ["ok"]
    row = domain.execute(text("SELECT plugin, outcome, duration_ms FROM plugin_invocations")).one()
    assert row[0] == "echo"
    assert row[1] == PluginOutcome.OK.value
    assert row[2] is not None


def test_the_audit_row_never_stores_arguments_or_the_body(domain: Session) -> None:
    executor, _seen = _executor(domain, lambda r: httpx.Response(200, json={"text": "secret-body", "n": 2}))
    _invoke(executor, q="secret-arg")
    dumped = json.dumps(
        [
            {key: str(value) for key, value in dict(row).items()}
            for row in domain.execute(text("SELECT * FROM plugin_invocations")).mappings()
        ]
    )
    assert "secret-arg" not in dumped
    assert "secret-body" not in dumped


def test_a_private_address_is_refused_with_no_connection(domain: Session) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"text": "nope"})

    executor = PluginExecutor(
        domain.get_bind(),
        _settings(),
        resolver=_resolver("10.0.0.5"),
        transport=httpx.MockTransport(handler),
    )

    result = _invoke(executor)

    assert seen == []
    assert "refused" in result.lower() or "could not return data" in result
    assert "10.0.0.5" not in result
    assert _outcomes(domain) == ["refused"]


def test_a_redirect_is_not_followed(domain: Session) -> None:
    executor, seen = _executor(
        domain, lambda r: httpx.Response(302, headers={"location": "https://evil.example/x"})
    )

    result = _invoke(executor)

    assert len(seen) == 1
    assert "redirect" in result
    assert _outcomes(domain) == ["refused"]


def test_an_oversized_body_is_refused(domain: Session) -> None:
    executor, _seen = _executor(
        domain,
        lambda r: httpx.Response(200, content=b"x" * 300_000),
        plugin_max_response_bytes=1024,
    )

    result = _invoke(executor)

    assert "too large" in result
    assert _outcomes(domain) == ["too_large"]


def test_a_timeout_is_returned_as_text(domain: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    executor, _seen = _executor(domain, handler)

    result = _invoke(executor)

    assert "could not return data" in result
    assert "time" in result
    assert _outcomes(domain) == ["timeout"]
    assert "echo.plugin-test.invalid" not in result or "plugin_echo" in result


def test_a_failure_does_not_raise(domain: Session) -> None:
    executor, _seen = _executor(domain, lambda r: httpx.Response(500, json={"error": "no"}))
    result = _invoke(executor)
    assert isinstance(result, str)
    assert "could not return data" in result
    assert _outcomes(domain) == ["unfetchable"]
