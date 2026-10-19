"""Compliant fetching: honest identity, paced requests, a hard page budget.

Every request this module makes says truthfully what it is. If a source
refuses that identity, the run stops and reports the refusal — it never
retries wearing a browser's identity, because obtaining content that the
honest request was denied is circumvention, not crawling.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final, Self
from urllib.parse import urljoin, urlsplit

import httpx

from app.ingestion.robots import RULES_PATH, RobotsRules, RulesUnavailable, parse_rules

logger = logging.getLogger(__name__)

APP_NAME: Final = "HomeRenovationAgentsBot"
APP_VERSION: Final = "0.1"

DEFAULT_TIMEOUT: Final = 30.0


def build_user_agent(contact: str) -> str:
    """The identifier sent on every request: what we are, and how to reach us."""
    return f"{APP_NAME}/{APP_VERSION} (+{contact})"


class BudgetExhausted(Exception):
    """Raised internally when the page budget stops a run. Not an error state."""


@dataclass
class PacedFetcher:
    """Fetches URLs honestly, no faster than the configured interval.

    The budget counts content pages. Fetching a source's rules is not a
    content page and is not charged against it — refusing to read the rules
    because the budget was spent would invert the point of having them.
    """

    user_agent: str
    min_interval_seconds: float = 1.0
    page_budget: int = 50
    timeout: float = DEFAULT_TIMEOUT
    client: httpx.Client | None = None

    _last_request_at: dict[str, float] = field(default_factory=dict, init=False)
    pages_fetched: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._owns_client = self.client is None
        if self.client is None:
            self.client = httpx.Client(follow_redirects=False, timeout=self.timeout)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        if self._owns_client and self.client is not None:
            self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # -- pacing ------------------------------------------------------------

    def _wait_turn(self, url: str) -> None:
        host = urlsplit(url).netloc
        previous = self._last_request_at.get(host)
        if previous is not None:
            remaining = self.min_interval_seconds - (time.monotonic() - previous)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[host] = time.monotonic()

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept-Language": "de-DE,de;q=0.9"}

    # -- requests ----------------------------------------------------------

    def fetch_rules(self, base_url: str, *, source: str) -> RobotsRules:
        """Retrieve and parse a source's published rules.

        Raises `RulesUnavailable` when the source will not serve them, which
        the caller must treat as permission not granted.
        """
        url = urljoin(base_url, RULES_PATH)
        self._wait_turn(url)
        assert self.client is not None
        try:
            response = self.client.get(url, headers=self._headers())
        except httpx.HTTPError as error:
            raise RulesUnavailable(source, f"{type(error).__name__}") from error

        if response.status_code != 200:
            raise RulesUnavailable(source, f"HTTP {response.status_code}")

        media_type = response.headers.get("content-type", "")
        if "text/plain" not in media_type:
            # A challenge page served with a 200 is still a refusal; robots.txt
            # is text/plain by definition, and HTML here means we got a wall.
            raise RulesUnavailable(
                source, f"HTTP 200 but content-type was {media_type or 'unset'}"
            )

        return parse_rules(response.text, user_agent=self.user_agent)

    def fetch_auxiliary(
        self, url: str, *, cookies: dict[str, str] | None = None
    ) -> httpx.Response:
        """Fetch a non-content resource, such as a sitemap or a live lookup.

        Paced like everything else, but not charged against the page budget:
        the budget exists to bound how much of a retailer's *content* a batch
        run pulls, and day 4's live lookups are paced and cached by their own
        `LiveFetcher` instead (CLAUDE.md §8a item 3, design.md decision 3).
        `cookies` lets a caller send the retailer's own store-selector cookie
        without this module knowing anything about what it means. Set as a
        header directly, rather than through httpx's per-request `cookies=`
        (deprecated, and it would persist into the client's cookie jar rather
        than applying to this request alone).
        """
        self._wait_turn(url)
        assert self.client is not None
        headers = self._headers()
        if cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        return self.client.get(url, headers=headers)

    def fetch_page(self, url: str) -> httpx.Response:
        """Fetch one content page, charged against the budget."""
        if self.pages_fetched >= self.page_budget:
            raise BudgetExhausted(url)
        self._wait_turn(url)
        assert self.client is not None
        response = self.client.get(url, headers=self._headers())
        self.pages_fetched += 1
        return response

    def fetch_within_budget(
        self, urls: list[str]
    ) -> Iterator[tuple[str, httpx.Response | Exception]]:
        """Yield (url, response-or-error) until the list or the budget runs out.

        A transport failure is yielded rather than raised: DNS going away
        mid-run is exactly the kind of thing that must cost one page, not the
        whole crawl. Only the budget ends the loop, and that is a normal end.
        """
        for url in urls:
            try:
                yield url, self.fetch_page(url)
            except BudgetExhausted:
                logger.info("page budget of %d reached, stopping", self.page_budget)
                return
            except httpx.HTTPError as error:
                # Charged against the budget: the request was made, and a
                # failing host must not let a run retry indefinitely.
                self.pages_fetched += 1
                yield url, error
