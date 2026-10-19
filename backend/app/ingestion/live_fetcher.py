"""Live fetching for owner-triggered lookups (pricing-researcher design decision 2).

An owner's turn is not a batch run: it needs a robots check on every request
rather than once per run, a short per-URL cache so a repeated question or a
multi-product comparison does not multiply load on the retailer, and its own
(shorter) timeout because the owner is waiting. `PacedFetcher` still does the
honest identification and pacing — this module adds the gate and the cache
around it rather than duplicating either.

Outcomes are a closed, readable set (live-listing-lookup: "Failure outcomes
are distinct and readable"). Nothing here raises for an ordinary failure; a
timeout, a refusal, an exclusion and a transport failure are all values a
caller can act on.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal, Self
from urllib.parse import urlsplit

import httpx

from app.ingestion.fetcher import PacedFetcher, build_user_agent
from app.ingestion.robots import RobotsRules, RulesUnavailable

logger = logging.getLogger("app")

# The owner is waiting, unlike a batch run: a shorter budget than ingestion's
# (`app.ingestion.fetcher.DEFAULT_TIMEOUT`, 30s).
DEFAULT_TIMEOUT: Final = 10.0
DEFAULT_CACHE_TTL_SECONDS: Final = 120.0
DEFAULT_CACHE_SIZE: Final = 256
DEFAULT_ROBOTS_REFRESH_SECONDS: Final = 3600.0

# toom's own store-selector cookie (design.md decision 2). Naming it here,
# rather than in the tool, keeps "what toom's cookie is called" in the one
# module that talks to toom over HTTP.
MARKET_ID_COOKIE: Final = "market_id"

Outcome = Literal["ok", "timeout", "refused", "excluded", "unfetchable"]

_REFUSAL_STATUSES: Final = frozenset({401, 403, 429})


@dataclass(frozen=True, slots=True)
class FetchResult:
    """One fetch's outcome. Never raised — always something a caller can read."""

    outcome: Outcome
    url: str
    html: str | None = None
    fetched_at: datetime | None = None
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class LiveFetcher:
    """One robots-gated, cached, paced fetch path for live shopper lookups.

    A long-lived object: built once at startup and held on `app.state`
    (pricing-researcher), so its cache and robots-rules cache actually
    accumulate hits across turns instead of resetting every request.
    """

    def __init__(
        self,
        *,
        contact: str,
        min_interval_seconds: float = 1.0,
        timeout: float = DEFAULT_TIMEOUT,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        cache_size: int = DEFAULT_CACHE_SIZE,
        robots_refresh_seconds: float = DEFAULT_ROBOTS_REFRESH_SECONDS,
        client: httpx.Client | None = None,
        clock: Callable[[], float] | None = None,
        hosts: frozenset[str] | None = None,
    ) -> None:
        # The retail hosts a fetch may reach (CLAUDE.md §5a); `None` leaves it unchecked.
        self._hosts = hosts
        self._fetcher = PacedFetcher(
            user_agent=build_user_agent(contact),
            min_interval_seconds=min_interval_seconds,
            timeout=timeout,
            client=client,
        )
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache_size = cache_size
        self._robots_refresh_seconds = robots_refresh_seconds
        # Ordered so a bounded cache can evict its oldest entry in O(1).
        self._cache: OrderedDict[tuple[str, str | None], tuple[FetchResult, float]] = (
            OrderedDict()
        )
        self._rules_cache: dict[str, tuple[RobotsRules, float]] = {}
        self._now = clock or time.monotonic

    @property
    def user_agent(self) -> str:
        return self._fetcher.user_agent

    def close(self) -> None:
        self._fetcher.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # -- robots --------------------------------------------------------------

    def _rules_for(self, url: str) -> RobotsRules:
        """The origin's rules, or `RulesUnavailable`.

        Rules that cannot be read are a refusal, never permission: a 403 is an
        answer (CLAUDE.md §5a). The predecessor fell back to allow-all here.
        """
        origin = _origin(url)
        now = self._now()
        cached = self._rules_cache.get(origin)
        if cached is not None and (now - cached[1]) < self._robots_refresh_seconds:
            return cached[0]
        rules = self._fetcher.fetch_rules(origin, source=origin)
        self._rules_cache[origin] = (rules, now)
        return rules

    # -- cache -----------------------------------------------------------------

    def _cached(self, key: tuple[str, str | None]) -> FetchResult | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        result, expires_at = entry
        if expires_at <= self._now():
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return result

    def _remember(self, key: tuple[str, str | None], result: FetchResult) -> FetchResult:
        self._cache[key] = (result, self._now() + self._cache_ttl_seconds)
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return result

    # -- fetching --------------------------------------------------------------

    def fetch(self, url: str, *, market_id: str | None = None, fresh: bool = False) -> FetchResult:
        """Fetch `url`, scoped to `market_id` when one is given.

        `market_id` travels as toom's own store-selector cookie (design.md
        decision 2) — nothing here interprets it, it is only ever forwarded.
        `fresh` skips the short per-URL cache for this read (a feedback policy
        asking for verification); pacing and robots rules still apply, and the
        fresh result replaces the cached one.
        """
        key = (url, market_id)
        cached = None if fresh else self._cached(key)
        if cached is not None:
            return cached

        if self._hosts is not None and (urlsplit(url).hostname or "").lower() not in self._hosts:
            return FetchResult(outcome="excluded", url=url, reason="this site is not a permitted retail source")

        try:
            rules = self._rules_for(url)
        except RulesUnavailable as error:
            logger.warning(
                "live fetcher could not obtain robots rules",
                extra={"context": {"origin": _origin(url), "reason": error.reason}},
            )
            return FetchResult(
                outcome="refused",
                url=url,
                reason=f"the retailer's crawling rules could not be read ({error.reason})",
            )
        if not rules.allows(url):
            return FetchResult(
                outcome="excluded",
                url=url,
                reason="excluded by the retailer's published crawling rules",
            )

        cookies = {MARKET_ID_COOKIE: market_id} if market_id else None
        try:
            response = self._fetcher.fetch_auxiliary(url, cookies=cookies)
        except httpx.TimeoutException:
            return FetchResult(
                outcome="timeout",
                url=url,
                reason="the page did not respond within the time budget",
            )
        except httpx.HTTPError as error:
            return FetchResult(
                outcome="unfetchable", url=url, reason=type(error).__name__
            )

        if response.status_code in _REFUSAL_STATUSES:
            return FetchResult(
                outcome="refused", url=url, reason=f"HTTP {response.status_code}"
            )
        if response.is_redirect:
            # Redirects are not followed: the target was never checked against the rules.
            return FetchResult(
                outcome="unfetchable", url=url,
                reason=f"HTTP {response.status_code}: the page moved to {response.headers.get('location', 'another address')}",
            )
        if response.status_code != 200:
            return FetchResult(
                outcome="unfetchable", url=url, reason=f"HTTP {response.status_code}"
            )

        result = FetchResult(
            outcome="ok", url=url, html=response.text, fetched_at=datetime.now(UTC)
        )
        return self._remember(key, result)


def make_live_fetcher(
    *,
    contact: str,
    min_interval_seconds: float = 1.0,
    timeout: float = DEFAULT_TIMEOUT,
    hosts: frozenset[str] | None = None,
) -> LiveFetcher:
    """The fetcher built at startup from settings (pricing-researcher)."""
    return LiveFetcher(
        contact=contact,
        min_interval_seconds=min_interval_seconds,
        timeout=timeout,
        hosts=hosts,
    )


__all__ = [
    "DEFAULT_CACHE_SIZE",
    "DEFAULT_CACHE_TTL_SECONDS",
    "DEFAULT_TIMEOUT",
    "MARKET_ID_COOKIE",
    "FetchResult",
    "LiveFetcher",
    "Outcome",
    "make_live_fetcher",
]
