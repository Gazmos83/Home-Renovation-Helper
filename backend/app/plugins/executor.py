"""The one bounded HTTPS GET an HTTPS plugin may make.

In order, per invocation: re-check the host, resolve and refuse non-global
addresses, connect to the checked address with the host's name for TLS, follow
no redirect, bound the response, validate the output (undeclared fields
dropped), wrap as untrusted content. Every outcome is recorded without
arguments or body; a failure is a readable result, never an exception.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Final
from urllib.parse import quote, urlencode, urlsplit
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.agent.prompts import Passage, wrap_passage
from app.config import Settings
from app.db.models import PluginInvocation, PluginOutcome
from app.plugins.https_schema import output_adapter
from app.plugins.manifest import HttpsManifest, RequestSpec

logger = logging.getLogger("app")

_UNAVAILABLE: Final = (
    "The {name} tool could not return data: {reason}. No result was obtained, so "
    "state that the information is unavailable and do not invent it."
)

USER_AGENT: Final = "HomeRenovationAgents/0.1"
Resolver = Callable[..., list[tuple[Any, ...]]]


class _Refusal(Exception):
    def __init__(self, outcome: PluginOutcome, reason: str) -> None:
        super().__init__(reason)
        self.outcome = outcome
        self.reason = reason


def _render_url(spec: RequestSpec, args: dict[str, Any]) -> tuple[str, str]:
    parts = urlsplit(spec.url)
    path = parts.path
    for name, value in args.items():
        path = path.replace("{" + name + "}", quote(str(value), safe=""))
    if any(segment in (".", "..") for segment in path.split("/")):
        raise _Refusal(PluginOutcome.REFUSED, "an argument is not a valid path value")
    query: dict[str, str] = {}
    for key, template in spec.query.items():
        placeholder = (
            template.strip("{}") if template.startswith("{") and template.endswith("}") else None
        )
        if placeholder is not None:
            value = args.get(placeholder)
            if value is None:
                continue
            query[key] = str(value).lower() if isinstance(value, bool) else str(value)
        else:
            query[key] = template
    target = path + (f"?{urlencode(query)}" if query else "")
    return target, f"https://{spec.host}{target}"


def _checked_address(host: str, resolver: Resolver) -> str:
    try:
        infos = resolver(host, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise _Refusal(PluginOutcome.UNFETCHABLE, "the host could not be resolved") from error
    addresses = []
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_multicast:
            raise _Refusal(PluginOutcome.REFUSED, "the host resolves to a non-public address")
        addresses.append(address)
    if not addresses:
        raise _Refusal(PluginOutcome.UNFETCHABLE, "the host could not be resolved")
    addresses.sort(key=lambda a: a.version)
    return str(addresses[0])


class PluginExecutor:
    """Executes HTTPS plugin calls; one per application."""

    def __init__(
        self,
        engine: Engine,
        settings: Settings,
        *,
        resolver: Resolver = socket.getaddrinfo,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._resolver = resolver
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._last_call: dict[str, float] = {}
        self._pace_lock = threading.Lock()

    def invoke(
        self,
        manifest: HttpsManifest,
        args: dict[str, Any],
        *,
        thread_id: UUID | None,
    ) -> str:
        started = self._clock()
        try:
            text = self._run(manifest, args)
        except _Refusal as refusal:
            self._record(manifest.name, thread_id, refusal.outcome, started)
            logger.warning(
                "plugin call refused",
                extra={
                    "context": {
                        "plugin": manifest.name,
                        "outcome": refusal.outcome.value,
                        "reason": refusal.reason,
                    }
                },
            )
            return _UNAVAILABLE.format(name=manifest.tools[0], reason=refusal.reason)
        self._record(manifest.name, thread_id, PluginOutcome.OK, started)
        return text

    def _run(self, manifest: HttpsManifest, args: dict[str, Any]) -> str:
        host = manifest.request.host
        if host not in self._settings.plugin_allowed_hosts:
            raise _Refusal(PluginOutcome.REFUSED, "the plugin's host is no longer approved")
        target, public_url = _render_url(manifest.request, args)
        address = _checked_address(host, self._resolver)
        self._pace(host)
        body = self._fetch(address, host, target)
        try:
            payload = json.loads(body)
        except ValueError:
            raise _Refusal(
                PluginOutcome.INVALID_OUTPUT, "the provider returned unreadable data"
            ) from None
        try:
            parsed = output_adapter(manifest).validate_python(payload)
        except ValidationError:
            raise _Refusal(
                PluginOutcome.INVALID_OUTPUT,
                "the provider's data did not match the declared format",
            ) from None
        rendered = output_adapter(manifest).dump_python(parsed, mode="json")
        fetched_at = datetime.now(UTC).isoformat()
        passage = Passage(
            content=json.dumps(rendered, ensure_ascii=False), url=public_url, scraped_at=fetched_at
        )
        return wrap_passage(passage, fetched_at)

    def _fetch(self, address: str, host: str, target: str) -> bytes:
        literal = f"[{address}]" if ":" in address else address
        limit = self._settings.plugin_max_response_bytes
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=self._settings.plugin_timeout_seconds,
                follow_redirects=False,
                verify=True,
            ) as client, client.stream(
                "GET",
                f"https://{literal}{target}",
                headers={
                    "Host": host,
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
                extensions={"sni_hostname": host},
            ) as response:
                    if response.is_redirect:
                        raise _Refusal(
                            PluginOutcome.REFUSED,
                            "the provider redirected, and redirects are not followed",
                        )
                    if response.status_code >= 400:
                        raise _Refusal(
                            PluginOutcome.UNFETCHABLE,
                            f"the provider answered HTTP {response.status_code}",
                        )
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise _Refusal(
                                PluginOutcome.TOO_LARGE, "the provider's response was too large"
                            )
                        chunks.append(chunk)
                    return b"".join(chunks)
        except httpx.TimeoutException:
            raise _Refusal(PluginOutcome.TIMEOUT, "the provider did not answer in time") from None
        except httpx.HTTPError:
            raise _Refusal(PluginOutcome.UNFETCHABLE, "the provider could not be reached") from None

    def _pace(self, host: str) -> None:
        interval = self._settings.plugin_min_interval_seconds
        with self._pace_lock:
            last = self._last_call.get(host)
            now = self._clock()
            if last is not None and now - last < interval:
                self._sleep(interval - (now - last))
            self._last_call[host] = self._clock()

    def _record(
        self,
        plugin: str,
        thread_id: UUID | None,
        outcome: PluginOutcome,
        started: float,
    ) -> None:
        duration = int((self._clock() - started) * 1000)
        try:
            with Session(self._engine) as session:
                session.add(
                    PluginInvocation(
                        id=uuid4(),
                        plugin=plugin,
                        thread_id=thread_id,
                        outcome=outcome.value,
                        duration_ms=max(duration, 0),
                    )
                )
                session.commit()
        except Exception as error:  # noqa: BLE001 - an audit write must not fail the turn
            logger.warning(
                "plugin invocation unrecorded",
                extra={"context": {"error_type": type(error).__name__, "outcome": outcome.value}},
            )
