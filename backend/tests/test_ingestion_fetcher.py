"""retail-ingestion: honest identification, pacing, and the page budget."""

from __future__ import annotations

import time

import httpx

from app.ingestion.fetcher import APP_NAME, PacedFetcher, build_user_agent

CONTACT = "https://example.invalid/contact"
UA = build_user_agent(CONTACT)


def recording_fetcher(**kwargs) -> tuple[PacedFetcher, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="<html><body>ok</body></html>")

    fetcher = PacedFetcher(
        user_agent=UA,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        **kwargs,
    )
    return fetcher, seen


def test_the_identifier_names_the_application_and_a_contact() -> None:
    assert APP_NAME in UA
    assert CONTACT in UA


def test_every_request_carries_the_honest_identifier() -> None:
    fetcher, seen = recording_fetcher(min_interval_seconds=0)
    with fetcher:
        for path in ("/a", "/b", "/c"):
            fetcher.fetch_page(f"https://toom.de{path}")

    assert len(seen) == 3
    assert {request.headers["user-agent"] for request in seen} == {UA}


def test_no_request_impersonates_a_browser() -> None:
    """A source refusing the honest identity must not be retried as a browser."""
    fetcher, seen = recording_fetcher(min_interval_seconds=0)
    with fetcher:
        fetcher.fetch_page("https://toom.de/a")

    agent = seen[0].headers["user-agent"]
    for impersonation in ("Mozilla", "AppleWebKit", "Chrome", "Safari"):
        assert impersonation not in agent


def test_successive_requests_to_one_host_are_paced() -> None:
    fetcher, _ = recording_fetcher(min_interval_seconds=0.25)
    started = time.monotonic()
    with fetcher:
        fetcher.fetch_page("https://toom.de/a")
        fetcher.fetch_page("https://toom.de/b")
    elapsed = time.monotonic() - started

    assert elapsed >= 0.25, "the second request must wait its turn"


def test_pacing_is_per_host() -> None:
    """A different host has its own clock; one slow site must not stall another."""
    fetcher, _ = recording_fetcher(min_interval_seconds=0.25)
    started = time.monotonic()
    with fetcher:
        fetcher.fetch_page("https://toom.de/a")
        fetcher.fetch_page("https://static.toom.de/b")
    elapsed = time.monotonic() - started

    assert elapsed < 0.25


def test_the_budget_stops_a_run_without_raising() -> None:
    fetcher, seen = recording_fetcher(min_interval_seconds=0, page_budget=2)
    urls = [f"https://toom.de/{n}" for n in range(10)]

    with fetcher:
        fetched = list(fetcher.fetch_within_budget(urls))

    assert len(fetched) == 2
    assert len(seen) == 2, "no request is made once the budget is spent"
    assert fetcher.pages_fetched == 2


def test_a_run_under_budget_fetches_everything() -> None:
    fetcher, _ = recording_fetcher(min_interval_seconds=0, page_budget=50)
    urls = [f"https://toom.de/{n}" for n in range(4)]

    with fetcher:
        assert len(list(fetcher.fetch_within_budget(urls))) == 4


def test_fetching_rules_is_not_charged_against_the_page_budget() -> None:
    """Reading the rules must never be crowded out by the budget."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        body = "User-agent: *\nDisallow: /nope"
        return httpx.Response(200, text=body, headers={"content-type": "text/plain"})

    fetcher = PacedFetcher(
        user_agent=UA,
        min_interval_seconds=0,
        page_budget=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with fetcher:
        fetcher.fetch_rules("https://toom.de", source="toom")
        fetcher.fetch_page("https://toom.de/a")

    assert fetcher.pages_fetched == 1
    assert seen == ["/robots.txt", "/a"]
