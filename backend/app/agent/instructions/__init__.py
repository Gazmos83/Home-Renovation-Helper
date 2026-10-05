"""One checked-in instruction file for each agent that talks in the design loop.

Each file is a YAML header between `---` lines and the agent's instruction text
after it. The header names the agent, the routing slot it runs on and its tools;
only the text is the agent's wording, and the header is what binds the tools.

`load_instructions` reads every file once and stops startup, naming the file, on
the first fault. It reads only the fixed names below, never a path a request
supplies.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from app.agent.models.routing import SLOTS
from app.agent.prompts import SENTINEL
from app.agent.tools import KNOWN_TOOLS

INSTRUCTIONS_DIR: Final = Path(__file__).parent

AGENT_NAMES: Final[tuple[str, ...]] = ("foreman", "intake", "designer", "builder")


class InstructionError(ValueError):
    """An instruction file is missing or invalid. The message names the file."""


class InstructionHeader(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    slot: str
    tools: tuple[str, ...] = ()


class AgentInstruction(BaseModel):
    model_config = ConfigDict(frozen=True)

    header: InstructionHeader
    text: str

    @property
    def name(self) -> str:
        return self.header.name

    @property
    def slot(self) -> str:
        return self.header.slot

    @property
    def tools(self) -> tuple[str, ...]:
        return self.header.tools


def _split(raw: str, filename: str) -> tuple[str, str]:
    lines = raw.split("\n")
    if not lines or lines[0].strip() != "---":
        raise InstructionError(f"{filename}: the file must start with a --- header")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :]).strip()
    raise InstructionError(f"{filename}: the header has no closing ---")


def parse_instruction(
    raw: str, *, filename: str, slots: Collection[str] = SLOTS
) -> AgentInstruction:
    """Validate one file's content. `filename` is `<agent name>.md`."""
    header_text, text = _split(raw, filename)
    try:
        data = yaml.safe_load(header_text)
    except yaml.YAMLError as error:
        raise InstructionError(f"{filename}: the header is not valid YAML: {error}") from None
    if not isinstance(data, dict):
        raise InstructionError(f"{filename}: the header must be a mapping")
    try:
        header = InstructionHeader.model_validate(data)
    except ValidationError as error:
        raise InstructionError(f"{filename}: invalid header: {error}") from None

    stem = filename.removesuffix(".md")
    if header.name != stem:
        raise InstructionError(f"{filename}: the header name {header.name!r} must be {stem!r}")
    if header.name not in AGENT_NAMES:
        raise InstructionError(f"{filename}: {header.name!r} is not a known agent")
    if header.slot not in slots:
        raise InstructionError(f"{filename}: the slot {header.slot!r} is not in the routing")
    unknown = sorted(set(header.tools) - KNOWN_TOOLS)
    if unknown:
        raise InstructionError(f"{filename}: unknown tool {', '.join(unknown)}")
    if not text:
        raise InstructionError(f"{filename}: the instruction text is empty")
    if SENTINEL in text:
        raise InstructionError(f"{filename}: the text contains the reserved delimiter {SENTINEL}")
    return AgentInstruction(header=header, text=text)


def load_instructions(
    directory: Path | None = None, *, slots: Collection[str] = SLOTS
) -> dict[str, AgentInstruction]:
    """Read all four files. The first fault stops the load, naming the file."""
    base = directory or INSTRUCTIONS_DIR
    loaded: dict[str, AgentInstruction] = {}
    for name in AGENT_NAMES:
        filename = f"{name}.md"
        try:
            raw = (base / filename).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise InstructionError(f"{filename}: the instruction file is missing") from None
        loaded[name] = parse_instruction(raw, filename=filename, slots=slots)
    return loaded
