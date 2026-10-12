"""Honest, paced HTTPS fetches with the existing pinned-address SSRF guard."""

import socket
from urllib.parse import urlsplit

import httpx

from app.ingestion.fetcher import PacedFetcher, build_user_agent
from app.ingestion.robots import RulesUnavailable, parse_rules
from app.plugins.executor import _checked_address


class KnowledgeFetcher(PacedFetcher):
    def __init__(
        self, settings, *, resolver=socket.getaddrinfo, transport=None, max_bytes=None
    ):
        super().__init__(
            user_agent=build_user_agent(settings.crawler_identity),
            min_interval_seconds=settings.ingestion_min_interval_seconds,
            page_budget=settings.ingestion_page_budget,
        )
        self._resolver = resolver
        self._transport = transport
        self._max_bytes = max_bytes or settings.guideline_upload_max_bytes

    def _get(self, url: str, *, limit: int) -> httpx.Response:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
        ):
            raise ValueError("only HTTPS without credentials/custom ports is permitted")
        host = parts.hostname
        address = _checked_address(host, self._resolver)
        literal = f"[{address}]" if ":" in address else address
        target = parts.path or "/"
        if parts.query:
            target += f"?{parts.query}"
        self._wait_turn(url)
        with (
            httpx.Client(
                transport=self._transport,
                timeout=self.timeout,
                follow_redirects=False,
                verify=True,
            ) as client,
            client.stream(
                "GET",
                f"https://{literal}{target}",
                headers={"Host": host, **self._headers()},
                extensions={"sni_hostname": host},
            ) as response,
        ):
            if response.is_redirect or response.status_code != 200:
                raise ValueError(
                    f"host refused content: HTTP {response.status_code}; no redirect/retry"
                )
            size, body = 0, []
            for piece in response.iter_bytes():
                size += len(piece)
                if size > limit:
                    raise ValueError("remote response exceeds the configured limit")
                body.append(piece)
            return httpx.Response(
                200,
                headers=response.headers,
                content=b"".join(body),
                request=httpx.Request("GET", url),
            )

    def fetch_rules(self, base_url: str, *, source: str):
        try:
            response = self._get(
                base_url.rstrip("/") + "/robots.txt", limit=1024 * 1024
            )
            if "text/plain" not in response.headers.get("content-type", ""):
                raise ValueError("robots response is not text/plain")
            return parse_rules(response.text, user_agent=self.user_agent)
        except Exception as error:  # noqa: BLE001 - all fetch/rules failures deny access
            raise RulesUnavailable(source, type(error).__name__) from None

    def fetch_page(self, url: str):
        from app.ingestion.fetcher import BudgetExhausted

        if self.pages_fetched >= self.page_budget:
            raise BudgetExhausted(url)
        self.pages_fetched += 1
        return self._get(url, limit=self._max_bytes)
