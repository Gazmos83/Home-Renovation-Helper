"""Langfuse tracing: off unless configured, and never able to fail a turn.

Three properties the service-foundation spec requires, in the order they
matter:

1. **Off unless all three values are set.** A deployment that has not
   configured Langfuse behaves exactly as before, with no callback attached
   and nothing imported that could fail.
2. **Identity per turn.** Each turn carries the owner and the session, and the
   project when there is one, so cost and behaviour can be read per user, per
   session and per project.
3. **Never blocking, and quiet about it.** A Langfuse that is unreachable,
   slow or refusing must not delay, fail or alter an answer. LangChain
   swallows callback-handler exceptions by default and the SDK batches its
   exports on a background thread, so a broken endpoint costs a log line and
   nothing else. A handler that cannot even be constructed disables tracing for
   the process rather than raising into the request. The failure is logged
   *once per process*: the SDK exports through OpenTelemetry, whose exporter
   retries and logs every batch it cannot deliver, so `_ExportFailureOnce`
   collapses that stream into one record of our own.
"""

from __future__ import annotations

import dataclasses
import logging
import re
import threading
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from typing import Any, Final

from app.config import Settings

logger = logging.getLogger("app")

# Metadata keys the Langfuse LangChain integration reads off the run config.
USER_ID_KEY: Final = "langfuse_user_id"
SESSION_ID_KEY: Final = "langfuse_session_id"
TAGS_KEY: Final = "langfuse_tags"

# The name given to the root span a turn opens so its trace id is known before
# the model runs. Every model call the turn makes nests under it. Each route
# passes its own stable, verb-first name; this is the fallback and the trace's
# name.
TURN_SPAN_NAME: Final = "turn"
DEFAULT_TAGS: Final = ("home-renovation",)

# E-mail addresses are masked in everything exported: inputs, outputs and
# metadata of every observation, including the LangChain integration's.
_EMAIL: Final = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_MASK: Final = "[email]"


def mask_personal_data(*, data: Any, **_kwargs: Any) -> Any:
    """The Langfuse client's `mask` hook: replace e-mail addresses anywhere in
    exported data, recursively, leaving every other value as it was."""
    if isinstance(data, str):
        return _EMAIL.sub(EMAIL_MASK, data)
    if isinstance(data, dict):
        return {key: mask_personal_data(data=value) for key, value in data.items()}
    if isinstance(data, list | tuple):
        return type(data)(mask_personal_data(data=value) for value in data)
    # The SDK hands over raw objects before serialising them; a LangChain
    # message is a Pydantic model, which it would serialise to this same dict.
    # A graph node's output is a LangGraph `Command`, a dataclass.
    if callable(getattr(data, "model_dump", None)):
        return mask_personal_data(data=data.model_dump())
    if dataclasses.is_dataclass(data) and not isinstance(data, type):
        return mask_personal_data(
            data={field.name: getattr(data, field.name) for field in dataclasses.fields(data)}
        )
    return data


# The logger the Langfuse SDK's OpenTelemetry exporter reports through. It
# retries on a background thread, so an unreachable collector produces records
# for as long as the process lives unless they are collapsed.
EXPORTER_LOGGER: Final = "opentelemetry.exporter"


class _ExportFailureOnce(logging.Filter):
    """Lets the first export failure through as one record of ours, and drops
    every later one. Every other record passes untouched.

    It is installed on the *handler*, not on the exporter's logger. A filter on
    a logger only sees what is logged directly to it: a record from a child
    exporter logger propagates to its ancestors' handlers without their filters
    ever running, so a filter on `opentelemetry.exporter` would silently do
    nothing. It runs on the exporter's background thread, hence the lock.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self.reported = False

    def filter(self, record: logging.LogRecord) -> bool:
        if not record.name.startswith(EXPORTER_LOGGER) or record.levelno < logging.WARNING:
            return True
        with self._lock:
            first = not self.reported
            self.reported = True
        if first:
            logger.warning(
                "tracing export failed; further export failures are not logged",
                extra={"context": {"exporter": record.name}},
            )
        return False


class Tracing:
    """Per-turn run configuration for Langfuse, or nothing at all.

    Built once at startup and asked for a run config per turn. `enabled` is
    latched off the moment anything goes wrong, so a broken deployment logs
    once rather than on every turn.
    """

    def __init__(self, settings: Settings, *, handler_factory: Any | None = None) -> None:
        self._enabled = settings.tracing_enabled
        self._handler: Any | None = None
        self._client: Any | None = None
        self._warned: set[str] = set()
        self._warn_lock = threading.Lock()
        self._links_unavailable = False
        if not self._enabled:
            return
        self._export_filter = _ExportFailureOnce()
        for handler in logging.getLogger().handlers:
            handler.addFilter(self._export_filter)
        try:
            self._client, self._handler = (handler_factory or _build)(settings)
        except Exception as error:  # noqa: BLE001 - tracing must never break startup
            self._enabled = False
            logger.warning(
                "tracing disabled: the Langfuse handler could not be created",
                extra={"context": {"error_type": type(error).__name__}},
            )

    @property
    def enabled(self) -> bool:
        return self._enabled and self._handler is not None

    def _warn_once(self, message: str, error: Exception) -> None:
        """Report a tracing failure the first time it happens in this process."""
        with self._warn_lock:
            first = message not in self._warned
            self._warned.add(message)
        if first:
            logger.warning(message, extra={"context": {"error_type": type(error).__name__}})

    def _run_config(
        self,
        *,
        owner_id: str,
        session_id: str,
        project_id: str | None,
        tags: Sequence[str],
    ) -> dict[str, Any]:
        """The callback and identity metadata for one turn."""
        metadata: dict[str, Any] = {
            USER_ID_KEY: owner_id,
            SESSION_ID_KEY: session_id,
            TAGS_KEY: list(tags),
        }
        if project_id is not None:
            metadata["langfuse_project_id"] = project_id
        return {"callbacks": [self._handler], "metadata": metadata}

    def _open_trace(
        self,
        stack: ExitStack,
        *,
        owner_id: str,
        session_id: str,
        tags: Sequence[str],
        name: str,
        input: Any,
    ) -> str | None:
        """Open a root span whose trace id this process chose, or return `None`.

        The id has to exist *before* the model is called, because it is stored
        on every usage row the turn writes. Returning `None` costs the turn a
        trace link and nothing else.
        """
        try:
            trace_id: str = self._client.create_trace_id()
            stack.enter_context(
                self._client.start_as_current_observation(
                    name=name,
                    as_type="span",
                    trace_context={"trace_id": trace_id},
                    input=input,
                )
            )
        except Exception as error:  # noqa: BLE001 - a turn must answer without tracing
            self._warn_once("tracing could not open a trace for this turn", error)
            return None
        try:
            from langfuse import propagate_attributes

            stack.enter_context(
                propagate_attributes(
                    user_id=owner_id, session_id=session_id, tags=list(tags), trace_name=name
                )
            )
        except Exception as error:  # noqa: BLE001 - the metadata keys still carry identity
            self._warn_once("tracing could not propagate this turn's attributes", error)
        return trace_id

    @contextmanager
    def turn(
        self,
        *,
        owner_id: str,
        session_id: str,
        project_id: str | None = None,
        tags: Sequence[str] = DEFAULT_TAGS,
        name: str = TURN_SPAN_NAME,
        input: Any = None,
    ) -> Iterator[tuple[dict[str, Any] | None, str | None]]:
        """Run one turn inside its trace, yielding `(run_config, trace_id)`.

        `(None, None)` when tracing is off, so a caller needs no branch of its
        own. The trace id is `None` whenever tracing is on but the trace could
        not be opened; the turn still runs and is still recorded.
        """
        if not self.enabled:
            yield None, None
            return
        config = self._run_config(
            owner_id=owner_id, session_id=session_id, project_id=project_id, tags=tags
        )
        with ExitStack() as stack:
            trace_id = self._open_trace(
                stack, owner_id=owner_id, session_id=session_id, tags=tags, name=name, input=input
            )
            yield config, trace_id

    def record_output(self, result: Any) -> None:
        """Set the open turn's output from its result: the reply, or the failure
        class when there is none. Never raises."""
        if not self.enabled:
            return
        reply = getattr(result, "reply", None)
        failure = getattr(result, "failure_class", None)
        output: Any = reply if reply is not None else ({"failure_class": failure} if failure else None)
        if output is None:
            return
        try:
            self._client.update_current_span(output=output)
        except Exception as error:  # noqa: BLE001 - a turn must answer without tracing
            self._warn_once("tracing could not record this turn's output", error)

    def record_render(self, **fields: Any) -> None:
        """Record a render's tier, estimate and actual as a Langfuse event.

        A no-op when tracing is off; a failure is reported once per process and
        never reaches the render (render-guard).
        """
        if not self.enabled:
            return
        try:
            self._client.create_event(name="render", metadata=fields)
        except Exception as error:  # noqa: BLE001 - a render must not depend on tracing
            self._warn_once("tracing could not record a render event", error)

    def trace_url(self, trace_id: str | None) -> str | None:
        """The Langfuse page for a trace, or `None` when there is none to show."""
        if not trace_id or not self.enabled or self._links_unavailable:
            return None
        try:
            url: str | None = self._client.get_trace_url(trace_id=trace_id)
        except Exception as error:  # noqa: BLE001 - a board request must answer
            self._links_unavailable = True
            self._warn_once("tracing could not resolve trace links", error)
            return None
        return url

    def flush(self, timeout: float = 2.0) -> None:
        """Push whatever is buffered at shutdown. Never raises."""
        if self._client is None:
            return
        try:
            self._client.flush()
        except Exception as error:  # noqa: BLE001 - shutdown must not fail on this
            logger.warning(
                "tracing could not be flushed",
                extra={"context": {"error_type": type(error).__name__}},
            )


def _build(settings: Settings) -> tuple[Any, Any]:
    """Construct the client and handler. Imported lazily so an unconfigured
    deployment never pays for the SDK at all."""
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    assert settings.langfuse_public_key is not None
    assert settings.langfuse_secret_key is not None
    client = Langfuse(
        public_key=settings.langfuse_public_key.get_secret_value(),
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
        environment=settings.langfuse_tracing_environment,
        mask=mask_personal_data,
    )
    return client, CallbackHandler()
