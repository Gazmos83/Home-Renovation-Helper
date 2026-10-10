"""Ingesting the guideline publications into the corpus (design-guidelines spec).

A file source (the owner's own PDF or Markdown under the guidelines folder) is
read locally with no network request. A URL source is fetched under this
service's identity, only after its host's robots.txt allows it. PDF text is read
with `pypdf`, HTML with the shared extractor; text is split on section markers
(`§ 43`, `4.1 …`) before the usual chunker, and each chunk keeps its title,
section and publication date. A source that refuses, cannot be read or is
missing is reported and skipped — never fetched another way (CLAUDE.md §5a).
"""

from __future__ import annotations

import io
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import DEFAULT_GUIDELINE_ROOT
from app.db.chunk_store import IncomingChunk, replace_page_chunks
from app.embedding import embed
from app.guidelines.sources import GuidelineSource, load_sources, resolve_path
from app.ingestion.extract import chunk_text, extract_text
from app.ingestion.fetcher import PacedFetcher
from app.ingestion.robots import RulesUnavailable

logger = logging.getLogger("app")

CATEGORY = "guideline"
_SECTION = re.compile(r"^\s*(§\s*\d+[a-z]?\b[^\n]{0,100}|\d+(?:\.\d+){1,3}\s+[A-ZÄÖÜ][^\n]{2,100})\s*$")


@dataclass
class GuidelineReport:
    ingested: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def summary(self) -> str:
        done = ", ".join(f"{name}: {count} chunks" for name, count in self.ingested.items()) or "nothing"
        return f"guidelines: {len(self.ingested)} source(s) ingested ({done}), {len(self.failures)} skipped"


def split_sections(text: str) -> list[tuple[str | None, str]]:
    """The text cut at section markers: `(section label, body)`, the label `None` before the first."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in text.splitlines():
        marker = _SECTION.match(line)
        if marker and len(line.strip()) <= 120:
            sections.append((" ".join(marker.group(1).split()), [line]))
        else:
            sections[-1][1].append(line)
    return [(label, "\n".join(lines).strip()) for label, lines in sections if "\n".join(lines).strip()]


def pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _chunks(source: GuidelineSource, text: str) -> list[IncomingChunk]:
    scraped_at = datetime.now(UTC)
    pieces: list[tuple[str | None, str]] = []
    for label, body in split_sections(text):
        pieces.extend((label, piece) for piece in chunk_text(body))
    vectors = embed([piece for _label, piece in pieces]) if pieces else []
    return [
        IncomingChunk(
            content=piece, embedding=vector, source_site=source.id, url=source.location, category=CATEGORY,
            chunk_index=index, scraped_at=scraped_at, title=source.title, section=label,
            published_on=source.published_on,
        )
        for index, ((label, piece), vector) in enumerate(zip(pieces, vectors, strict=True))
    ]


def _local_text(source: GuidelineSource, root: Path) -> str | None:
    """The text of a file source, or `None` when the file is missing."""
    target = resolve_path(source, root)
    if not target.is_file():
        return None
    if source.format == "pdf":
        return pdf_text(target.read_bytes())
    return target.read_text(encoding="utf-8")


def _remote_text(source: GuidelineSource, fetcher: PacedFetcher | None, report: GuidelineReport) -> str | None:
    """The text of a URL source, or `None` after recording why it was skipped."""
    assert source.url is not None
    if fetcher is None:
        report.failures.append(f"{source.id}: no fetcher for a URL source")
        return None
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(source.url))
    try:
        rules = fetcher.fetch_rules(origin, source=source.id)
    except RulesUnavailable as refusal:
        report.failures.append(f"{source.id}: its robots rules could not be read ({refusal.reason})")
        return None
    if not rules.allows(source.url):
        report.failures.append(f"{source.id}: excluded by {origin}'s published crawling rules")
        return None
    response = fetcher.fetch_auxiliary(source.url)
    if response.status_code != 200:
        report.failures.append(f"{source.id}: HTTP {response.status_code}")
        return None
    return pdf_text(response.content) if source.format == "pdf" else extract_text(response.text)


def ingest_guidelines(
    session: Session,
    fetcher: PacedFetcher | None = None,
    sources: Sequence[GuidelineSource] | None = None,
    *,
    root: Path = DEFAULT_GUIDELINE_ROOT,
) -> GuidelineReport:
    report = GuidelineReport()
    if sources is None:
        # Uploaded PDFs are file sources beside the checked-in list (dev-panel-insights); `uploads`
        # imports this module, so it is read here rather than at the top.
        from app.guidelines.uploads import uploaded_sources

        sources = [*load_sources(root=root), *uploaded_sources(session)]
    for source in sources:
        try:
            if source.path is not None:
                text = _local_text(source, root)
                if text is None:
                    report.failures.append(f"{source.id}: the file {source.path!r} is missing")
                    continue
            else:
                text = _remote_text(source, fetcher, report)
                if text is None:
                    continue
            incoming = _chunks(source, text)
            if not incoming:
                report.failures.append(f"{source.id}: no readable text")
                continue
            replace_page_chunks(session, source.location, incoming, page_length=len(incoming))
            session.commit()
            report.ingested[source.id] = len(incoming)
        except Exception as error:  # noqa: BLE001 - one source must not end the run
            session.rollback()
            report.failures.append(f"{source.id}: {type(error).__name__}")
            logger.warning("guideline source %s failed: %s", source.id, error)
    return report
