"""The ingestion run: discover, fetch, extract, embed, upsert, report.

A run is re-runnable by design. Chunks are keyed on (url, chunk_index), so a
second pass over a page writes only the chunks whose text changed, refreshes
the timestamp on the rest, and drops any past the page's new end; the corpus
does not grow and unchanged text is never re-embedded. The report separates
created, updated and unchanged so that "nothing changed" is visible rather
than inferred.

One page failing never ends the run. A retailer's site is not under our
control, and a run that aborts on the first 500 would be useless against
fifty pages of someone else's markup.

Lawful sources only (CLAUDE.md §5a): permission is the source's own robots.txt
for this service's stated identity, read before any page, and a refusal ends the
run and is reported — never retried under another identity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import zip_longest

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.chunk_store import (
    IncomingChunk,
    content_hash,
    refresh_page_chunks,
    replace_page_chunks,
    stored_page_contents,
    stored_page_hashes,
)
from app.embedding import embed
from app.ingestion.extract import chunk_text, extract_text
from app.ingestion.fetcher import PacedFetcher, build_user_agent
from app.ingestion.robots import RobotsRules, RulesUnavailable
from app.ingestion.sitemap import parse_locations
from app.ingestion.sources import RetailSource, get_source

logger = logging.getLogger(__name__)


class SourceNotEnabled(Exception):
    """Ingestion was asked for a source this deployment does not permit."""

    def __init__(self, source: str) -> None:
        self.source = source
        super().__init__(
            f"retail source {source!r} is not enabled for this deployment; "
            f"add it to RETAIL_SOURCES to ingest it"
        )


@dataclass
class PageFailure:
    url: str
    reason: str


@dataclass
class GroupReport:
    """One source group's share of a run (retail-ingestion coverage reporting)."""

    discovered: int = 0
    allowed: int = 0
    excluded: int = 0
    selected: int = 0
    fetched: int = 0
    changed: int = 0
    unchanged: int = 0
    failed: int = 0


@dataclass
class RunReport:
    """What a run did, in enough detail to tell a re-run from a first run."""

    source: str
    created: int = 0
    updated: int = 0
    # Chunks seen again with identical text: timestamp refreshed, nothing
    # re-embedded or rewritten.
    unchanged: int = 0
    pages_ingested: int = 0
    skipped_by_rule: list[str] = field(default_factory=list)
    failures: list[PageFailure] = field(default_factory=list)
    budget_reached: bool = False
    refused: str | None = None
    # Per source group, and which group each selected URL came from.
    groups: dict[str, GroupReport] = field(default_factory=dict)
    page_groups: dict[str, str] = field(default_factory=dict)

    @property
    def gaps(self) -> list[str]:
        """Groups that yielded no usable page — reported, never claimed complete."""
        return [name for name, group in self.groups.items() if group.fetched - group.failed <= 0]

    def group(self, url: str) -> GroupReport | None:
        name = self.page_groups.get(url)
        return self.groups.get(name) if name is not None else None

    @property
    def succeeded(self) -> bool:
        """A run that processed no page at all is a failure, not an empty success."""
        return self.refused is None and not (self.pages_ingested == 0 and self.failures)

    def summary(self) -> str:
        if self.refused:
            return f"{self.source}: refused automated access ({self.refused})"
        headline = (
            f"{self.source}: {self.pages_ingested} pages, "
            f"{self.created} chunks created, {self.updated} updated, "
            f"{self.unchanged} unchanged, "
            f"{len(self.skipped_by_rule)} skipped by rule, "
            f"{len(self.failures)} failed"
        )
        lines = [headline]
        for name, group in self.groups.items():
            lines.append(
                f"  {name}: {group.discovered} discovered, {group.allowed} allowed, "
                f"{group.excluded} excluded by rule, {group.selected} selected, "
                f"{group.fetched} fetched, {group.changed} changed, "
                f"{group.unchanged} unchanged, {group.failed} failed"
            )
        if self.groups and self.gaps:
            lines.append(f"  gaps (no usable page): {', '.join(self.gaps)}")
        return "\n".join(lines)


def _allocate(
    by_group: dict[str, list[str]], shares: dict[str, float], limit: int
) -> list[str]:
    """Each group's share of the budget, then leftovers to groups that have more.

    A group with fewer URLs than its share yields the rest to the others, in
    group order. The result interleaves groups, so a run stopped early by the
    fetcher's own page budget still spans every group.
    """
    taken = {name: urls[: int(limit * shares.get(name, 0.0))] for name, urls in by_group.items()}
    remaining = limit - sum(len(urls) for urls in taken.values())
    while remaining > 0:
        progressed = False
        for name, urls in by_group.items():
            if remaining == 0:
                break
            if len(taken[name]) < len(urls):
                taken[name].append(urls[len(taken[name])])
                remaining -= 1
                progressed = True
        if not progressed:
            break
    ordered: list[str] = []
    for row in zip_longest(*taken.values()):
        ordered.extend(url for url in row if url)
    return ordered


def discover_urls(
    fetcher: PacedFetcher,
    source: RetailSource,
    rules: RobotsRules,
    *,
    limit: int,
    shares: dict[str, float] | None = None,
    report: RunReport | None = None,
) -> tuple[list[str], list[str]]:
    """Return (allowed URLs, URLs excluded by the source's own rules).

    The budget is allocated across the source's groups by their shares
    (`shares` overrides them by group name); `report`, when given, receives
    each group's discovery counts and which group every selected URL is from.
    """
    per_sitemap: list[list[str]] = []
    for sitemap_url in source.sitemap_urls:
        if not rules.allows(sitemap_url):
            continue
        try:
            response = fetcher.fetch_auxiliary(sitemap_url)
            response.raise_for_status()
            kind, locations = parse_locations(response.text)
        except Exception as error:  # noqa: BLE001 - a bad sitemap is not fatal
            logger.warning("sitemap %s unusable: %s", sitemap_url, error)
            continue
        if kind == "index":
            # Nested indexes are followed one level; deeper nesting is not
            # something toom uses and would multiply requests.
            for nested in locations[:5]:
                try:
                    nested_response = fetcher.fetch_auxiliary(nested)
                    _, nested_locations = parse_locations(nested_response.text)
                    locations.extend(nested_locations)
                except Exception as error:  # noqa: BLE001
                    logger.warning("nested sitemap %s unusable: %s", nested, error)
                    continue
        per_sitemap.append(locations)

    # Take from each sitemap in turn rather than draining the first one.
    # toom's categories.xml alone lists far more matching URLs than any budget
    # allows, so first-come-first-served would spend the whole run on product
    # categories and never reach the delivery, returns and cut-service pages —
    # which are the prose a shopper's questions are actually answered from.
    interleaved: list[str] = []
    for row in zip_longest(*per_sitemap):
        interleaved.extend(url for url in row if url)

    group_shares = {group.name: group.share for group in source.groups}
    group_shares.update(shares or {})
    by_group: dict[str, list[str]] = {group.name: [] for group in source.groups}
    excluded: list[str] = []
    counts = {group.name: GroupReport() for group in source.groups}
    for url in dict.fromkeys(interleaved):
        name = source.group_of(url)
        if name is None:
            continue
        counts[name].discovered += 1
        if rules.allows(url):
            counts[name].allowed += 1
            by_group[name].append(url)
        else:
            counts[name].excluded += 1
            excluded.append(url)

    for group in source.groups:
        by_group[group.name] = group.diversified(by_group[group.name])
    selected = _allocate(by_group, group_shares, limit)
    if report is not None:
        for url in selected:
            name = source.group_of(url)
            if name is not None:
                counts[name].selected += 1
                report.page_groups[url] = name
        report.groups = counts
    return selected, excluded


def ingest_source(
    session: Session,
    settings: Settings,
    source_name: str,
    *,
    urls: list[str] | None = None,
    fetcher: PacedFetcher | None = None,
) -> RunReport:
    """Run ingestion for one source and report what happened.

    `fetcher` is injectable so a run can be exercised against recorded
    responses; left unset, one is built from settings.
    """
    if not settings.source_enabled(source_name):
        raise SourceNotEnabled(source_name)

    source = get_source(source_name)
    report = RunReport(source=source_name)

    fetcher = fetcher or PacedFetcher(
        user_agent=build_user_agent(settings.crawler_identity),
        min_interval_seconds=settings.ingestion_min_interval_seconds,
        page_budget=settings.ingestion_page_budget,
    )

    with fetcher:
        # Permission first: no content page is requested before the rules are
        # in hand, and a refusal ends the run here.
        try:
            rules = fetcher.fetch_rules(source.base_url, source=source_name)
        except RulesUnavailable as refusal:
            report.refused = refusal.reason
            logger.warning("%s", refusal)
            return report

        targets = urls
        if targets is None:
            targets, excluded = discover_urls(
                fetcher,
                source,
                rules,
                limit=settings.ingestion_page_budget,
                report=report,
            )
            report.skipped_by_rule.extend(excluded)
        else:
            allowed = []
            for url in targets:
                (allowed if rules.allows(url) else report.skipped_by_rule).append(url)
            targets = allowed

        for url, outcome in fetcher.fetch_within_budget(targets):
            try:
                if isinstance(outcome, Exception):
                    raise outcome
                outcome.raise_for_status()
                group = report.group(url)
                if group is not None:
                    group.fetched += 1
                _ingest_page(session, source, url, outcome.text, report)
            except Exception as error:  # noqa: BLE001 - one page must not end the run
                report.failures.append(PageFailure(url, type(error).__name__))
                group = report.group(url)
                if group is not None:
                    group.failed += 1
                logger.warning("page %s failed: %s", url, error)

        report.budget_reached = fetcher.pages_fetched >= fetcher.page_budget

    return report


def _ingest_page(
    session: Session,
    source: RetailSource,
    url: str,
    html: str,
    report: RunReport,
) -> None:
    pieces = chunk_text(extract_text(html))
    if not pieces:
        raise ValueError("no readable text on the page")

    # Compare before embedding: the model is the expensive step, and a page
    # that says what it said last time needs none of it. Comparison is on the
    # extracted, chunked text, so a change in the chunker or the extractor
    # shows up as changed content and is re-embedded; a swap of the embedding
    # model does not, and needs a full re-embed run instead.
    # Compared by content hash, falling back to the text for a chunk stored
    # before hashes existed; either way unchanged text is never re-embedded.
    stored = stored_page_contents(session, url)
    stored_hashes = stored_page_hashes(session, url)

    def same(index: int, content: str) -> bool:
        known = stored_hashes.get(index)
        return known == content_hash(content) if known else stored.get(index) == content

    changed = [(index, content) for index, content in enumerate(pieces) if not same(index, content)]
    unchanged = [index for index, content in enumerate(pieces) if same(index, content)]

    vectors = embed([content for _, content in changed]) if changed else []
    scraped_at = datetime.now(UTC)
    incoming = [
        IncomingChunk(
            content=content,
            embedding=vector,
            source_site=source.name,
            url=url,
            category=source.categorise(url),
            chunk_index=index,
            scraped_at=scraped_at,
        )
        for (index, content), vector in zip(changed, vectors, strict=True)
    ]
    result = replace_page_chunks(session, url, incoming, page_length=len(pieces))
    refreshed = refresh_page_chunks(session, url, unchanged, scraped_at)
    session.commit()

    report.pages_ingested += 1
    report.created += result.created
    report.updated += result.updated
    report.unchanged += refreshed
    group = report.group(url)
    if group is not None:
        if result.created or result.updated:
            group.changed += 1
        else:
            group.unchanged += 1
