"""Catalogue entries not yet registered as source versions (read-only)."""

from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT
from app.db.models import KnowledgeSource, KnowledgeSourceVersion
from app.engineering.schemas import SourceIn

CATALOGUE = REPO_ROOT / "config" / "engineering_sources.yaml"


def is_registered(session: Session, source: SourceIn) -> bool:
    known = session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.key == source.key)
    )
    return (
        known is not None
        and session.scalar(
            select(KnowledgeSourceVersion).where(
                KnowledgeSourceVersion.source_id == known.id,
                KnowledgeSourceVersion.attributes
                == source.metadata.model_dump(mode="json"),
            )
        )
        is not None
    )


def unregistered(session: Session, path: Path = CATALOGUE) -> list[SourceIn]:
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = [SourceIn.model_validate(raw) for raw in entries]
    return [source for source in sources if not is_registered(session, source)]
