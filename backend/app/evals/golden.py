"""The hand-written golden set: loading, validation and the passage-key check.

A passage key survives a re-ingest of unchanged content: `<url>#<chunk_index>`
for catalogue and guideline chunks, `<version_id>:<block_id>` for engineering
evidence. Everything is checked before any retrieval or model call.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, Literal
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, EngineeringChunk

PathName = Literal["catalog", "guideline", "engineering"]
Split = Literal["dev", "held_out"]

_CHUNK_KEY: Final = re.compile(r"^(?P<url>.+)#(?P<index>\d+)$")


class GoldenSetError(ValueError):
    """The golden set is invalid. The message names the entry and the field or key."""


class GoldenEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    question: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    expected: list[str] = Field(min_length=1)
    path: PathName
    split: Split


def _entries(raw: object) -> list[object]:
    if not isinstance(raw, dict) or set(raw) != {"questions"} or not isinstance(raw["questions"], list):
        raise GoldenSetError("golden set must be a mapping with exactly one key, 'questions', holding a list")
    return raw["questions"]


def parse_golden(raw: object) -> list[GoldenEntry]:
    """Validate a loaded golden set; the first fault names the entry and the field."""
    entries: list[GoldenEntry] = []
    seen: set[str] = set()
    for position, item in enumerate(_entries(raw), start=1):
        name = item.get("id") if isinstance(item, dict) and isinstance(item.get("id"), str) else f"#{position}"
        try:
            entry = GoldenEntry.model_validate(item)
        except ValidationError as error:
            first = error.errors()[0]
            field = ".".join(str(part) for part in first["loc"]) or "(entry)"
            raise GoldenSetError(f"golden set entry {name!r}, field {field!r}: {first['msg']}") from error
        if entry.id in seen:
            raise GoldenSetError(f"golden set entry {entry.id!r} appears more than once")
        seen.add(entry.id)
        for key in entry.expected:
            if not _well_formed(entry.path, key):
                raise GoldenSetError(f"golden set entry {entry.id!r}, field 'expected': malformed key {key!r}")
        entries.append(entry)
    return entries


def load_golden(path: Path) -> list[GoldenEntry]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GoldenSetError(f"golden set not found: {path}") from error
    except yaml.YAMLError as error:
        raise GoldenSetError(f"golden set is not valid YAML: {path}") from error
    return parse_golden(raw)


def _well_formed(path: PathName, key: str) -> bool:
    if path != "engineering":
        return _CHUNK_KEY.match(key) is not None
    version, _, block = key.partition(":")
    try:
        UUID(version)
    except ValueError:
        return False
    return bool(block)


def _exists(session: Session, path: PathName, key: str) -> bool:
    if path == "engineering":
        version, _, block = key.partition(":")
        statement = select(EngineeringChunk.id).where(
            EngineeringChunk.version_id == UUID(version), EngineeringChunk.block_id == block
        )
    else:
        match = _CHUNK_KEY.match(key)
        assert match is not None  # parse_golden checked the form
        statement = select(Chunk.id).where(
            Chunk.url == match["url"], Chunk.chunk_index == int(match["index"])
        )
    return session.scalar(statement.limit(1)) is not None


def check_keys(session: Session, entries: list[GoldenEntry]) -> None:
    """Refuse a key missing from the database, so a re-ingest that moved it is
    caught here instead of scored as a retrieval miss."""
    for entry in entries:
        for key in entry.expected:
            if not _exists(session, entry.path, key):
                raise GoldenSetError(
                    f"golden set entry {entry.id!r} expects passage {key!r}, which is not in the database"
                )
