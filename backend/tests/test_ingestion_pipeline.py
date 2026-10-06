"""retail-ingestion: gating, idempotency, failure isolation, run reporting.

These run against the real database but never the network: responses come
from a mock transport, and the embedder is stubbed so the suite does not load
a 2GB model to prove that a 404 does not end a run.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.chunk_store import count_chunks, stored_page_contents
from app.db.models import EMBEDDING_DIMENSIONS
from app.ingestion import pipeline as pipeline_module
from app.ingestion.extract import chunk_text, extract_text
from app.ingestion.fetcher import PacedFetcher, build_user_agent
from app.ingestion.pipeline import SourceNotEnabled, ingest_source

pytestmark = pytest.mark.usefixtures("clean_chunks")

ROBOTS = "User-agent: *\nDisallow: /typo3/\n"

PAGE = """
<html><body>
<h1>Möbelbauplatte beschichtet</h1>
<p>2630 x 400 x 19 mm, weiß beschichtet, 20,99 Euro pro Platte.</p>
<p>Geeignet für Regalböden und den Möbelbau im Innenbereich.</p>
</body></html>
"""

REVISED = PAGE.replace("20,99", "22,49")

# Long enough to chunk several times, so a change to one part of the page can
# be told apart from a change to the whole page.
_PARAGRAPHS = [
    f"<p>Absatz {index}: " + ("Möbelbauplatte beschichtet, 19 mm stark. " * 12) + "</p>"
    for index in range(6)
]
LONG_PAGE = "<html><body><h1>Plattenübersicht</h1>" + "".join(_PARAGRAPHS) + "</body></html>"
LONG_PAGE_REVISED = LONG_PAGE.replace("Absatz 5:", "Absatz 5 (neu, 22,49 Euro):")
SHORT_PAGE = "<html><body><h1>Plattenübersicht</h1>" + _PARAGRAPHS[0] + "</body></html>"

HOLZ = "https://toom.de/c/bauen-renovieren/holz/moebelbauplatten"
BAUSTOFFE = "https://toom.de/c/bauen-renovieren/baustoffe/daemmung"
EXCLUDED = "https://toom.de/typo3/secret"


@pytest.fixture(autouse=True)
def stub_embedder(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[list[str]]]:
    """Deterministic vectors of the right width, without loading the model.

    Yields the record of every batch embedded, so a test can prove not just
    what was stored but what the model was — and was not — asked to do.
    """
    embedded: list[list[str]] = []

    def fake_embed(texts, **_):
        embedded.append(list(texts))
        return [
            [float((index + position) % 7) / 7.0 for position in range(EMBEDDING_DIMENSIONS)]
            for index, _ in enumerate(texts)
        ]

    monkeypatch.setattr(pipeline_module, "embed", fake_embed)
    yield embedded


def make_fetcher(pages: dict[str, str], *, budget: int = 50) -> PacedFetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(
                200, text=ROBOTS, headers={"content-type": "text/plain"}
            )
        body = pages.get(url)
        if body is None:
            return httpx.Response(404, text="not found")
        return httpx.Response(200, text=body)

    return PacedFetcher(
        user_agent=build_user_agent("https://example.invalid"),
        min_interval_seconds=0,
        page_budget=budget,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.fixture
def toom_settings(test_database_url: str) -> Settings:
    return Settings(
        database_url=test_database_url,
        owner_email="owner@example.com",
        owner_password="an-initial-owner-password",
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        retail_sources="toom",
        _env_file=None,
    )


# --- gating -----------------------------------------------------------------


def test_a_disabled_source_is_refused_without_any_request(
    db_session: Session, toom_settings: Settings
) -> None:
    """Configuration decides; ingestion must not reach out to check."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, text=ROBOTS)

    fetcher = PacedFetcher(
        user_agent="x",
        min_interval_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(SourceNotEnabled) as caught:
        ingest_source(db_session, toom_settings, "kaufland", fetcher=fetcher)

    assert "kaufland" in str(caught.value)
    assert requested == [], "a disabled source must not be contacted"


# --- rules ------------------------------------------------------------------


def test_a_refusing_source_is_reported_not_raised(
    db_session: Session, toom_settings: Settings
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="<html>Sicherheitsprüfung</html>")

    fetcher = PacedFetcher(
        user_agent="x",
        min_interval_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    report = ingest_source(db_session, toom_settings, "toom", fetcher=fetcher)

    assert report.refused is not None
    assert "403" in report.refused
    assert report.succeeded is False
    assert count_chunks(db_session) == 0


def test_a_url_the_rules_exclude_is_skipped_not_failed(
    db_session: Session, toom_settings: Settings
) -> None:
    fetcher = make_fetcher({HOLZ: PAGE})

    report = ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ, EXCLUDED], fetcher=fetcher
    )

    assert report.skipped_by_rule == [EXCLUDED]
    assert report.failures == []
    assert report.pages_ingested == 1


# --- idempotency ------------------------------------------------------------


def test_a_second_run_over_unchanged_pages_does_not_grow_the_corpus(
    db_session: Session, toom_settings: Settings
) -> None:
    first = ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE})
    )
    after_first = count_chunks(db_session)

    second = ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE})
    )

    assert after_first == count_chunks(db_session)
    assert first.created > 0 and first.updated == 0 and first.unchanged == 0
    assert second.created == 0 and second.updated == 0, (
        "a re-run over identical text must neither create nor rewrite"
    )
    assert second.unchanged == after_first, "every chunk was seen again, unchanged"


def test_an_unchanged_page_is_not_re_embedded(
    db_session: Session, toom_settings: Settings, stub_embedder: list[list[str]]
) -> None:
    """The model is the expensive step; a page that did not change must not pay it."""
    ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE})
    )
    assert len(stub_embedder) == 1, "the first run embeds the page"
    stub_embedder.clear()

    ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE})
    )

    assert stub_embedder == [], "an unchanged page must make zero embedding calls"


def test_an_unchanged_rerun_still_advances_the_timestamp(
    db_session: Session, toom_settings: Settings
) -> None:
    """Freshness is recorded separately from content: "seen again" must be visible."""
    ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE})
    )
    before = db_session.execute(
        text("SELECT max(scraped_at) FROM chunks WHERE url = :url"), {"url": HOLZ}
    ).scalar_one()

    ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE})
    )
    after = db_session.execute(
        text("SELECT max(scraped_at) FROM chunks WHERE url = :url"), {"url": HOLZ}
    ).scalar_one()

    assert after > before


def test_a_revised_page_re_embeds_only_the_chunks_that_changed(
    db_session: Session, toom_settings: Settings, stub_embedder: list[list[str]]
) -> None:
    original = chunk_text(extract_text(LONG_PAGE))
    revised = chunk_text(extract_text(LONG_PAGE_REVISED))
    assert len(original) > 1, "the fixture must span several chunks to mean anything"
    assert len(original) == len(revised)
    expected_changed = [
        new for old, new in zip(original, revised, strict=True) if old != new
    ]
    assert 0 < len(expected_changed) < len(revised)

    ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: LONG_PAGE})
    )
    stub_embedder.clear()

    report = ingest_source(
        db_session,
        toom_settings,
        "toom",
        urls=[HOLZ],
        fetcher=make_fetcher({HOLZ: LONG_PAGE_REVISED}),
    )

    assert [piece for batch in stub_embedder for piece in batch] == expected_changed
    assert report.updated == len(expected_changed)
    assert report.unchanged == len(revised) - len(expected_changed)
    assert report.created == 0
    assert stored_page_contents(db_session, HOLZ) == dict(enumerate(revised))


def test_a_page_that_shrinks_drops_its_obsolete_tail(
    db_session: Session, toom_settings: Settings
) -> None:
    """Writing only changed chunks must not keep the ones the page no longer has."""
    ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: LONG_PAGE})
    )
    long_count = count_chunks(db_session, url=HOLZ)

    ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: SHORT_PAGE})
    )

    short_pieces = chunk_text(extract_text(SHORT_PAGE))
    assert 0 < len(short_pieces) < long_count
    assert count_chunks(db_session, url=HOLZ) == len(short_pieces)
    assert stored_page_contents(db_session, HOLZ) == dict(enumerate(short_pieces))


def test_revised_content_replaces_the_stored_text(
    db_session: Session, toom_settings: Settings
) -> None:
    ingest_source(
        db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE})
    )
    ingest_source(
        db_session,
        toom_settings,
        "toom",
        urls=[HOLZ],
        fetcher=make_fetcher({HOLZ: REVISED}),
    )

    stored = db_session.execute(
        text("SELECT content FROM chunks WHERE url = :url"), {"url": HOLZ}
    ).scalars().all()
    joined = "\n".join(stored)

    assert "22,49" in joined
    assert "20,99" not in joined, "no superseded copy may remain"


# --- failure isolation ------------------------------------------------------


def test_one_failing_page_does_not_end_the_run(
    db_session: Session, toom_settings: Settings
) -> None:
    missing = "https://toom.de/c/bauen-renovieren/holz/gone"
    fetcher = make_fetcher({HOLZ: PAGE, BAUSTOFFE: PAGE})

    report = ingest_source(
        db_session,
        toom_settings,
        "toom",
        urls=[HOLZ, missing, BAUSTOFFE],
        fetcher=fetcher,
    )

    assert report.pages_ingested == 2
    assert [failure.url for failure in report.failures] == [missing]
    assert report.failures[0].reason
    assert report.succeeded is True


def test_a_run_where_every_page_fails_reports_failure(
    db_session: Session, toom_settings: Settings
) -> None:
    """An empty corpus must not be reported as a successful run."""
    report = ingest_source(
        db_session,
        toom_settings,
        "toom",
        urls=[HOLZ, BAUSTOFFE],
        fetcher=make_fetcher({}),
    )

    assert report.pages_ingested == 0
    assert len(report.failures) == 2
    assert report.succeeded is False


# --- budget -----------------------------------------------------------------


def test_the_page_budget_bounds_a_run(
    db_session: Session, toom_settings: Settings
) -> None:
    urls = [f"https://toom.de/c/bauen-renovieren/holz/p{n}" for n in range(6)]
    fetcher = make_fetcher({url: PAGE for url in urls}, budget=2)

    report = ingest_source(db_session, toom_settings, "toom", urls=urls, fetcher=fetcher)

    assert report.pages_ingested == 2
    assert report.budget_reached is True
    assert report.succeeded is True, "the budget ending a run is not a failure"


# --- sitemap discovery ------------------------------------------------------

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://toom.de/c/bauen-renovieren/holz/osb-platten</loc></url>
  <url><loc>https://toom.de/c/bauen-renovieren/holz/multiplexplatten</loc></url>
  <url><loc>https://toom.de/c/garten-freizeit/grills</loc></url>
  <url><loc>https://toom.de/hilfe/versand/</loc></url>
  <url><loc>https://toom.de/typo3/admin</loc></url>
</urlset>
"""


def discovery_fetcher(budget: int) -> PacedFetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/robots.txt"):
            return httpx.Response(
                200, text=ROBOTS, headers={"content-type": "text/plain"}
            )
        return httpx.Response(
            200, text=SITEMAP, headers={"content-type": "application/xml"}
        )

    return PacedFetcher(
        user_agent="x",
        min_interval_seconds=0,
        page_budget=budget,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_discovery_keeps_only_relevant_allowed_urls() -> None:
    from app.ingestion.pipeline import discover_urls
    from app.ingestion.robots import parse_rules
    from app.ingestion.sources import TOOM

    fetcher = discovery_fetcher(budget=50)
    rules = parse_rules(ROBOTS, user_agent="x")

    with fetcher:
        allowed, excluded = discover_urls(fetcher, TOOM, rules, limit=50)

    # Grills match no include pattern; typo3 matches none either, so it is
    # filtered before the rules ever see it.
    assert "https://toom.de/c/garten-freizeit/grills" not in allowed
    assert "https://toom.de/typo3/admin" not in allowed
    assert "https://toom.de/c/bauen-renovieren/holz/osb-platten" in allowed
    assert "https://toom.de/hilfe/versand/" in allowed
    assert excluded == []


def test_discovery_respects_the_limit() -> None:
    from app.ingestion.pipeline import discover_urls
    from app.ingestion.robots import parse_rules
    from app.ingestion.sources import TOOM

    fetcher = discovery_fetcher(budget=50)
    rules = parse_rules(ROBOTS, user_agent="x")

    with fetcher:
        allowed, _ = discover_urls(fetcher, TOOM, rules, limit=2)

    assert len(allowed) == 2


def test_discovery_reports_urls_the_rules_exclude() -> None:
    """A relevant URL the rules forbid is skipped by rule, not silently dropped."""
    from app.ingestion.pipeline import discover_urls
    from app.ingestion.robots import parse_rules
    from app.ingestion.sources import TOOM

    fetcher = discovery_fetcher(budget=50)
    rules = parse_rules(
        "User-agent: *\nDisallow: /c/bauen-renovieren/holz/osb-platten", user_agent="x"
    )

    with fetcher:
        allowed, excluded = discover_urls(fetcher, TOOM, rules, limit=50)

    assert excluded == ["https://toom.de/c/bauen-renovieren/holz/osb-platten"]
    assert "https://toom.de/c/bauen-renovieren/holz/osb-platten" not in allowed


def test_a_transport_failure_costs_one_page_not_the_run(
    db_session: Session, toom_settings: Settings
) -> None:
    """Regression: a real run died when DNS failed part-way through.

    `fetch_page` is called as the generator advances, so the transport error
    was raised outside the per-page try block and ended the crawl. The spec
    requires a page that cannot be *fetched* to be isolated like any other.
    """
    dead = "https://toom.de/c/bauen-renovieren/holz/unreachable"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(
                200, text=ROBOTS, headers={"content-type": "text/plain"}
            )
        if url == dead:
            raise httpx.ConnectError("[Errno -3] Temporary failure in name resolution")
        return httpx.Response(200, text=PAGE)

    fetcher = PacedFetcher(
        user_agent="x",
        min_interval_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    report = ingest_source(
        db_session,
        toom_settings,
        "toom",
        urls=[HOLZ, dead, BAUSTOFFE],
        fetcher=fetcher,
    )

    assert report.pages_ingested == 2, "the pages after the failure must still run"
    assert [failure.url for failure in report.failures] == [dead]
    assert "ConnectError" in report.failures[0].reason
    assert report.succeeded is True


# --- grouped coverage and content hashes (retail-ingestion, 2026-09-23) --------------

PRODUCT = "https://toom.de/p/siebdruckplatte-18-mm-birke/1234567"
GUIDE = "https://toom.de/selbermachen/bad-sanitaer/fliesen/fliesen-legen/"
UNRELATED_PRODUCT = "https://toom.de/p/gartengrill-kugel/7654321"


def test_product_and_guide_urls_are_grouped_and_categorised() -> None:
    from app.ingestion.sources import TOOM

    assert (TOOM.group_of(PRODUCT), TOOM.categorise(PRODUCT)) == ("products", "product")
    assert (TOOM.group_of(GUIDE), TOOM.categorise(GUIDE)) == ("guides_tiling", "guide")
    assert TOOM.group_of("https://toom.de/selbermachen/werkstatt-maschinen/heimwerkerpraxis/x/") == "guides_workshop"
    assert TOOM.group_of("https://toom.de/hilfe/versand/") == "policy"
    assert TOOM.group_of(UNRELATED_PRODUCT) is None, "only reviewed product keywords"


def test_the_budget_is_shared_and_an_exhausted_group_yields_to_others() -> None:
    from app.ingestion.pipeline import _allocate

    by_group = {
        "policy": ["h1"],
        "categories": [f"c{i}" for i in range(20)],
        "products": [f"p{i}" for i in range(40)],
        "guides_tiling": [],
    }
    shares = {"policy": 0.1, "categories": 0.3, "products": 0.4, "guides_tiling": 0.2}

    selected = _allocate(by_group, shares, 10)

    assert len(selected) == 10
    assert "h1" in selected
    assert sum(1 for url in selected if url.startswith("c")) >= 3
    assert sum(1 for url in selected if url.startswith("p")) >= 4
    assert selected[:3] == ["h1", "c0", "p0"], "groups are interleaved"


def _grouped_sitemap_fetcher(robots: str = ROBOTS) -> PacedFetcher:
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{HOLZ}</loc></url>
  <url><loc>{PRODUCT}</loc></url>
  <url><loc>{UNRELATED_PRODUCT}</loc></url>
  <url><loc>{GUIDE}</loc></url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text=robots, headers={"content-type": "text/plain"})
        if "sitemap" in url:
            return httpx.Response(200, text=sitemap, headers={"content-type": "application/xml"})
        if url in (HOLZ, PRODUCT, GUIDE):
            return httpx.Response(200, text=PAGE.replace("Möbelbauplatte", url.rsplit("/", 2)[-2]))
        return httpx.Response(404, text="not found")

    return PacedFetcher(
        user_agent="x",
        min_interval_seconds=0,
        page_budget=50,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_a_run_reports_counts_per_group_and_names_the_gaps(
    db_session: Session, toom_settings: Settings
) -> None:
    db_session.execute(text("TRUNCATE TABLE chunks"))
    db_session.commit()

    report = ingest_source(db_session, toom_settings, "toom", fetcher=_grouped_sitemap_fetcher())

    assert report.groups["products"].discovered == 1
    assert report.groups["products"].fetched == 1 and report.groups["products"].changed == 1
    assert report.groups["guides_tiling"].fetched == 1
    assert report.groups["categories"].fetched == 1
    assert "guides_workshop" in report.gaps and "products" not in report.gaps
    assert "gaps (no usable page)" in report.summary()
    categories = dict(db_session.execute(text("SELECT url, category FROM chunks")).all())
    assert categories[PRODUCT] == "product" and categories[GUIDE] == "guide"


def test_a_disallowed_product_page_is_reported_excluded(
    db_session: Session, toom_settings: Settings
) -> None:
    report = ingest_source(
        db_session, toom_settings, "toom",
        fetcher=_grouped_sitemap_fetcher("User-agent: *\nDisallow: /p/\n"),
    )

    assert PRODUCT in report.skipped_by_rule
    assert report.groups["products"].excluded == 1 and report.groups["products"].fetched == 0


def test_hashes_skip_unchanged_pages_and_track_changed_ones(
    db_session: Session, toom_settings: Settings, stub_embedder: list[list[str]]
) -> None:
    from app.db.chunk_store import content_hash

    db_session.execute(text("TRUNCATE TABLE chunks"))
    db_session.commit()
    ingest_source(db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE}))
    first = db_session.execute(text("SELECT content, content_hash FROM chunks WHERE url = :u"), {"u": HOLZ}).all()
    assert all(row.content_hash == content_hash(row.content) for row in first)
    batches = len(stub_embedder)

    rerun = ingest_source(db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE}))
    assert len(stub_embedder) == batches, "an unchanged page is not re-embedded"
    assert rerun.created == rerun.updated == 0
    assert db_session.execute(text("SELECT count(*) FROM chunks WHERE url = :u"), {"u": HOLZ}).scalar_one() == len(first)

    ingest_source(db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: REVISED}))
    after = db_session.execute(text("SELECT content, content_hash FROM chunks WHERE url = :u"), {"u": HOLZ}).all()
    assert {row.content_hash for row in after} != {row.content_hash for row in first}
    assert all(row.content_hash == content_hash(row.content) for row in after)


def test_an_old_chunk_without_a_hash_gains_one_when_seen_unchanged(
    db_session: Session, toom_settings: Settings, stub_embedder: list[list[str]]
) -> None:
    db_session.execute(text("TRUNCATE TABLE chunks"))
    db_session.commit()
    ingest_source(db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE}))
    db_session.execute(text("UPDATE chunks SET content_hash = NULL"))
    db_session.commit()
    batches = len(stub_embedder)

    ingest_source(db_session, toom_settings, "toom", urls=[HOLZ], fetcher=make_fetcher({HOLZ: PAGE}))

    assert len(stub_embedder) == batches
    missing = db_session.execute(text("SELECT count(*) FROM chunks WHERE content_hash IS NULL")).scalar_one()
    assert missing == 0


def test_products_are_taken_across_keywords_not_by_the_most_numerous() -> None:
    from app.ingestion.sources import TOOM

    products = next(group for group in TOOM.groups if group.name == "products")
    urls = [f"https://toom.de/p/spanplattenschrauben-{i}-mm/{i}" for i in range(10)] + [
        "https://toom.de/p/siebdruckplatte-2500-x-1250-x-15-mm/7100576",
        "https://toom.de/p/fliesenkleber-25-kg/2350361",
    ]

    ordered = products.diversified(urls)

    assert set(ordered[:3]) >= {
        "https://toom.de/p/siebdruckplatte-2500-x-1250-x-15-mm/7100576",
        "https://toom.de/p/fliesenkleber-25-kg/2350361",
    }
    assert TOOM.group_of("https://toom.de/p/glastuer-siebdruck-1972-x-709/100086") is None
    assert TOOM.group_of("https://toom.de/p/teppich-crosby-graubraun-60-x-110-cm/10452942") is None
    assert TOOM.group_of("https://toom.de/p/osb3-verlegeplatte-cityboard-18-mm/7700361") == "products"
