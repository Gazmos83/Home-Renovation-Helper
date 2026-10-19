"""design-guidelines: official publications are ingested sectioned, or reported and skipped."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.guidelines.ingest import CATEGORY, ingest_guidelines, pdf_text, split_sections
from app.guidelines.sources import GuidelineSource, GuidelineSourceError, load_sources
from app.ingestion.fetcher import PacedFetcher

pytestmark = pytest.mark.usefixtures("clean_chunks")

ALLOW_ALL = "User-agent: *\nAllow: /"


def make_pdf(lines: list[str]) -> bytes:
    """A one-page PDF whose text layer is `lines` (no external tool needed)."""
    stream = "BT /F1 12 Tf 14 TL 50 750 Td " + " T* ".join(
        f"({line.replace('(', '[').replace(')', ']')}) Tj" for line in lines
    ) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


PDF = make_pdf([
    "ASR A1.2 Raumabmessungen",
    "1 Anwendungsbereich",
    "Diese Regel gilt fuer Arbeitsraeume.",
    "4.1 Raumhoehe",
    "Die lichte Raumhoehe betraegt mindestens 2,50 m.",
])


def source(source_id: str, url: str, fmt: str = "pdf") -> GuidelineSource:
    return GuidelineSource(
        id=source_id, title="ASR A1.2", jurisdiction="DE", url=url, format=fmt,
        published_on=date(2022, 1, 1), licence="official",
    )


def fetcher_for(handler) -> PacedFetcher:
    return PacedFetcher(
        user_agent="test-agent", min_interval_seconds=0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_a_pdf_is_ingested_as_sectioned_guideline_chunks(db_session: Session, fake_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ALLOW_ALL, headers={"content-type": "text/plain"})
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})

    report = ingest_guidelines(db_session, fetcher_for(handler), [source("asr-a1-2", "https://rules.test/asr.pdf")])

    assert report.ingested["asr-a1-2"] >= 2 and report.failures == []
    rows = db_session.scalars(select(Chunk).where(Chunk.category == CATEGORY)).all()
    sections = {row.section for row in rows}
    assert "4.1 Raumhoehe" in sections
    assert all(row.title == "ASR A1.2" and row.published_on == date(2022, 1, 1) for row in rows)
    assert all(row.source_site == "asr-a1-2" for row in rows)


def test_a_refused_source_is_reported_and_skipped_without_fetching_it(db_session: Session, fake_embedder) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /", headers={"content-type": "text/plain"})
        return httpx.Response(200, content=PDF)

    report = ingest_guidelines(db_session, fetcher_for(handler), [source("closed", "https://closed.test/a.pdf")])

    assert report.ingested == {}
    assert "excluded" in report.failures[0] and "closed" in report.failures[0]
    assert seen == ["/robots.txt"]


def test_unreadable_rules_are_a_refusal(db_session: Session, fake_embedder) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(404, text="nope")

    report = ingest_guidelines(db_session, fetcher_for(handler), [source("nobots", "https://nobots.test/a.pdf")])

    assert report.ingested == {} and "could not be read" in report.failures[0]
    assert seen == ["/robots.txt"]


def test_one_failing_source_does_not_stop_the_next(db_session: Session, fake_embedder) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ALLOW_ALL, headers={"content-type": "text/plain"})
        if request.url.host == "bad.test":
            return httpx.Response(500, text="boom")
        return httpx.Response(200, content=PDF)

    report = ingest_guidelines(
        db_session, fetcher_for(handler),
        [source("bad", "https://bad.test/a.pdf"), source("good", "https://good.test/a.pdf")],
    )

    assert "bad: HTTP 500" in report.failures
    assert "good" in report.ingested


def test_sections_are_split_at_paragraph_and_numbered_headings() -> None:
    parts = split_sections("Vorwort\n§ 43 Aufenthaltsraeume\nText a\n3.2 Beleuchtung\nText b")
    assert [label for label, _ in parts] == [None, "§ 43 Aufenthaltsraeume", "3.2 Beleuchtung"]


def test_pdf_text_reads_the_text_layer() -> None:
    assert "Raumhoehe" in pdf_text(PDF)


def test_the_checked_in_sources_load() -> None:
    assert all(s.url or s.path for s in load_sources())


def local(source_id: str, path: str, fmt: str = "pdf") -> GuidelineSource:
    return GuidelineSource(
        id=source_id, title="ASR A1.2", jurisdiction="DE", path=path, format=fmt,
        published_on=date(2022, 1, 1), licence="owner's copy",
    )


def no_request(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"a local source made a request: {request.url}")


def test_a_local_pdf_is_ingested_with_no_network_request(db_session: Session, fake_embedder, tmp_path) -> None:
    (tmp_path / "pdf").mkdir()
    (tmp_path / "pdf" / "asr.pdf").write_bytes(PDF)

    report = ingest_guidelines(db_session, fetcher_for(no_request), [local("asr", "pdf/asr.pdf")], root=tmp_path)

    assert report.ingested["asr"] >= 2 and report.failures == []
    rows = db_session.scalars(select(Chunk).where(Chunk.source_site == "asr")).all()
    assert {row.url for row in rows} == {"file:pdf/asr.pdf"}
    assert "4.1 Raumhoehe" in {row.section for row in rows}
    assert all(row.category == CATEGORY and row.published_on == date(2022, 1, 1) for row in rows)


def test_a_local_markdown_note_is_ingested_by_section(db_session: Session, fake_embedder, tmp_path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "wardrobe.md").write_text("Einleitung\n3.2 Durchgang\nVor dem Schrank 900 mm frei.\n")

    report = ingest_guidelines(
        db_session, None, [local("wardrobe", "notes/wardrobe.md", "md")], root=tmp_path
    )

    assert report.ingested["wardrobe"] >= 1
    sections = {r.section for r in db_session.scalars(select(Chunk).where(Chunk.source_site == "wardrobe"))}
    assert "3.2 Durchgang" in sections


def test_a_missing_local_file_is_reported_and_the_next_source_still_runs(
    db_session: Session, fake_embedder, tmp_path
) -> None:
    (tmp_path / "ok.pdf").write_bytes(PDF)

    report = ingest_guidelines(
        db_session, None, [local("gone", "gone.pdf"), local("ok", "ok.pdf")], root=tmp_path
    )

    assert report.failures == ["gone: the file 'gone.pdf' is missing"]
    assert "ok" in report.ingested


def test_a_path_outside_the_folder_fails_loading_naming_the_source(tmp_path) -> None:
    listing = tmp_path / "s.yaml"
    listing.write_text(
        "sources:\n  - {id: sneaky, title: t, jurisdiction: j, path: ../secret.pdf, format: pdf,"
        " published_on: 2022-01-01, licence: l}\n"
    )
    with pytest.raises(GuidelineSourceError, match="source 'sneaky': path '../secret.pdf' leaves"):
        load_sources(listing, root=tmp_path / "docs")


@pytest.mark.parametrize("location", ["", "url: https://x.test/a, path: a.pdf, "])
def test_a_source_needs_exactly_one_location(tmp_path, location: str) -> None:
    listing = tmp_path / "s.yaml"
    listing.write_text(
        "sources:\n  - {id: a, title: t, jurisdiction: j, " + location
        + "format: pdf, published_on: 2022-01-01, licence: l}\n"
    )
    with pytest.raises(GuidelineSourceError, match="exactly one of url and path"):
        load_sources(listing, root=tmp_path)


def test_a_source_list_with_a_duplicate_id_is_refused(tmp_path) -> None:
    path = tmp_path / "s.yaml"
    entry = "  - {id: a, title: t, jurisdiction: j, url: 'https://x.test/a', format: pdf, published_on: 2022-01-01, licence: l}\n"
    path.write_text("sources:\n" + entry + entry)
    with pytest.raises(GuidelineSourceError, match="'a' is listed twice"):
        load_sources(path)


def test_page_furniture_is_cut_and_a_furniture_only_chunk_is_dropped() -> None:
    from app.guidelines.ingest import without_furniture

    topics = ["brackets", "pins", "hinges", "aprons", "spans"]
    pages = [f"This page explains shelf {topic} in some detail.\nShelf Guide https://example.org/guide\n{n} of 5 10/8/26, 08:45"
             for n, topic in enumerate(topics, start=1)]
    pages[0] += "\n1 x 8 27 23\n1 x 10 30 25\n1 x 12 32 26\n5 x 8 38 32"  # a table on one page stays
    kept = without_furniture(pages, [pages[0], "Shelf Guide https://example.org/guide\n5 of 5 10/8/26, 08:45"])
    assert kept == ["This page explains shelf brackets in some detail.\n1 x 8 27 23\n1 x 10 30 25\n1 x 12 32 26\n5 x 8 38 32"]
