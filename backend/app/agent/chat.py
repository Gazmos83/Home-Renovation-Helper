"""One owner turn through the Foreman graph, and the owner's answer to a pause.

`answer` runs a turn, `resume` answers the pending confirmation, `pending` reads
it, `history` reads the thread's messages. Both run through `run_events`, which
streams the graph and reports each specialist and tool as it starts, then one
ending event (studio-chat-polish), so the streamed and the JSON routes cannot
drift. A gateway failure on a turn forgets the unanswered message (the thread
never holds a question with no answer); absent memory is a stated failure,
never a half-stored turn.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import psycopg
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langgraph.types import Command

from app.agent import decision_summary, summaries, titles
from app.agent.models.openrouter_client import GatewayError

logger = logging.getLogger("app")

MEMORY_UNAVAILABLE_REASON = "the conversation memory is not available right now"


@dataclass(frozen=True)
class Pending:
    confirmation_id: str
    subject: str
    summary: str
    proposal: dict[str, Any]
    # `confirmation` or `questions` (studio-chat-polish); a question set has no subject,
    # summary or proposal, and a confirmation no questions.
    kind: str = "confirmation"
    questions: list[dict[str, Any]] = field(default_factory=list)
    # A question set's Workspace layout button: "room" for the placement questions (view-piece-in-room).
    layout: str | None = None
    # A confirmation's calculations, `{"columns", "rows"}` (confirmation-summaries).
    table: dict[str, Any] | None = None

    @property
    def title(self) -> str:
        return confirmation_title(self.subject)


@dataclass(frozen=True)
class TurnResult:
    reply: str | None = None
    specialist: str | None = None
    pending: Pending | None = None
    failure_class: str | None = None
    failure_reason: str | None = None
    # The specialists that ran in this turn, by role (studio-chat-polish). Reporting
    # detail, so it is left out of comparing two results.
    specialists: tuple[str, ...] = field(default=(), compare=False)
    trace_content_suppressed: bool = field(default=False, compare=False)


@dataclass(frozen=True)
class TurnEvent:
    """One step of a running turn: `specialist`, `tool`, or an ending event (`reply`,
    `pending`, `error`) that also carries the turn's `result`. `data` holds only
    role names, plain tool names, reply text and the pending item."""

    kind: str
    data: dict[str, Any] = field(default_factory=dict)
    result: TurnResult | None = None


ENDING_EVENTS = frozenset({"reply", "pending", "error", "stopped"})

# The stop signal of each thread's running turn (homeowner-chat, app-check-2026-10-09).
# Process-local: the app runs one process, so this registry is complete.
_stops: dict[UUID, threading.Event] = {}
_stops_lock = threading.Lock()


def begin_turn(thread_id: UUID) -> None:
    """Register a running turn of the thread, so it can be stopped."""
    with _stops_lock:
        _stops[thread_id] = threading.Event()


def end_turn(thread_id: UUID) -> None:
    with _stops_lock:
        _stops.pop(thread_id, None)


def request_stop(thread_id: UUID) -> bool:
    """Ask the thread's running turn to stop at its next step; whether one is running."""
    with _stops_lock:
        signal = _stops.get(thread_id)
        if signal is None:
            return False
        signal.set()
        return True


def _stop_signal(thread_id: UUID) -> threading.Event | None:
    with _stops_lock:
        return _stops.get(thread_id)


def plain_tool_name(tool: str) -> str:
    """How a tool is named to the owner while it runs: `revise_package` → `revise package`."""
    return tool.replace("_", " ")

def checkpoint_thread(thread_id: UUID) -> str:
    """The checkpointer's id for a conversation."""
    return f"chat:{thread_id}"


def forget(graph: Any, thread_id: UUID) -> None:
    """Delete a conversation's memory from the checkpointer (piece-versions-and-chat-delete)."""
    graph.checkpointer.delete_thread(checkpoint_thread(thread_id))


def _config(
    thread_id: UUID, owner_id: UUID, run_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    config = dict(run_config or {})
    config["configurable"] = {
        **config.get("configurable", {}),
        "thread_id": checkpoint_thread(thread_id),
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
        kind=str(value.get("kind") or "confirmation"),
        questions=[dict(q) for q in value.get("questions") or []],
        layout=value.get("layout") if value.get("layout") == "room" else None,
        table=_table(value.get("table")),
    )


def _table(value: Any) -> dict[str, Any] | None:
    """A confirmation's table as stored, or `None` when it has none or is malformed."""
    if not isinstance(value, dict) or not isinstance(value.get("columns"), list) or not isinstance(value.get("rows"), list):
        return None
    return {
        "columns": [str(c) for c in value["columns"]],
        "rows": [[str(cell) for cell in row] for row in value["rows"] if isinstance(row, list)],
    }


def _text(content: Any) -> str:
    return content if isinstance(content, str) else str(content)


def _last_assistant_text(state: dict[str, Any]) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage):
            return _text(message.content)
    return ""


def _result(state: dict[str, Any], interrupts: Any, specialists: tuple[str, ...]) -> TurnResult:
    specialist = state.get("specialist") or None
    if not specialists and specialist:
        # A resumed turn continues inside the specialist that paused; the Foreman does not choose again.
        specialists = (specialist,)
    return TurnResult(
        reply=_last_assistant_text(state),
        specialist=specialist,
        pending=_pending_of(interrupts[0]) if interrupts else None,
        specialists=specialists,
    )


def _unavailable() -> TurnResult:
    return TurnResult(failure_class="unavailable", failure_reason=MEMORY_UNAVAILABLE_REASON)


def _failed(result: TurnResult) -> TurnEvent:
    return TurnEvent(
        "error", {"failure_class": result.failure_class, "reason": result.failure_reason}, result
    )


def _ending(result: TurnResult) -> TurnEvent:
    if result.pending is not None:
        return TurnEvent("pending", {"pending": result.pending, "specialists": list(result.specialists)}, result)
    return TurnEvent("reply", {"reply": result.reply or "", "specialists": list(result.specialists)}, result)


def _stopped(started: list[str]) -> TurnEvent:
    text = "Stopped. This message and its replies were removed."
    if started:
        text += (
            f" Already started before the stop and not undone: {', '.join(dict.fromkeys(started))}; "
            "anything it finished stays."
        )
    return TurnEvent("stopped", {"text": text}, TurnResult(failure_class="stopped", failure_reason=text))


def run_events(
    graph: Any,
    graph_input: Any,
    config: dict[str, Any],
    *,
    human: HumanMessage | None = None,
    stop: threading.Event | None = None,
) -> Iterator[TurnEvent]:
    """Run the graph on `graph_input`, yielding each specialist and tool as it starts and
    then exactly one ending event. `human` is the turn's owner message, forgotten again
    when the gateway fails (a resume has none).

    When `stop` is set the turn ends at its next step with a `stopped` event, and the
    thread is rewound to before the owner's message. A model call already running
    finishes and is discarded; a tool that already ran is not undone."""
    specialists: list[str] = []
    started: list[str] = []
    stream = None
    try:
        if stop is not None and stop.is_set():
            yield _stopped(started)
            return
        stream = graph.stream(graph_input, config=config, stream_mode=["updates", "custom"], subgraphs=True)
        for _namespace, mode, chunk in stream:
            if mode == "custom" and isinstance(chunk, dict) and chunk.get("tool"):
                started.append(plain_tool_name(str(chunk["tool"])))
                yield TurnEvent("tool", {"plugin": started[-1]})
            elif mode == "updates" and isinstance(chunk, dict):
                role = (chunk.get("foreman") or {}).get("specialist") if isinstance(chunk.get("foreman"), dict) else None
                if role:
                    specialists.append(role)
                    yield TurnEvent("specialist", {"role": role})
            if stop is not None and stop.is_set():
                stream.close()
                _forget_unanswered(graph, config, human)
                yield _stopped(started)
                return
        snapshot = graph.get_state(config)
    except GatewayError as error:
        if human is not None:
            _forget_unanswered(graph, config, human)
        yield _failed(TurnResult(failure_class=error.error_class, failure_reason=error.reason))
        return
    except psycopg.OperationalError as error:
        _log_store_failure(error)
        yield _failed(_unavailable())
        return
    yield _ending(_result(snapshot.values, snapshot.interrupts, tuple(specialists)))


def owner_message(message: str, upload_ids: list[UUID] | None = None) -> HumanMessage:
    """The owner's message as stored: its text and the ids of the files sent with it."""
    return HumanMessage(
        message,
        id=str(uuid4()),
        additional_kwargs={"upload_ids": [str(i) for i in upload_ids]} if upload_ids else {},
    )


def turn_events(
    graph: Any,
    *,
    thread_id: UUID,
    owner_id: UUID,
    message: str,
    upload_ids: list[UUID] | None = None,
    run_config: dict[str, Any] | None = None,
) -> Iterator[TurnEvent]:
    """`run_events` for one owner turn."""
    if graph is None:
        yield _failed(_unavailable())
        return
    human = owner_message(message, upload_ids)
    yield from run_events(
        graph,
        {"messages": [human]},
        _config(thread_id, owner_id, run_config),
        human=human,
        stop=_stop_signal(thread_id),
    )


def resume_events(
    graph: Any,
    *,
    thread_id: UUID,
    owner_id: UUID,
    value: dict[str, Any],
    run_config: dict[str, Any] | None = None,
) -> Iterator[TurnEvent]:
    """`run_events` for the owner's answer to the pending item."""
    if graph is None:
        yield _failed(_unavailable())
        return
    yield from run_events(
        graph, Command(resume=value), _config(thread_id, owner_id, run_config), stop=_stop_signal(thread_id)
    )


def _first_sentence(text: str) -> str:
    return text.split(". ")[0].rstrip(".")


def latest_owner_message_id(graph: Any, *, thread_id: UUID, owner_id: UUID) -> str | None:
    """The id of the thread's latest owner message, if it has one. Raises on an unreachable store."""
    messages = graph.get_state(_config(thread_id, owner_id)).values.get("messages", [])
    owners = [m for m in messages if isinstance(m, HumanMessage)]
    return owners[-1].id if owners else None


def rewind_latest(
    graph: Any, *, thread_id: UUID, owner_id: UUID, message_id: str
) -> tuple[HumanMessage, list[str]] | str:
    """Remove the thread's latest owner message and every reply after it.

    The removed message, and each action the rewound turn confirmed (in the tool result's
    own words: these stay), or why nothing was rewound: `message_id` is not the latest
    owner message. Builds, versions, renders and house-file writes are never undone.
    """
    config = _config(thread_id, owner_id)
    messages = list(graph.get_state(config).values.get("messages", []))
    owners = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if not owners or messages[owners[-1]].id != message_id:
        return "only the latest message can be edited"
    start = owners[-1]
    kept = [
        _first_sentence(_text(m.content))
        for m in messages[start:]
        if isinstance(m, ToolMessage) and (m.additional_kwargs.get("confirmation") or {}).get("answer") == "yes"
    ]
    graph.update_state(config, {"messages": [RemoveMessage(id=m.id) for m in messages[start:]]})
    return messages[start], kept


def edit_events(
    graph: Any,
    *,
    thread_id: UUID,
    owner_id: UUID,
    message_id: str,
    message: str,
    run_config: dict[str, Any] | None = None,
) -> Iterator[TurnEvent]:
    """`run_events` for an edited latest message: the thread is rewound to before it, then
    the first event names what the rewound turn confirmed (it stays), then the new text
    runs as a turn with the replaced message's files."""
    if graph is None:
        yield _failed(_unavailable())
        return
    try:
        rewound = rewind_latest(graph, thread_id=thread_id, owner_id=owner_id, message_id=message_id)
    except psycopg.OperationalError as error:
        _log_store_failure(error)
        yield _failed(_unavailable())
        return
    if isinstance(rewound, str):
        yield _failed(TurnResult(failure_class="not_latest", failure_reason=rewound))
        return
    replaced, kept = rewound
    yield TurnEvent("rewound", {"kept": kept})
    upload_ids = [UUID(i) for i in replaced.additional_kwargs.get("upload_ids") or []]
    yield from turn_events(
        graph, thread_id=thread_id, owner_id=owner_id, message=message, upload_ids=upload_ids, run_config=run_config
    )


def final_result(events: Iterator[TurnEvent]) -> TurnResult:
    """The turn's result: run the events to their ending."""
    result = _unavailable()
    for event in events:
        if event.result is not None:
            result = event.result
    return result


def _log_store_failure(error: Exception) -> None:
    logger.error(
        "chat memory unavailable", extra={"context": {"error_type": type(error).__name__}}
    )


def _committed_messages(graph: Any, config: dict[str, Any]) -> list[Any]:
    """The thread's messages as last committed. A turn stopped inside a specialist leaves
    that specialist's writes pending; they are not in the stored messages, so a removal
    built from them would name ids that do not exist."""
    checkpointer = getattr(graph, "checkpointer", None)
    saved = checkpointer.get_tuple(config) if checkpointer is not None else None
    if saved is None:
        return list(graph.get_state(config).values.get("messages", []))
    return list(saved.checkpoint.get("channel_values", {}).get("messages", []))


def _forget_unanswered(graph: Any, config: dict[str, Any], human: HumanMessage | None) -> None:
    """Remove the failed turn from the thread, from the owner's message onward (without
    `human`, from the thread's last owner message: a stopped resume)."""
    try:
        messages = _committed_messages(graph, config)
        ids = [m.id for m in messages]
        if human is None:
            owners = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
            start = owners[-1] if owners else None
        else:
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
    """Run one turn of one thread for the owner. `upload_ids` are files from the thread."""
    return final_result(
        turn_events(
            graph,
            thread_id=thread_id,
            owner_id=owner_id,
            message=message,
            upload_ids=upload_ids,
            run_config=run_config,
        )
    )


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
    return final_result(
        resume_events(
            graph,
            thread_id=thread_id,
            owner_id=owner_id,
            value={"answer": answer_value, "reason": reason},
            run_config=run_config,
        )
    )


def title_for(
    graph: Any, *, thread_id: UUID, owner_id: UUID, run_config: dict[str, Any] | None = None
) -> str | None:
    """A title for the thread from the owner's first message, written by the Foreman slot's
    model or, when that call is refused or fails, cut from the message; `None` when the
    thread holds no owner message. Not stored here. Never raises."""
    config = _config(thread_id, owner_id, run_config)
    try:
        messages = graph.get_state(config).values.get("messages", [])
    except Exception as error:  # noqa: BLE001 - no title is better than a failed turn
        _log_store_failure(error)
        return None
    first = next((m for m in messages if isinstance(m, HumanMessage)), None)
    if first is None or not _text(first.content).strip():
        return None

    def call(system: str, prompt: list[Any], max_output: int) -> str:
        return graph.side_call("chat.title", system, prompt, max_output, config)

    return titles.title_for(call, _text(first.content))


def decision_for(
    graph: Any, *, thread_id: UUID, owner_id: UUID, message: str
) -> decision_summary.DecisionRow | None:
    """A chat message as one topic and one-line decision for the note (homeowner-chat), or `None`
    when the call is refused or fails. Nothing is stored. Never raises."""
    config = _config(thread_id, owner_id)

    def call(system: str, prompt: list[Any], max_output: int) -> str:
        return graph.side_call("chat.decision", system, prompt, max_output, config)

    return decision_summary.compress_message(call, message)


def compress(
    graph: Any, engine: Any, *, thread_id: UUID, owner_id: UUID, package_id: str | None, settings: Any
) -> str | None:
    """Write the active note over every exchange but the kept turns now (conversation-memory-settings);
    the note, or `None` when the call is refused or fails. Raises on an unreachable store."""
    config = _config(thread_id, owner_id)
    messages = list(graph.get_state(config).values.get("messages", []))

    def call(system: str, prompt: list[Any], max_output: int) -> str:
        return graph.side_call("chat.summary", system, prompt, max_output, config)

    return summaries.compress_now(engine, thread_id, call, messages, package_id, settings)


def pending(graph: Any, *, thread_id: UUID, owner_id: UUID) -> Pending | None:
    """The thread's pending confirmation, if any. Raises on an unreachable store."""
    snapshot = graph.get_state(_config(thread_id, owner_id))
    interrupts = snapshot.interrupts
    return _pending_of(interrupts[0]) if interrupts else None


def brief_confirmed(graph: Any, *, thread_id: UUID, owner_id: UUID) -> bool:
    """Whether a brief was confirmed in this thread. Raises on an unreachable store."""
    snapshot = graph.get_state(_config(thread_id, owner_id))
    return bool(snapshot.values.get("brief"))


def read_brief(graph: Any, *, thread_id: UUID, owner_id: UUID) -> dict[str, Any]:
    """The thread's confirmed brief, empty when none. Raises on an unreachable store."""
    return dict(graph.get_state(_config(thread_id, owner_id)).values.get("brief") or {})


def write_brief(graph: Any, *, thread_id: UUID, owner_id: UUID, brief: dict[str, Any]) -> None:
    """Replace the thread's brief (conversation-brief-panel). Raises on an unreachable store."""
    graph.update_state(_config(thread_id, owner_id), {"brief": brief})


# The owner's plain title for each confirmation subject; composed by code, never by a model,
# so no internal tool name reaches the owner (confirmation-summaries).
CONFIRMATION_TITLES: dict[str, str] = {
    "compose_room": "Composing room",
    "revise": "Revising piece",
    "rebuild": "Rebuilding piece",
    "create_piece": "Creating piece",
    "duplicate_piece": "Duplicating piece",
    "import_design": "Importing design",
    "import_version": "Importing version",
    "brief": "Confirming the brief",
    "plan": "Reading the plan",
    "room": "Confirming the room",
    "decisions": "Changing decisions",
    "final_render": "Final render",
    "detail_pass": "Detail pass",
    "detail_render": "Detail render",
    "remnant": "Recording a remnant",
    "version_verdict": "Rating the version",
    "render_feedback": "Rating the render",
    "assessment_inputs": "Engineering inputs",
}


def confirmation_title(subject: str) -> str:
    """The plain title of a confirmation subject; "Confirmation" for one with none."""
    return CONFIRMATION_TITLES.get(subject, "Confirmation")


def _confirmation_entry(answered: dict[str, Any]) -> dict[str, Any]:
    """One answered confirmation's history entry: the old one-line `text` plus its parts."""
    subject = str(answered.get("subject", ""))
    entry: dict[str, Any] = {
        "role": "confirmation",
        "text": _confirmation_line(answered),
        "subject": subject,
        "title": confirmation_title(subject),
        "summary": str(answered.get("summary", "")),
        "answer": "yes" if answered.get("answer") == "yes" else "no",
    }
    if answered.get("reason"):
        entry["reason"] = str(answered["reason"])
    table = _table(answered.get("table"))
    if table is not None:
        entry["table"] = table
    return entry


def _confirmation_line(answered: dict[str, Any]) -> str:
    """One answered confirmation as the owner saw it: subject, summary and answer."""
    line = f"{answered.get('subject', '')}: {answered.get('summary', '')} — {answered.get('answer', '')}"
    if answered.get("reason"):
        line += f" ({answered['reason']})"
    return line


def _notice_entry(notice: Any, links: Mapping[Any, list[dict[str, str]]] | None = None) -> dict[str, Any]:
    entry = {"role": "notice", "kind": notice.kind, "text": notice.text, "outcome": notice.outcome, "tier": notice.tier}
    if notice.package_id is not None and notice.version is not None:
        entry |= {"package_id": notice.package_id, "version": notice.version}
    found = (links or {}).get(getattr(notice, "id", None))
    if found:
        entry["links"] = found
    return entry


def history(
    graph: Any, *, thread_id: UUID, owner_id: UUID, notices: Sequence[Any] = (),
    notice_links: Mapping[Any, list[dict[str, str]]] | None = None,
) -> list[dict[str, Any]]:
    """The owner's messages (with the ids of the files sent with each), every reply with
    text, and each answered confirmation, in order.

    A reply sent together with tool calls is shown; tool calls, arguments and
    results are not. An answered confirmation is one line from the tool message
    it was recorded on; an answered question set is its question and answer rows,
    and a declined one the owner's own words (studio-chat-polish). Each of `notices`
    (in `after_messages` order) comes after the messages the thread held when it was posted
    (studio-layout), with its `notice_links` by notice id when it has any (room-render-notices).
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
    shown: list[dict[str, Any]] = []
    waiting_notices = list(notices)
    for position, message in enumerate(messages):
        while waiting_notices and waiting_notices[0].after_messages <= position:
            shown.append(_notice_entry(waiting_notices.pop(0), notice_links))
        if isinstance(message, HumanMessage):
            entry = {"role": "owner", "text": _text(message.content)}
            if message.id:
                entry["message_id"] = message.id
            if message.additional_kwargs.get("upload_ids"):
                entry["upload_ids"] = list(message.additional_kwargs["upload_ids"])
            shown.append(entry)
        elif isinstance(message, AIMessage) and _text(message.content).strip():
            shown.append({"role": "assistant", "text": _text(message.content)})
        elif isinstance(message, ToolMessage) and isinstance(message.additional_kwargs.get("confirmation"), dict):
            shown.append(_confirmation_entry(message.additional_kwargs["confirmation"]))
        elif isinstance(message, ToolMessage) and isinstance(message.additional_kwargs.get("answers"), dict):
            answered = message.additional_kwargs["answers"]
            if answered.get("declined"):
                shown.append({"role": "owner", "text": str(answered["declined"])})
            else:
                shown.append({"role": "assistant", "kind": "answers", "text": "", "rows": list(answered.get("rows") or [])})
    shown += [_notice_entry(notice, notice_links) for notice in waiting_notices]
    return shown
