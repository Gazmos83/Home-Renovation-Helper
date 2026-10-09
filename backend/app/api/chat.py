"""The homeowner's conversation with the Foreman (homeowner-chat). Owner-gated.

A thread is started, listed, read and deleted; a turn is one message in and one reply out;
a gated action pauses the turn until the owner answers `yes` or `no` on the
thread. A running turn can be stopped, and the latest owner message edited and run again. A turn and an answer can also be followed as Server-Sent Events
(studio-chat-polish): each specialist and tool as it starts, then one ending event.
The response models and event bodies are the only exit: they have no field for a
model, a prompt, a token count, a cost or a file-system path (CLAUDE.md §1).
"""

from __future__ import annotations

import json
import logging
import queue
import shutil
import threading
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.agent import chat, house_file, progress, uploads
from app.api.gate import require_owner
from app.auth.sessions import AuthSessionRecord
from app.blender import storage

logger = logging.getLogger("app")

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_owner)])

MEMORY_DOWN = "the conversation memory is not available right now"
TURN_RUNNING = "a reply is still being written in this conversation; delete it once the turn has ended"

# The threads with a turn or a resume running in this process, so a delete cannot remove a
# conversation whose turn would write its memory again (piece-versions-and-chat-delete).
# The app runs one process, so this set is complete.
_running: set[UUID] = set()
_running_lock = threading.Lock()


class ThreadIn(BaseModel):
    title: str = Field(default="", max_length=200)
    package_id: str | None = None


class RenameIn(BaseModel):
    title: str = Field(max_length=400)

    @field_validator("title")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        trimmed = value.strip()
        if not 1 <= len(trimmed) <= 200:
            raise ValueError("the title must be 1 to 200 characters")
        return trimmed


class TurnIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    upload_ids: list[UUID] = Field(default_factory=list)


class EditIn(BaseModel):
    """The latest owner message, by id, and its new text (homeowner-chat)."""

    message_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=8000)


class ResumeIn(BaseModel):
    """The owner's answer to the pending item: `answer` (and an optional `reason`) for a
    confirmation; `answers` (one per question) or `declined` for a question set."""

    confirmation_id: str
    answer: Literal["yes", "no"] | None = None
    reason: str | None = Field(default=None, max_length=1000)
    answers: list[Annotated[str, Field(min_length=1, max_length=500)]] | None = None
    declined: str | None = Field(default=None, min_length=1, max_length=2000)

    def value_for(self, pending: chat.Pending) -> dict[str, Any] | str:
        """The resume value for `pending`, or why this answer does not fit it."""
        if pending.kind == "questions":
            if self.answer is not None or (self.answers is None) == (self.declined is None):
                return "answer the questions with one answer each, or decline them with a message"
            if self.declined is not None:
                return {"declined": self.declined.strip()}
            if len(self.answers or []) != len(pending.questions):
                return f"there are {len(pending.questions)} questions; send one answer for each"
            return {"answers": [a.strip() for a in self.answers or []]}
        if self.answer is None or self.answers is not None or self.declined is not None:
            return "answer the confirmation with yes or no"
        return {"answer": self.answer, "reason": self.reason}

    def said(self) -> str:
        """The answer as the trace's input."""
        if self.answer is not None:
            return self.answer
        return self.declined or "; ".join(self.answers or [])


class QuestionOut(BaseModel):
    text: str
    unit: str | None
    choices: list[str]


class PendingOut(BaseModel):
    confirmation_id: str
    kind: Literal["confirmation", "questions"]
    subject: str
    summary: str
    proposal: dict[str, Any]
    questions: list[QuestionOut]


class TurnOut(BaseModel):
    reply: str
    specialist: str | None
    pending: PendingOut | None


class ThreadOut(BaseModel):
    thread_id: UUID
    title: str
    package_id: str | None
    created_at: str
    last_turn_at: str


class AnswerRowOut(BaseModel):
    question: str
    answer: str


class MessageOut(BaseModel):
    role: Literal["owner", "assistant", "confirmation", "notice"]
    text: str
    # `answers` is an answered question set, shown as its `rows` (studio-chat-polish).
    kind: Literal["text", "answers"] = Field(default="text", exclude_if=lambda kind: kind == "text")
    rows: list[AnswerRowOut] | None = Field(default=None, exclude_if=lambda rows: rows is None)
    # The files sent with an owner's message; left out when none were.
    upload_ids: list[UUID] | None = Field(default=None, exclude_if=lambda ids: ids is None)
    # An owner's message's id, so the latest one can be edited; left out for the other roles.
    message_id: str | None = Field(default=None, exclude_if=lambda v: v is None)
    # A render notice (studio-layout): its outcome and tier, and for a piece version the
    # piece and version; all left out for the other roles.
    outcome: Literal["succeeded", "failed"] | None = Field(default=None, exclude_if=lambda v: v is None)
    tier: str | None = Field(default=None, exclude_if=lambda v: v is None)
    package_id: str | None = Field(default=None, exclude_if=lambda v: v is None)
    version: int | None = Field(default=None, exclude_if=lambda v: v is None)


class ThreadDetailOut(ThreadOut):
    messages: list[MessageOut]
    pending: PendingOut | None


class StepOut(BaseModel):
    step: str
    done: bool
    detail: str | None


class RequestOut(BaseModel):
    field: str
    request: str


class ProgressOut(BaseModel):
    package_id: str | None
    name: str | None
    latest_version: int | None
    approved_version: int | None
    build_status: str | None
    steps: list[StepOut]
    next_step: str
    open_review_items: int
    open_requests: list[RequestOut]
    screenshot: str | None
    still: str | None
    viewer: str | None
    # True while a render of the latest version is queued or running (studio-layout).
    rendering: bool = False


def _refusal(code: int, failure_class: str, reason: str) -> HTTPException:
    return HTTPException(code, detail={"failure_class": failure_class, "reason": reason})


def _graph(request: Request) -> Any:
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise _refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MEMORY_DOWN)
    return graph


def _thread_out(thread: Any) -> ThreadOut:
    return ThreadOut(
        thread_id=thread.id,
        title=thread.title,
        package_id=thread.package_id,
        created_at=thread.created_at.isoformat(),
        last_turn_at=thread.last_turn_at.isoformat(),
    )


def _pending_out(pending: chat.Pending | None) -> PendingOut | None:
    if pending is None:
        return None
    return PendingOut(
        confirmation_id=pending.confirmation_id,
        kind="questions" if pending.kind == "questions" else "confirmation",
        subject=pending.subject,
        summary=pending.summary,
        proposal=pending.proposal,
        questions=[
            QuestionOut(text=str(q.get("text", "")), unit=q.get("unit") or None, choices=list(q.get("choices") or []))
            for q in pending.questions
        ],
    )


def _pending_label(pending: chat.Pending) -> str:
    return "questions" if pending.kind == "questions" else f"{pending.subject} confirmation"


def _load_thread(request: Request, thread_id: UUID) -> Any:
    with Session(request.app.state.engine) as session:
        thread = house_file.get_thread(session, thread_id)
        if thread is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        session.expunge(thread)
        return thread


def _check_uploads(request: Request, thread_id: UUID, upload_ids: list[UUID]) -> None:
    """Every attached id must be an upload of this thread; images within the per-turn limit, one design."""
    if not upload_ids:
        return
    with Session(request.app.state.engine) as session:
        owned = {upload.id: upload.kind for upload in uploads.list_uploads(session, thread_id)}
    for upload_id in upload_ids:
        if upload_id not in owned:
            raise _refusal(422, "unknown_upload", f"upload {upload_id} does not belong to this conversation")
    limit = request.app.state.settings.turn_max_images
    if sum(1 for i in upload_ids if owned[i] in uploads.IMAGE_KINDS) > limit:
        raise _refusal(422, "too_many_images", f"a turn takes at most {limit} images")
    if sum(1 for i in upload_ids if owned[i] == "design") > 1:
        raise _refusal(422, "too_many_designs", "a turn takes at most one design file")


def _current_pending(request: Request, graph: Any, thread_id: UUID, owner: UUID) -> chat.Pending | None:
    try:
        return chat.pending(graph, thread_id=thread_id, owner_id=owner)
    except psycopg.OperationalError as error:
        logger.error("chat memory unavailable", extra={"context": {"error_type": type(error).__name__}})
        raise _refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MEMORY_DOWN) from None


@contextmanager
def _turn_running(request: Request, thread_id: UUID):
    """Mark the thread as running a turn; refuse one deleted meanwhile."""
    with _running_lock:
        with Session(request.app.state.engine) as session:
            if house_file.get_thread(session, thread_id) is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        _running.add(thread_id)
        chat.begin_turn(thread_id)
    try:
        yield
    finally:
        with _running_lock:
            chat.end_turn(thread_id)
            _running.discard(thread_id)


EventsFactory = Callable[[dict[str, Any]], Iterator[chat.TurnEvent]]


def _events(request: Request, thread: Any, owner: UUID, message: str, make_events: EventsFactory) -> Iterator[chat.TurnEvent]:
    """The turn's events inside its trace; the thread is touched once the turn has answered."""
    tracing = request.app.state.tracing
    result: chat.TurnResult | None = None
    with tracing.turn(
        owner_id=str(owner),
        session_id=str(thread.id),
        project_id=thread.package_id,
        input=message,
    ) as (config, trace_id):
        run_config = dict(config or {})
        run_config["configurable"] = {"trace_id": trace_id, "package_id": thread.package_id}
        for event in make_events(run_config):
            if event.result is not None:
                result = event.result
                tracing.record_output(result)
            yield event
        if result is not None and result.failure_class is None and not thread.title:
            title = _write_title(request, thread, owner, run_config)
            if title:
                yield chat.TurnEvent("title", {"title": title})
    if result is not None and result.failure_class is None:
        with Session(request.app.state.engine) as session:
            house_file.touch_thread(session, thread.id)
            session.commit()


def _write_title(request: Request, thread: Any, owner: UUID, run_config: dict[str, Any]) -> str | None:
    """Title an untitled thread after its first answered turn; an owner's title set
    meanwhile is kept. The title written, or `None`."""
    graph = request.app.state.graph
    title = chat.title_for(graph, thread_id=thread.id, owner_id=owner, run_config=run_config) if graph else None
    if not title:
        return None
    with Session(request.app.state.engine) as session:
        written = house_file.set_title_if_empty(session, thread.id, title)
        session.commit()
    return title if written else None


def _run(request: Request, thread: Any, owner: UUID, message: str, make_events: EventsFactory) -> TurnOut:
    """Run the turn to its end and answer from its result (the JSON routes)."""
    with _turn_running(request, thread.id):
        result = chat.final_result(_events(request, thread, owner, message, make_events))
    if result.failure_class is not None:
        code = {
            "unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
            "stopped": status.HTTP_409_CONFLICT,
        }.get(result.failure_class, status.HTTP_502_BAD_GATEWAY)
        raise _refusal(code, result.failure_class, result.failure_reason or "the turn failed")
    return TurnOut(
        reply=result.reply or "",
        specialist=result.specialist,
        pending=_pending_out(result.pending),
    )


def _event_body(event: chat.TurnEvent) -> dict[str, Any]:
    """An event's data as sent: role names, plain tool names, reply text, the pending item."""
    if event.kind == "pending":
        pending = _pending_out(event.data["pending"])
        return {"pending": pending.model_dump() if pending else None, "specialists": event.data["specialists"]}
    return dict(event.data)


def _sse(kind: str, data: dict[str, Any]) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream(request: Request, thread: Any, owner: UUID, message: str, make_events: EventsFactory) -> StreamingResponse:
    """Follow the turn as Server-Sent Events.

    The thread is marked running before the response opens, so a thread deleted
    meanwhile is still a 404 with no stream. The turn runs on its own thread and
    feeds a queue: a client that goes away stops reading, and the turn still
    finishes into the checkpointer.
    """
    running = ExitStack()
    running.enter_context(_turn_running(request, thread.id))
    events: queue.Queue[str | None] = queue.Queue()

    def work() -> None:
        try:
            for event in _events(request, thread, owner, message, make_events):
                events.put(_sse(event.kind, _event_body(event)))
        except Exception as error:  # noqa: BLE001 - the stream must still end
            logger.error("streamed turn failed", extra={"context": {"error_type": type(error).__name__}})
            events.put(_sse("error", {"failure_class": "internal", "reason": "the turn failed"}))
        finally:
            running.close()
            events.put(_sse("done", {}))
            events.put(None)

    threading.Thread(target=work, name=f"turn-{thread.id}", daemon=True).start()

    def body() -> Iterator[str]:
        while (chunk := events.get()) is not None:
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/threads", status_code=status.HTTP_201_CREATED)
def start_thread(body: ThreadIn, request: Request) -> ThreadOut:
    if body.package_id is not None:
        try:
            package_id = storage.validate_package_id(body.package_id)
        except storage.InvalidPackageId as error:
            raise _refusal(422, "invalid_package_id", str(error)) from None
        if not storage.versions(request.app.state.settings.render_root, package_id):
            raise _refusal(422, "unknown_package", f"there is no package {package_id!r}")
    with Session(request.app.state.engine) as session:
        thread = house_file.create_thread(session, body.title, package_id=body.package_id)
        session.commit()
        session.refresh(thread)
        return _thread_out(thread)


@router.get("/threads")
def list_threads(request: Request) -> list[ThreadOut]:
    with Session(request.app.state.engine) as session:
        return [_thread_out(thread) for thread in house_file.list_threads(session)]


@router.get("/threads/{thread_id}")
def read_thread(
    thread_id: UUID, request: Request, login: Annotated[AuthSessionRecord, Depends(require_owner)]
) -> ThreadDetailOut:
    thread = _load_thread(request, thread_id)
    graph = _graph(request)
    with Session(request.app.state.engine) as session:
        notices = house_file.notices_for(session, thread_id)
    try:
        messages = chat.history(graph, thread_id=thread_id, owner_id=login.user_id, notices=notices)
        waiting = chat.pending(graph, thread_id=thread_id, owner_id=login.user_id)
    except psycopg.OperationalError as error:
        logger.error("chat memory unavailable", extra={"context": {"error_type": type(error).__name__}})
        raise _refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MEMORY_DOWN) from None
    return ThreadDetailOut(
        **_thread_out(thread).model_dump(),
        messages=[MessageOut(**m) for m in messages],
        pending=_pending_out(waiting),
    )


@router.patch("/threads/{thread_id}")
def rename_thread(thread_id: UUID, body: RenameIn, request: Request) -> ThreadOut:
    """The owner's title; no generated title replaces it afterwards."""
    with Session(request.app.state.engine) as session:
        if not house_file.set_title(session, thread_id, body.title):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        session.commit()
        return _thread_out(house_file.get_thread(session, thread_id))


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: UUID, request: Request) -> Response:
    """Delete a conversation: its memory first, then its index entry (with its upload
    records and tool settings), then its upload files. Pieces and versions stay."""
    graph = _graph(request)
    with _running_lock:
        with Session(request.app.state.engine) as session:
            if house_file.get_thread(session, thread_id) is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        if thread_id in _running:
            raise _refusal(status.HTTP_409_CONFLICT, "turn_running", TURN_RUNNING)
        try:
            chat.forget(graph, thread_id)
        except Exception as error:  # noqa: BLE001 - any memory failure leaves everything in place
            logger.error("chat memory unavailable", extra={"context": {"error_type": type(error).__name__}})
            raise _refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MEMORY_DOWN) from None
        with Session(request.app.state.engine) as session:
            house_file.delete_thread(session, thread_id)
            session.commit()
    shutil.rmtree(request.app.state.settings.upload_root / str(thread_id), ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/threads/{thread_id}/progress")
def read_progress(
    thread_id: UUID, request: Request, login: Annotated[AuthSessionRecord, Depends(require_owner)]
) -> ProgressOut:
    thread = _load_thread(request, thread_id)
    graph = _graph(request)
    try:
        confirmed = chat.brief_confirmed(graph, thread_id=thread_id, owner_id=login.user_id)
    except psycopg.OperationalError as error:
        logger.error("chat memory unavailable", extra={"context": {"error_type": type(error).__name__}})
        raise _refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MEMORY_DOWN) from None
    with Session(request.app.state.engine) as session:
        found = progress.piece_progress(
            session,
            request.app.state.settings.render_root,
            thread.package_id,
            brief_confirmed=confirmed,
        )
    return ProgressOut(**found)


def _turn_factory(request: Request, thread_id: UUID, body: TurnIn, owner: UUID) -> tuple[Any, EventsFactory]:
    """Every refusal decided before the turn runs, then the turn's events."""
    thread = _load_thread(request, thread_id)
    graph = _graph(request)
    _check_uploads(request, thread_id, body.upload_ids)
    waiting = _current_pending(request, graph, thread_id, owner)
    if waiting is not None:
        raise _refusal(
            status.HTTP_409_CONFLICT,
            "confirmation_pending",
            f"answer the pending {_pending_label(waiting)} first",
        )

    def make_events(run_config: dict[str, Any]) -> Iterator[chat.TurnEvent]:
        return chat.turn_events(
            graph,
            thread_id=thread_id,
            owner_id=owner,
            message=body.message,
            upload_ids=body.upload_ids,
            run_config=run_config,
        )

    return thread, make_events


def _resume_factory(request: Request, thread_id: UUID, body: ResumeIn, owner: UUID) -> tuple[Any, EventsFactory]:
    thread = _load_thread(request, thread_id)
    graph = _graph(request)
    waiting = _current_pending(request, graph, thread_id, owner)
    if waiting is None or waiting.confirmation_id != body.confirmation_id:
        raise _refusal(
            status.HTTP_409_CONFLICT,
            "no_such_confirmation",
            "there is no pending confirmation with that id",
        )
    value = body.value_for(waiting)
    if isinstance(value, str):
        raise _refusal(422, "wrong_answer", value)

    def make_events(run_config: dict[str, Any]) -> Iterator[chat.TurnEvent]:
        return chat.resume_events(
            graph,
            thread_id=thread_id,
            owner_id=owner,
            value=value,
            run_config=run_config,
        )

    return thread, make_events


@router.post("/threads/{thread_id}/turns")
def send_turn(
    thread_id: UUID,
    body: TurnIn,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> TurnOut:
    thread, make_events = _turn_factory(request, thread_id, body, login.user_id)
    return _run(request, thread, login.user_id, body.message, make_events)


@router.post("/threads/{thread_id}/turns/stream", response_class=StreamingResponse)
def stream_turn(
    thread_id: UUID,
    body: TurnIn,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> StreamingResponse:
    thread, make_events = _turn_factory(request, thread_id, body, login.user_id)
    return _stream(request, thread, login.user_id, body.message, make_events)


@router.post("/threads/{thread_id}/turns/stop")
def stop_turn(thread_id: UUID, request: Request) -> dict[str, bool]:
    """Stop the thread's running turn at its next step; it ends its stream with `stopped`
    and is removed from the thread. A pending confirmation is not a running turn."""
    _load_thread(request, thread_id)
    if not chat.request_stop(thread_id):
        raise _refusal(status.HTTP_409_CONFLICT, "no_turn_running", "no reply is being written in this conversation")
    return {"stopping": True}


@router.post("/threads/{thread_id}/turns/latest", response_class=StreamingResponse)
def edit_latest_turn(
    thread_id: UUID,
    body: EditIn,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> StreamingResponse:
    """Replace the latest owner message and run it again, streamed like a turn.

    The thread is rewound to before that message; what the rewound turn confirmed stays
    and is named in the first event (`rewound`). Refused while a turn runs or an answer
    is pending, and for any message but the latest owner message."""
    thread = _load_thread(request, thread_id)
    graph = _graph(request)
    owner = login.user_id
    with _running_lock:
        if thread_id in _running:
            raise _refusal(status.HTTP_409_CONFLICT, "turn_running", "a reply is still being written; stop it or wait")
    waiting = _current_pending(request, graph, thread_id, owner)
    if waiting is not None:
        raise _refusal(
            status.HTTP_409_CONFLICT, "confirmation_pending", f"answer the pending {_pending_label(waiting)} first"
        )
    try:
        latest = chat.latest_owner_message_id(graph, thread_id=thread_id, owner_id=owner)
    except psycopg.OperationalError as error:
        logger.error("chat memory unavailable", extra={"context": {"error_type": type(error).__name__}})
        raise _refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MEMORY_DOWN) from None
    if latest is None or latest != body.message_id:
        raise _refusal(status.HTTP_409_CONFLICT, "not_latest", "only the latest message can be edited")

    def make_events(run_config: dict[str, Any]) -> Iterator[chat.TurnEvent]:
        # The rewind runs inside the turn, so no other turn can start in between.
        return chat.edit_events(
            graph, thread_id=thread_id, owner_id=owner, message_id=body.message_id,
            message=body.message, run_config=run_config,
        )

    return _stream(request, thread, owner, body.message, make_events)


@router.post("/threads/{thread_id}/resume")
def answer_confirmation(
    thread_id: UUID,
    body: ResumeIn,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> TurnOut:
    thread, make_events = _resume_factory(request, thread_id, body, login.user_id)
    return _run(request, thread, login.user_id, body.said(), make_events)


@router.post("/threads/{thread_id}/resume/stream", response_class=StreamingResponse)
def stream_answer(
    thread_id: UUID,
    body: ResumeIn,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> StreamingResponse:
    thread, make_events = _resume_factory(request, thread_id, body, login.user_id)
    return _stream(request, thread, login.user_id, body.said(), make_events)
