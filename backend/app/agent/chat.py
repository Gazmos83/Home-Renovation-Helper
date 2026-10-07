"""One owner turn through the Foreman graph, and the owner's answer to a pause.

`answer` runs a turn, `resume` answers the pending confirmation, `pending` reads
it, `history` reads the thread's messages. A gateway failure on a turn forgets
the unanswered message (the thread never holds a question with no answer);
absent memory is a stated failure, never a half-stored turn.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import psycopg
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langgraph.types import Command

from app.agent.models.openrouter_client import GatewayError

logger = logging.getLogger("app")

MEMORY_UNAVAILABLE_REASON = "the conversation memory is not available right now"


@dataclass(frozen=True)
class Pending:
    confirmation_id: str
    subject: str
    summary: str
    proposal: dict[str, Any]


@dataclass(frozen=True)
class TurnResult:
    reply: str | None = None
    specialist: str | None = None
    pending: Pending | None = None
    failure_class: str | None = None
    failure_reason: str | None = None


def _config(
    thread_id: UUID, owner_id: UUID, run_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    config = dict(run_config or {})
    config["configurable"] = {
        **config.get("configurable", {}),
        "thread_id": f"chat:{thread_id}",
        "owner_id": str(owner_id),
        "chat_thread": str(thread_id),
    }
    return config


def _pending_of(interrupt_obj: Any) -> Pending:
    value = interrupt_obj.value or {}
    return Pending(
        confirmation_id=interrupt_obj.id,
        subject=str(value.get("subject", "")),
        summary=str(value.get("summary", "")),
        proposal=dict(value.get("proposal") or {}),
    )


def _text(content: Any) -> str:
    return content if isinstance(content, str) else str(content)


def _last_assistant_text(state: dict[str, Any]) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage):
            return _text(message.content)
    return ""


def _result(state: dict[str, Any]) -> TurnResult:
    interrupts = state.get("__interrupt__")
    if interrupts:
        return TurnResult(
            reply=_last_assistant_text(state),
            specialist=state.get("specialist") or None,
            pending=_pending_of(interrupts[0]),
        )
    return TurnResult(reply=_last_assistant_text(state), specialist=state.get("specialist") or None)


def _unavailable() -> TurnResult:
    return TurnResult(failure_class="unavailable", failure_reason=MEMORY_UNAVAILABLE_REASON)


def _log_store_failure(error: Exception) -> None:
    logger.error(
        "chat memory unavailable", extra={"context": {"error_type": type(error).__name__}}
    )


def _forget_unanswered(graph: Any, config: dict[str, Any], human: HumanMessage) -> None:
    """Remove the failed turn from the thread, from the owner's message onward."""
    try:
        snapshot = graph.get_state(config)
        messages = snapshot.values.get("messages", [])
        ids = [m.id for m in messages]
        start = ids.index(human.id) if human.id in ids else None
        if start is None:
            return
        graph.update_state(config, {"messages": [RemoveMessage(id=m.id) for m in messages[start:]]})
    except Exception as error:  # noqa: BLE001 - the failure is already being reported
        logger.warning(
            "could not remove an unanswered message",
            extra={"context": {"error_type": type(error).__name__}},
        )


def answer(
    graph: Any,
    *,
    thread_id: UUID,
    owner_id: UUID,
    message: str,
    upload_ids: list[UUID] | None = None,
    run_config: dict[str, Any] | None = None,
) -> TurnResult:
    """Run one turn of one thread for the owner. `upload_ids` are images from the thread."""
    if graph is None:
        return _unavailable()
    config = _config(thread_id, owner_id, run_config)
    human = HumanMessage(
        message,
        id=str(uuid4()),
        additional_kwargs={"upload_ids": [str(i) for i in upload_ids]} if upload_ids else {},
    )
    try:
        state = graph.invoke({"messages": [human]}, config=config)
    except GatewayError as error:
        _forget_unanswered(graph, config, human)
        return TurnResult(failure_class=error.error_class, failure_reason=error.reason)
    except psycopg.OperationalError as error:
        _log_store_failure(error)
        return _unavailable()
    return _result(state)


def resume(
    graph: Any,
    *,
    thread_id: UUID,
    owner_id: UUID,
    answer_value: str,
    reason: str | None = None,
    run_config: dict[str, Any] | None = None,
) -> TurnResult:
    """Answer the pending confirmation (`yes` or `no`); a second pause may follow."""
    if graph is None:
        return _unavailable()
    config = _config(thread_id, owner_id, run_config)
    try:
        state = graph.invoke(Command(resume={"answer": answer_value, "reason": reason}), config=config)
    except GatewayError as error:
        return TurnResult(failure_class=error.error_class, failure_reason=error.reason)
    except psycopg.OperationalError as error:
        _log_store_failure(error)
        return _unavailable()
    return _result(state)


def pending(graph: Any, *, thread_id: UUID, owner_id: UUID) -> Pending | None:
    """The thread's pending confirmation, if any. Raises on an unreachable store."""
    snapshot = graph.get_state(_config(thread_id, owner_id))
    interrupts = snapshot.interrupts
    return _pending_of(interrupts[0]) if interrupts else None


def brief_confirmed(graph: Any, *, thread_id: UUID, owner_id: UUID) -> bool:
    """Whether a brief was confirmed in this thread. Raises on an unreachable store."""
    snapshot = graph.get_state(_config(thread_id, owner_id))
    return bool(snapshot.values.get("brief"))


def _confirmation_line(answered: dict[str, Any]) -> str:
    """One answered confirmation as the owner saw it: subject, summary and answer."""
    line = f"{answered.get('subject', '')}: {answered.get('summary', '')} — {answered.get('answer', '')}"
    if answered.get("reason"):
        line += f" ({answered['reason']})"
    return line


def history(graph: Any, *, thread_id: UUID, owner_id: UUID) -> list[dict[str, str]]:
    """The owner's messages, every reply with text, and each answered confirmation, in order.

    A reply sent together with tool calls is shown; tool calls, arguments and
    results are not. An answered confirmation is one line from the tool message
    it was recorded on.
    """
    config = _config(thread_id, owner_id)
    snapshot = graph.get_state(config)
    messages = list(snapshot.values.get("messages", []))
    if snapshot.interrupts:
        # A paused specialist's messages stay in its own sub-graph until the owner answers;
        # its words before the card are shown now, above the pending confirmation.
        known = {m.id for m in messages}
        for task in graph.get_state(config, subgraphs=True).tasks:
            values = getattr(task.state, "values", None) or {}
            messages += [m for m in values.get("messages", []) if m.id not in known]
    shown = []
    for message in messages:
        if isinstance(message, HumanMessage):
            shown.append({"role": "owner", "text": _text(message.content)})
        elif isinstance(message, AIMessage) and _text(message.content).strip():
            shown.append({"role": "assistant", "text": _text(message.content)})
        elif isinstance(message, ToolMessage) and isinstance(message.additional_kwargs.get("confirmation"), dict):
            shown.append({"role": "confirmation", "text": _confirmation_line(message.additional_kwargs["confirmation"])})
    return shown
