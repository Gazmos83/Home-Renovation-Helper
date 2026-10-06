"""The checked-in list of guideline publications (`config/guideline_sources.yaml`).

A source is either a file the owner placed under the guidelines folder
(`path`, relative to it) or an official URL. A path that leaves the folder is
refused when the list loads.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.config import DEFAULT_GUIDELINE_ROOT, ConfigurationError

DEFAULT_SOURCES_PATH: Final = Path(__file__).resolve().parents[2] / "config" / "guideline_sources.yaml"


class GuidelineSourceError(ConfigurationError):
    """The sources file is unusable. The message names the source or the file."""


class GuidelineSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    jurisdiction: str
    url: str | None = None
    path: str | None = None
    format: Literal["pdf", "html", "md"]
    published_on: date
    licence: str

    @model_validator(mode="after")
    def _one_location(self) -> Self:
        if (self.url is None) == (self.path is None):
            raise ValueError("give exactly one of url and path")
        if self.url is not None and not self.url.startswith("https://"):
            raise ValueError("a url must be https")
        if self.url is not None and self.format == "md":
            raise ValueError("a url source is pdf or html")
        if self.path is not None and self.format == "html":
            raise ValueError("a file source is pdf or md")
        return self

    @property
    def location(self) -> str:
        """What identifies the document in the corpus (its `url` column)."""
        return self.url if self.url is not None else f"file:{self.path}"


def resolve_path(source: GuidelineSource, root: Path) -> Path:
    """The file of a path source, refused when it leaves `root`."""
    assert source.path is not None
    base = root.resolve()
    target = (base / source.path).resolve()
    if not target.is_relative_to(base):
        raise GuidelineSourceError(f"source {source.id!r}: path {source.path!r} leaves the guidelines folder")
    return target


def load_sources(
    path: Path = DEFAULT_SOURCES_PATH, *, root: Path = DEFAULT_GUIDELINE_ROOT
) -> tuple[GuidelineSource, ...]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GuidelineSourceError(f"guideline sources file not found: {path}") from None
    except yaml.YAMLError as error:
        raise GuidelineSourceError(f"guideline sources file is not valid YAML: {path}: {error}") from None
    if not isinstance(raw, dict) or not isinstance(raw.get("sources"), list):
        raise GuidelineSourceError(f"{path.name}: needs a 'sources' list")
    sources: list[GuidelineSource] = []
    seen: set[str] = set()
    for index, item in enumerate(raw["sources"]):
        try:
            source = GuidelineSource.model_validate(item)
        except ValidationError as error:
            name = item.get("id") if isinstance(item, dict) else index
            raise GuidelineSourceError(f"{path.name}: source {name!r}: {error.errors()[0]['msg']}") from None
        if source.id in seen:
            raise GuidelineSourceError(f"{path.name}: source {source.id!r} is listed twice")
        if source.path is not None:
            resolve_path(source, root)
        seen.add(source.id)
        sources.append(source)
    return tuple(sources)


def source_ids(path: Path = DEFAULT_SOURCES_PATH) -> frozenset[str]:
    return frozenset(source.id for source in load_sources(path))
