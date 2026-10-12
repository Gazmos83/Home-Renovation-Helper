"""Developer CLI: metadata-only catalogue seed or reviewed confined-file ingest."""

import argparse
import json
from pathlib import Path
from uuid import UUID

import yaml
from sqlalchemy.orm import Session

from app.config import load_settings
from app.db.session import make_engine
from app.engineering.catalogue import CATALOGUE, is_registered
from app.engineering.ingest import ingest_version, stage_file
from app.engineering.registry import register_source
from app.engineering.schemas import SourceIn


def seed_catalogue(session: Session, path: Path = CATALOGUE) -> int:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    created = 0
    for raw in entries:
        source = SourceIn.model_validate(raw)
        if is_registered(session, source):
            continue
        register_source(session, source)
        created += 1
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "seed-links", help="register the brief catalogue without fetching or extracting"
    )
    ingest = commands.add_parser(
        "ingest-file", help="stage and ingest an already rights-approved local source"
    )
    ingest.add_argument("version_id", type=UUID)
    ingest.add_argument(
        "relative_path", help="PDF/HTML/Markdown path confined to GUIDELINE_ROOT"
    )
    args = parser.parse_args()
    settings = load_settings()
    engine = make_engine(settings.database_url)
    try:
        with Session(engine) as session:
            if args.command == "seed-links":
                count = seed_catalogue(session)
                session.commit()
                print(json.dumps({"registered": count, "content_requests": 0}))
            else:
                stage_file(
                    session,
                    args.version_id,
                    settings.guideline_root,
                    args.relative_path,
                )
                session.commit()
                run = ingest_version(session, settings, args.version_id)
                session.commit()
                print(
                    json.dumps(
                        {"state": run.state, "blocks": run.blocks, "reason": run.reason}
                    )
                )
                if run.state != "published":
                    raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
