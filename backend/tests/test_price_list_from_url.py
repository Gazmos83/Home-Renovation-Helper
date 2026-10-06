"""price-list: a pasted toom URL becomes a captured entry in one step."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.pricing import capture
from app.pricing.errors import Refused
from app.pricing.product_page import read_product
from tests.pricing_helpers import clean_pricing, fixture, make_fetcher

SOURCES = frozenset({"toom"})
PRODUCT = "/p/hartschaumplatte-eps-040-50-x-100-cm/3150333"
SIEB = "/p/siebdruckplatte-2500-x-1250-x-15-mm/7100576"
LISTING = "/c/bauen-renovieren/baustoffe/daemmung/hartschaumplatten"


@pytest.fixture
def session(migrated_database: str):
    from app.db.session import make_engine

    engine = make_engine(migrated_database)
    clean_pricing(engine)
    with Session(engine) as s:
        yield s
        s.rollback()
    clean_pricing(engine)
    engine.dispose()


def go(session, pages, url, **kw):
    fetcher, seen = make_fetcher(pages)
    with fetcher:
        result = capture.capture_from_url(
            session, fetcher, url, key=kw.pop("key", "foam:50x100"), category=kw.pop("category", "finish"),
            retail_sources=SOURCES, **kw,
        )
    return result, seen


def test_a_pasted_url_makes_a_captured_entry_with_its_price_and_source(session) -> None:
    result, _ = go(session, {PRODUCT: (200, fixture("toom_product_3150333.html"))}, f"https://toom.de{PRODUCT}")
    assert result.outcome == "ok"
    entry = result.entry
    assert (entry.provenance, entry.base_cents, entry.unit) == ("captured", 3649, "per_piece")
    assert entry.source_url == f"https://toom.de{PRODUCT}" and entry.captured_at is not None
    assert entry.label == "Hartschaumplatte EPS 040 50 x 100 cm"


def test_a_panel_takes_its_sheet_size_from_the_page(session) -> None:
    html = fixture("toom_product_3150333.html")
    result, _ = go(session, {PRODUCT: (200, html)}, f"https://toom.de{PRODUCT}", key="panel:foam", category="panel")
    entry = result.entry
    assert (entry.sheet_length_mm, entry.sheet_width_mm, entry.thickness_mm) == (1000, 500, 100)


def test_the_page_text_is_indexed_in_the_same_step(session) -> None:
    indexed: list[tuple[str, str, str]] = []
    go(
        session, {PRODUCT: (200, fixture("toom_product_3150333.html"))}, f"https://toom.de{PRODUCT}",
        indexer=lambda _s, url, title, text: indexed.append((url, title, text)),
    )
    assert indexed and indexed[0][0].endswith(PRODUCT) and "Wärmedämmung" in indexed[0][2]


def test_a_price_missing_from_the_page_is_read_from_the_category_listing(session) -> None:
    page = fixture("toom_product_3150333.html")
    page = page.replace('window.__PRODUCT_STATE__ = {"price": "36,49", "availability": "in_stock"};', "")
    crumb = (
        '<script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":['
        f'{{"@type":"ListItem","position":1,"item":{{"@id":"https://toom.de{LISTING}","name":"Hartschaumplatten"}}}},'
        f'{{"@type":"ListItem","position":2,"item":{{"@id":"https://toom.de{PRODUCT}","name":"x"}}}}]}}</script>'
    )
    page = page.replace("</head>", crumb + "</head>")
    result, seen = go(
        session, {PRODUCT: (200, page), LISTING: (200, fixture("toom_listing_hartschaumplatten.html"))},
        f"https://toom.de{PRODUCT}",
    )
    assert result.outcome == "ok" and result.entry.base_cents is not None
    assert any(r.url.path == LISTING for r in seen)


def test_a_price_found_nowhere_creates_nothing_and_says_what_is_missing(session) -> None:
    html = fixture("toom_product_siebdruckplatte_7100576.html")
    result, _ = go(session, {SIEB: (200, html)}, f"https://toom.de{SIEB}", key="panel:sieb", category="panel")
    assert result.outcome == "unreadable" and result.entry is None
    assert "no price could be read" in result.reason
    from app.pricing import price_list
    from app.pricing.errors import NotFound

    with pytest.raises(NotFound):
        price_list.get_entry(session, "panel:sieb")


def test_another_retailer_is_refused_naming_the_host_and_nothing_is_fetched(session) -> None:
    fetcher, seen = make_fetcher({})
    with fetcher, pytest.raises(Refused, match="www.bauhaus.info is not a permitted source"):
        capture.capture_from_url(
            session, fetcher, "https://www.bauhaus.info/p/x/1", key="x", category="finish", retail_sources=SOURCES
        )
    assert seen == []


@pytest.mark.parametrize("status", [401, 403, 429])
def test_a_refusal_is_reported_and_creates_nothing(session, status) -> None:
    result, seen = go(session, {PRODUCT: (status, "denied")}, f"https://toom.de{PRODUCT}")
    assert result.outcome == "refused" and str(status) in result.reason and result.entry is None
    # Asked once, under the service's own identity; never retried.
    assert [r.url.path for r in seen].count(PRODUCT) == 1
    assert all("HomeRenovationAgentsBot" in r.headers["user-agent"] for r in seen)


def test_robots_disallowing_the_page_creates_nothing_and_does_not_fetch_it(session) -> None:
    fetcher, seen = make_fetcher({PRODUCT: (200, "x")}, robots="User-agent: *\nDisallow: /p/\n")
    with fetcher:
        result = capture.capture_from_url(
            session, fetcher, f"https://toom.de{PRODUCT}", key="k", category="finish", retail_sources=SOURCES
        )
    assert result.outcome == "excluded" and result.entry is None
    assert [r for r in seen if r.url.path == PRODUCT] == []


def test_a_url_that_is_not_a_product_page_is_unreadable(session) -> None:
    result, seen = go(session, {}, "https://toom.de/c/holz")
    assert result.outcome == "unreadable" and "not a toom product page" in result.reason
    assert seen == []


def test_the_read_values_are_plain_facts_not_guesses() -> None:
    fetcher, _ = make_fetcher({SIEB: (200, fixture("toom_product_siebdruckplatte_7100576.html"))})
    with fetcher:
        read = read_product(fetcher, f"https://toom.de{SIEB}")
    assert (read.sheet_length_mm, read.sheet_width_mm, read.thickness_mm) == (2500, 1250, 15)
    assert read.price_cents is None and read.missing == ("price",)
