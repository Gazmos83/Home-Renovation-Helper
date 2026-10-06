"""retail-ingestion: published rules are obtained, parsed, and obeyed."""

from __future__ import annotations

import httpx
import pytest

from app.ingestion.fetcher import PacedFetcher, build_user_agent
from app.ingestion.robots import RulesUnavailable, parse_rules

UA = build_user_agent("https://example.invalid/contact")

# Trimmed from toom's real robots.txt: the query-parameter patterns are the
# ones urllib.robotparser silently fails to match.
TOOM_RULES = """
User-agent: *

Disallow: /typo3/
Disallow: /*?SID=
Disallow: /s/*accid=

User-agent: bingbot
crawl-delay: 30
Disallow: /

Sitemap: https://static.toom.de/sitemap/sitemap.xml
"""


def rules():
    return parse_rules(TOOM_RULES, user_agent=UA)


def test_a_path_no_rule_names_is_allowed() -> None:
    assert rules().allows("https://toom.de/c/bauen-renovieren/holz") is True


def test_a_disallowed_prefix_is_excluded() -> None:
    assert rules().allows("https://toom.de/typo3/index.php") is False


def test_a_wildcard_query_pattern_is_excluded() -> None:
    """The case stdlib gets wrong: it would report this as allowed."""
    assert rules().allows("https://toom.de/c/holz?SID=abc123") is False
    assert rules().allows("https://toom.de/s/suche?accid=9") is False


def test_rules_for_another_agent_do_not_apply_to_us() -> None:
    """bingbot is disallowed everything; that group is not ours."""
    assert rules().allows("https://toom.de/anything") is True


def test_sitemaps_are_collected() -> None:
    assert rules().sitemaps == ("https://static.toom.de/sitemap/sitemap.xml",)


def test_the_longest_matching_rule_wins() -> None:
    parsed = parse_rules(
        "User-agent: *\nDisallow: /printing/\nAllow: /printing/consumables/",
        user_agent=UA,
    )
    assert parsed.allows("https://oki.com/printing/drivers") is False
    assert parsed.allows("https://oki.com/printing/consumables/toner") is True


def test_end_anchored_pattern_matches_only_the_end() -> None:
    parsed = parse_rules("User-agent: *\nDisallow: /*.pdf$", user_agent=UA)
    assert parsed.allows("https://toom.de/a/manual.pdf") is False
    assert parsed.allows("https://toom.de/a/manual.pdf.html") is True


def test_excluded_reports_every_blocked_url() -> None:
    urls = ["https://toom.de/ok", "https://toom.de/typo3/x", "https://toom.de/y?SID=1"]
    assert rules().excluded(urls) == [
        "https://toom.de/typo3/x",
        "https://toom.de/y?SID=1",
    ]


# --- retrieval --------------------------------------------------------------


def fetcher_over(handler) -> PacedFetcher:
    transport = httpx.MockTransport(handler)
    return PacedFetcher(
        user_agent=UA,
        min_interval_seconds=0,
        client=httpx.Client(transport=transport, follow_redirects=True),
    )


def test_rules_are_retrieved_and_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/robots.txt"
        return httpx.Response(
            200, text=TOOM_RULES, headers={"content-type": "text/plain"}
        )

    with fetcher_over(handler) as fetcher:
        parsed = fetcher.fetch_rules("https://toom.de", source="toom")

    assert parsed.allows("https://toom.de/typo3/x") is False


def test_a_source_refusing_its_rules_is_reported_not_crashed() -> None:
    """bauhaus.info and kaufland.de both do exactly this."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, html="<title>Sicherheitsprüfung</title>")

    with fetcher_over(handler) as fetcher, pytest.raises(RulesUnavailable) as caught:
        fetcher.fetch_rules("https://www.bauhaus.info", source="bauhaus")

    assert caught.value.source == "bauhaus"
    assert "403" in caught.value.reason


def test_a_challenge_page_served_as_200_is_still_a_refusal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<html>verify</html>", headers={"content-type": "text/html"}
        )

    with fetcher_over(handler) as fetcher, pytest.raises(RulesUnavailable) as caught:
        fetcher.fetch_rules("https://www.kaufland.de", source="kaufland")

    assert "text/html" in caught.value.reason
