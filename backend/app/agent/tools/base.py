"""What every agent tool shares: its dependencies, its context and its shape.

A tool is a name, a description, the schema the model is shown, a `run` and an
optional `preview`. `preview(args, ctx)` returns a `Confirmation` (the turn
pauses for the owner's answer), `Questions` (the turn pauses for the owner's
answers, which `run` reads from `ctx.answer`), a string (a refusal returned to
the model with no pause) or `None` (run without a pause). `run(args, ctx)` returns the text the
model reads, or a `ToolOutput` that also updates graph state.

Ownership, thread and piece come from `ToolContext`, built by code from the
request — never from an argument the model supplied (CLAUDE.md §8).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.agent import house_file
from app.blender import runner
from app.blender.launch import Launch, subprocess_launch
from app.config import Settings
from app.render.tiers import Tiers


class ToolDeps:
    """The service pieces tools use, read lazily from `app.state`-shaped storage.

    Lazy because test seams (`blender_launch`) are set after the app is built,
    and the event loop exists only once the app is running.
    """

    def __init__(self, state: Any) -> None:
        self._state = state

    @property
    def engine(self) -> Engine:
        return self._state.engine

    @property
    def settings(self) -> Settings:
        return self._state.settings

    @property
    def render_root(self) -> Path:
        return self._state.settings.render_root

    @property
    def tiers(self) -> Tiers:
        return self._state.tiers

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._state.blender_semaphore

    @property
    def launch(self) -> Launch:
        return getattr(self._state, "blender_launch", None) or subprocess_launch

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return getattr(self._state, "loop", None)

    @property
    def graph(self) -> Any:
        """The compiled Foreman graph, or `None` when conversation memory is down."""
        return getattr(self._state, "graph", None)

    @property
    def offload(self) -> Any:
        """The render server's runtime, or `None` when it is not configured."""
        return getattr(self._state, "offload", None)

    @property
    def live(self) -> Any:
        """The live Blender's socket client, sharing the one-process lock."""
        existing = getattr(self._state, "live_blender", None)
        if existing is not None:
            return existing
        from app.live.socket_client import LiveBlender

        settings = self.settings
        return LiveBlender(
            settings.blender_live_host,
            settings.blender_live_port,
            semaphore=self.semaphore,
            timeout=settings.blender_live_timeout_seconds,
        )

    @property
    def live_fetcher(self) -> Any:
        return getattr(self._state, "live_fetcher", None)

    @property
    def design_rules(self) -> tuple[Any, ...]:
        return getattr(self._state, "design_rules", ())

    @property
    def lighting(self) -> Any:
        """The lamp-light factors (room-lamp-lights); the defaults when the app loaded none."""
        from app.blender.lighting import DEFAULT_LIGHTING

        return getattr(self._state, "lighting", DEFAULT_LIGHTING)

    @property
    def tracing(self) -> Any:
        return getattr(self._state, "tracing", None)

    @property
    def model_provider(self):
        provide = getattr(self._state, "model_provider", None)
        if provide is not None:
            return provide
        models = getattr(self._state, "models", None) or {}
        return models.__getitem__

    @property
    def budgets(self) -> Any:
        """The token restrictions per model (`app.state.budgets`, else the stored ones)."""
        found = getattr(self._state, "budgets", None)
        if found is not None:
            return found
        from app.agent.models.budgets import Budgets

        return Budgets(self.engine)

    def model_id(self, slot: str) -> str:
        routing = getattr(self._state, "routing", None)
        if routing is not None:
            return routing.model_for(slot)
        return f"fake/{slot}"

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session

    # --- builds and renders run on the app's event loop -----------------------

    def build_coroutine(self, package_id: str, version: int, record: str = "piece"):
        settings = self.settings
        return runner.run_build(
            root=settings.render_root,
            blender_bin=settings.blender_bin,
            timeout=settings.blender_timeout_seconds,
            package_id=package_id,
            version=version,
            semaphore=self.semaphore,
            launch=self.launch,
            record=record,
            models_root=settings.upload_root / "models",
        )

    def start_build(
        self, package_id: str, version: int, record: str = "piece"
    ) -> asyncio.Future | None:
        """Schedule a build on the app loop; `None` when there is no loop."""
        loop = self.loop
        if loop is None:
            return None
        return asyncio.run_coroutine_threadsafe(self.build_coroutine(package_id, version, record), loop)


@dataclass(frozen=True)
class ToolContext:
    deps: ToolDeps
    owner_id: UUID
    thread_id: UUID | None = None
    package_id: str | None = None
    brief: dict[str, Any] = field(default_factory=dict)
    last_message: str = ""
    approved: bool = False
    # Where this turn is traced and which agent and model are speaking; used to
    # attribute a render the turn starts (feedback-capture).
    trace_id: str | None = None
    slot: str | None = None
    model: str | None = None
    # The owner's answer to a `Questions` pause: `{"answers": [...]}` or `{"declined": "..."}`.
    answer: dict[str, Any] | None = None
    # The thread's messages, composed by code, for `revise_package`'s measurement check.
    history: tuple[Any, ...] = ()
    engineering_turn: bool = False
    engineering_enabled: bool = False
    calculators_enabled: bool = False


@dataclass(frozen=True)
class Confirmation:
    """A pause for the owner. `proposal` is the structured form of `summary`; `table` is an
    optional `{"columns": [str], "rows": [[str]]}` of display strings shown with it
    (confirmation-summaries). Neither the title nor the table reaches a model."""

    subject: str
    summary: str
    proposal: dict[str, Any]
    table: dict[str, Any] | None = None


@dataclass(frozen=True)
class Questions:
    """A pause for the owner's answers. Each question is `{text, unit, choices}`; `layout`
    names a Workspace layout the set offers to open ("room": the Room layout button)."""

    questions: list[dict[str, Any]]
    layout: str | None = None


@dataclass(frozen=True)
class ToolOutput:
    text: str
    update: dict[str, Any] = field(default_factory=dict)


Preview = Confirmation | Questions | str | None


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    schema: type[BaseModel]
    run: Callable[[dict[str, Any], ToolContext], str | ToolOutput]
    preview: Callable[[dict[str, Any], ToolContext], Preview] | None = None

    @property
    def gated(self) -> bool:
        return self.preview is not None

    def structured(self) -> StructuredTool:
        """The schema the model is shown; the graph runs `run`, never this."""
        return StructuredTool.from_function(
            func=lambda **_kwargs: "",
            name=self.name,
            description=self.description,
            args_schema=self.schema,
        )


def parse_args(model: type[BaseModel], args: dict[str, Any]) -> tuple[BaseModel | None, str]:
    """The validated arguments, or a refusal naming what is wrong."""
    try:
        return model.model_validate(args), ""
    except ValidationError as error:
        parts = []
        for detail in error.errors():
            location = ".".join(str(item) for item in detail["loc"]) or "(root)"
            parts.append(f"{location}: {detail['msg']}")
        return None, "invalid arguments: " + "; ".join(parts)


_PATH_INDEX = re.compile(r"\.(\d+)")


def unknown_fields(error: ValidationError) -> list[str]:
    """The paths a validation error says the schema does not define, `a[0].b` style."""
    found = []
    for detail in error.errors():
        if detail["type"] == "extra_forbidden":
            path = ".".join(str(item) for item in detail["loc"])
            found.append(_PATH_INDEX.sub(r"[\1]", path))
    return found


def record_unknown_fields(
    ctx: ToolContext, fields: list[str], package_id: str | None
) -> None:
    """Ladder step 2: each unknown field becomes a generator-extension request."""
    with ctx.deps.session() as session:
        for name in fields:
            house_file.record_extension_request(
                session,
                name,
                ctx.last_message or "(no message)",
                package_id=package_id,
                thread_id=ctx.thread_id,
            )
        session.commit()


def extension_refusal(message: str, fields: list[str]) -> str:
    named = ", ".join(fields)
    return (
        f"{message}. The schema does not define {named}, so this cannot be expressed yet; "
        "the request has been recorded for the workshop. Tell the owner plainly that this "
        "cannot be done yet and was written down. Do not offer to write Blender code."
    )
