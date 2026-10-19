"""live-listing-lookup: the honest, paced, gated, cached fetch path."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx
import pytest

from app.ingestion.fetcher import build_user_agent
from app.ingestion.live_fetcher import (
    DEFAULT_CACHE_TTL_SECONDS,
    MARKET_ID_COOKIE,
    LiveFetcher,
)

CONTACT = "https://example.invalid/contact"
ALLOW_ALL = "User-agent: *\nAllow: /"


def make_fetcher(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    clock: Callable[[], float] | None = None,
    **kwargs: object,
) -> tuple[LiveFetcher, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    fetcher = LiveFetcher(
        contact=CONTACT,
        min_interval_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(recording)),
        clock=clock,
        **kwargs,  # type: ignore[arg-type]
    )
    return fetcher, seen


def robots_and(pages: dict[str, httpx.Response], robots_text: str = ALLOW_ALL):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots_text, headers={"content-type": "text/plain"})
        return pages.get(request.url.path, httpx.Response(404, text="not found"))

    return handler


# --- outcomes ------------------------------------------------------------------


def test_a_successful_fetch_carries_html_and_a_fetch_time() -> None:
    fetcher, _ = make_fetcher(
        robots_and({"/p/1": httpx.Response(200, text="<html>ok</html>")})
    )
    with fetcher:
        result = fetcher.fetch("https://toom.de/p/1")

    assert result.outcome == "ok"
    assert result.html == "<html>ok</html>"
    assert result.fetched_at is not None


def test_a_timeout_is_reported_as_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ALLOW_ALL, headers={"content-type": "text/plain"})
        raise httpx.TimeoutException("timed out", request=request)

    fetcher, _ = make_fetcher(handler)
    with fetcher:
        result = fetcher.fetch("https://toom.de/p/1")

    assert result.outcome == "timeout"
    assert result.html is None


@pytest.mark.parametrize("status", [401, 403, 429])
def test_a_refusal_status_is_reported_as_refused(status: int) -> None:
    fetcher, _ = make_fetcher(robots_and({"/p/1": httpx.Response(status, text="no")}))
    with fetcher:
        result = fetcher.fetch("https://toom.de/p/1")

    assert result.outcome == "refused"


def test_a_transport_failure_is_reported_as_unfetchable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ALLOW_ALL, headers={"content-type": "text/plain"})
        raise httpx.ConnectError("refused", request=request)

    fetcher, _ = make_fetcher(handler)
    with fetcher:
        result = fetcher.fetch("https://toom.de/p/1")

    assert result.outcome == "unfetchable"


def test_a_server_error_is_reported_as_unfetchable() -> None:
    fetcher, _ = make_fetcher(robots_and({"/p/1": httpx.Response(500, text="oops")}))
    with fetcher:
        result = fetcher.fetch("https://toom.de/p/1")

    assert result.outcome == "unfetchable"


def test_a_redirect_is_an_answer_and_never_followed() -> None:
    moved = httpx.Response(301, headers={"location": "https://www.bauhaus.info/p/1"})
    fetcher, seen = make_fetcher(robots_and({"/p/1": moved}))
    with fetcher:
        result = fetcher.fetch("https://toom.de/p/1")

    assert result.outcome == "unfetchable"
    assert "https://www.bauhaus.info/p/1" in (result.reason or "")
    assert all(request.url.host == "toom.de" for request in seen)


def test_a_host_outside_the_retail_sources_makes_no_request() -> None:
    fetcher, seen = make_fetcher(robots_and({}), hosts=frozenset({"toom.de"}))
    with fetcher:
        result = fetcher.fetch("https://www.bauhaus.info/p/1")

    assert result.outcome == "excluded"
    assert seen == []


def test_a_robots_excluded_path_makes_no_request() -> None:
    fetcher, seen = make_fetcher(
        robots_and(
            {"/p/excluded": httpx.Response(200, text="should never be seen")},
            robots_text="User-agent: *\nDisallow: /p/excluded",
        )
    )
    with fetcher:
        result = fetcher.fetch("https://toom.de/p/excluded")

    assert result.outcome == "excluded"
    assert all(request.url.path != "/p/excluded" for request in seen)


def test_unavailable_robots_rules_are_a_refusal_and_the_page_is_never_fetched(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rules that cannot be read are not permission: a 403 is an answer. (The
    predecessor fell back to allow-all; pricing-researcher decision 2 reverses it.)"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, text="<html>ok</html>")

    fetcher, seen = make_fetcher(handler)
    with caplog.at_level(logging.WARNING), fetcher:
        result = fetcher.fetch("https://toom.de/p/1")

    assert result.outcome == "refused"
    assert "crawling rules could not be read" in result.reason
    records = [r for r in caplog.records if r.message == "live fetcher could not obtain robots rules"]
    assert len(records) == 1
    assert records[0].context["reason"] == "ConnectError"
    assert [r for r in seen if r.url.path == "/p/1"] == []


# --- caching ---------------------------------------------------------------------


def test_a_cache_hit_makes_no_request_and_keeps_the_original_fetch_time() -> None:
    clock = iter([0.0, 0.0, 1.0, 1.0]).__next__
    fetcher, seen = make_fetcher(
        robots_and({"/p/1": httpx.Response(200, text="v1")}), clock=clock
    )
    with fetcher:
        first = fetcher.fetch("https://toom.de/p/1")
        second = fetcher.fetch("https://toom.de/p/1")

    content_requests = [r for r in seen if r.url.path == "/p/1"]
    assert len(content_requests) == 1, "the second lookup must be served from cache"
    assert second.fetched_at == first.fetched_at


def test_a_cache_entry_expires_after_its_ttl() -> None:
    expired = DEFAULT_CACHE_TTL_SECONDS + 1
    times = iter([0.0, 0.0, expired, expired, expired])
    fetcher, seen = make_fetcher(
        robots_and({"/p/1": httpx.Response(200, text="v1")}), clock=times.__next__
    )
    with fetcher:
        fetcher.fetch("https://toom.de/p/1")
        fetcher.fetch("https://toom.de/p/1")

    content_requests = [r for r in seen if r.url.path == "/p/1"]
    assert len(content_requests) == 2, "an expired entry must be re-fetched"


def test_the_cache_is_keyed_on_url_and_market_id() -> None:
    fetcher, seen = make_fetcher(robots_and({"/p/1": httpx.Response(200, text="v1")}))
    with fetcher:
        fetcher.fetch("https://toom.de/p/1", market_id="3648")
        fetcher.fetch("https://toom.de/p/1", market_id="3646")

    content_requests = [r for r in seen if r.url.path == "/p/1"]
    assert len(content_requests) == 2, "a different store must not be served the other's cache"


def test_the_cache_is_bounded() -> None:
    fetcher, seen = make_fetcher(
        robots_and({f"/p/{n}": httpx.Response(200, text="v") for n in range(300)}),
        cache_size=5,
    )
    with fetcher:
        for n in range(300):
            fetcher.fetch(f"https://toom.de/p/{n}")
        fetcher.fetch("https://toom.de/p/0")

    content_requests = [r for r in seen if r.url.path == "/p/0"]
    assert len(content_requests) == 2, "the oldest entry must have been evicted"


# --- robots refresh -----------------------------------------------------------


def test_robots_rules_are_fetched_once_within_the_refresh_window() -> None:
    times = iter([0.0, 0.0, 10.0, 10.0])
    fetcher, seen = make_fetcher(
        robots_and({"/p/1": httpx.Response(200, text="a"), "/p/2": httpx.Response(200, text="b")}),
        clock=times.__next__,
    )
    with fetcher:
        fetcher.fetch("https://toom.de/p/1")
        fetcher.fetch("https://toom.de/p/2")

    robots_requests = [r for r in seen if r.url.path == "/robots.txt"]
    assert len(robots_requests) == 1


def test_robots_rules_refresh_after_an_hour() -> None:
    times = iter([0.0, 0.0, 3700.0, 3700.0])
    fetcher, seen = make_fetcher(
        robots_and({"/p/1": httpx.Response(200, text="a"), "/p/2": httpx.Response(200, text="b")}),
        clock=times.__next__,
    )
    with fetcher:
        fetcher.fetch("https://toom.de/p/1")
        fetcher.fetch("https://toom.de/p/2")

    robots_requests = [r for r in seen if r.url.path == "/robots.txt"]
    assert len(robots_requests) == 2


# --- pacing ---------------------------------------------------------------------


def test_successive_fetches_to_one_host_are_paced() -> None:
    # `make_fetcher` always sets `min_interval_seconds=0`, so pacing is
    # exercised with a fetcher built directly here instead.
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ALLOW_ALL, headers={"content-type": "text/plain"})
        return httpx.Response(200, text="ok")

    paced = LiveFetcher(
        contact=CONTACT,
        min_interval_seconds=0.25,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    started = time.monotonic()
    with paced:
        paced.fetch("https://toom.de/p/1")
        paced.fetch("https://toom.de/p/2")
    elapsed = time.monotonic() - started

    assert elapsed >= 0.25


# --- identity and the market cookie --------------------------------------------


def test_the_user_agent_matches_ingestions() -> None:
    fetcher, seen = make_fetcher(robots_and({"/p/1": httpx.Response(200, text="a")}))
    with fetcher:
        fetcher.fetch("https://toom.de/p/1")

    content_request = next(r for r in seen if r.url.path == "/p/1")
    assert content_request.headers["user-agent"] == build_user_agent(CONTACT)
    assert fetcher.user_agent == build_user_agent(CONTACT)


def test_the_market_cookie_is_sent_only_when_a_store_is_given() -> None:
    fetcher, seen = make_fetcher(
        robots_and({"/p/1": httpx.Response(200, text="a"), "/p/2": httpx.Response(200, text="b")})
    )
    with fetcher:
        fetcher.fetch("https://toom.de/p/1", market_id="3646")
        fetcher.fetch("https://toom.de/p/2")

    scoped = next(r for r in seen if r.url.path == "/p/1")
    unscoped = next(r for r in seen if r.url.path == "/p/2")
    assert scoped.headers.get("cookie") == f"{MARKET_ID_COOKIE}=3646"
    assert "cookie" not in unscoped.headers


def test_a_fresh_read_bypasses_the_cache_once_and_refreshes_it() -> None:
    """feedback-learning: `verify_first` asks for fresh verification."""
    bodies = iter(["v1", "v2"])
    fetcher, seen = make_fetcher(
        lambda r: httpx.Response(200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"})
        if r.url.path == "/robots.txt"
        else httpx.Response(200, text=next(bodies))
    )
    with fetcher:
        fetcher.fetch("https://toom.de/p/1")
        fresh = fetcher.fetch("https://toom.de/p/1", fresh=True)
        cached = fetcher.fetch("https://toom.de/p/1")

    assert len([r for r in seen if r.url.path == "/p/1"]) == 2
    assert fresh.html == "v2" and cached.html == "v2"
