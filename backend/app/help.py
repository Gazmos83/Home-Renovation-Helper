"""The Studio's help from configuration (help-center).

`config/help.yaml` is the one source for the Help page and Intake's `read_help`
tool. It loads at startup and stops it by name on a malformed file, an unknown key
or a repeated topic id, the same posture as the render tiers and the presets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Final, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from app.config import ConfigurationError

DEFAULT_HELP_PATH: Final = Path(__file__).resolve().parents[1] / "config" / "help.yaml"

TopicId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,31}$")]
Line = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class HelpError(ConfigurationError):
    """The help configuration cannot be used."""


class Block(BaseModel):
    """A paragraph (`text`) or a list (`items`), optionally under a heading."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    heading: Line | None = None
    text: Line | None = None
    items: Annotated[list[Line], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> Block:
        if (self.text is None) == (self.items is None):
            raise ValueError("a block holds either text or items")
        return self


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: TopicId
    title: Line
    body: Annotated[list[Block], Field(min_length=1)]
    prompt: Line | None = None
    download: Literal["import_template"] | None = None


class Help(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    topics: Annotated[list[Topic], Field(min_length=1)]

    def ids(self) -> list[str]:
        return [topic.id for topic in self.topics]

    def topic(self, topic_id: str) -> Topic | None:
        return next((topic for topic in self.topics if topic.id == topic_id), None)


def topic_text(topic: Topic) -> str:
    """One topic as plain text: its title, its blocks, then its prompt."""
    lines = [topic.title]
    for block in topic.body:
        lines.append("")
        if block.heading:
            lines.append(f"{block.heading}:")
        if block.text is not None:
            lines.append(block.text)
        for item in block.items or ():
            lines.append(f"- {item}")
    if topic.prompt:
        lines += ["", "Default prompt:", topic.prompt]
    return "\n".join(lines)


def _first_problem(error: ValidationError) -> str:
    problem = error.errors()[0]
    where = ".".join(str(part) for part in problem["loc"])
    return f"{where}: {problem['msg']}"


def load_help(path: Path = DEFAULT_HELP_PATH) -> Help:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise HelpError(f"help configuration not found: {path}") from error
    except yaml.YAMLError as error:
        raise HelpError(f"help configuration is not valid YAML: {path}") from error
    try:
        loaded = Help.model_validate(raw)
    except ValidationError as error:
        raise HelpError(f"{path.name}: {_first_problem(error)}") from None
    ids = loaded.ids()
    repeated = sorted({topic_id for topic_id in ids if ids.count(topic_id) > 1})
    if repeated:
        raise HelpError(f"{path.name} names the topic id {', '.join(map(repr, repeated))} more than once")
    return loaded
