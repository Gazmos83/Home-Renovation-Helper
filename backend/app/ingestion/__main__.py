"""Run ingestion from the command line.

    uv run python -m app.ingestion               # every enabled retail source
    uv run python -m app.ingestion toom          # one source
    uv run python -m app.ingestion --budget 10   # a smaller run
    uv run python -m app.ingestion --store       # the home store's capture
    uv run python -m app.ingestion --guidelines  # the guideline publications

Re-running is the normal case, not a repair: pages already held are updated in
place and the report says how many were created versus updated.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import make_engine
from app.ingestion.fetcher import PacedFetcher, build_user_agent
from app.ingestion.pipeline import SourceNotEnabled, ingest_source
from app.logging import configure_logging


def _fetcher(settings) -> PacedFetcher:
    return PacedFetcher(
        user_agent=build_user_agent(settings.crawler_identity),
        min_interval_seconds=settings.ingestion_min_interval_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.ingestion", description=__doc__)
    parser.add_argument("sources", nargs="*", help="sources to ingest; defaults to every enabled source")
    parser.add_argument("--store", action="store_true", help="capture the home store instead of the page corpus")
    parser.add_argument("--guidelines", action="store_true", help="ingest the guideline publications instead")
    parser.add_argument("--budget", type=int, default=None, help="override the page budget for this run")
    arguments = parser.parse_args(argv)

    configure_logging()
    settings = get_settings()
    if arguments.budget is not None:
        settings = settings.model_copy(update={"ingestion_page_budget": arguments.budget})
    engine = make_engine(str(settings.database_url))

    try:
        if arguments.store:
            from app.pricing.store import ingest_home_store

            with Session(engine) as session, _fetcher(settings) as fetcher:
                report = ingest_home_store(session, fetcher, settings.toom_home_store)
            print(report.summary())
            for failure in report.failures:
                print(f"  failed: {failure}", file=sys.stderr)
            return 1 if report.failures else 0

        if arguments.guidelines:
            from app.guidelines.ingest import ingest_guidelines

            with Session(engine) as session, _fetcher(settings) as fetcher:
                report = ingest_guidelines(session, fetcher, root=settings.guideline_root)
            print(report.summary())
            for failure in report.failures:
                print(f"  skipped: {failure}", file=sys.stderr)
            return 0

        failed = False
        with Session(engine) as session:
            for source in arguments.sources or sorted(settings.retail_sources):
                try:
                    report = ingest_source(session, settings, source)
                except SourceNotEnabled as error:
                    print(f"skipped: {error}", file=sys.stderr)
                    failed = True
                    continue
                print(report.summary())
                for failure in report.failures:
                    print(f"  failed: {failure.url} ({failure.reason})", file=sys.stderr)
                if report.budget_reached:
                    print(f"  budget of {settings.ingestion_page_budget} reached")
                failed = failed or not report.succeeded
        return 1 if failed else 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    raise SystemExit(main())
