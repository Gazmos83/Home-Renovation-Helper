"""The homeowner's conversation with the Foreman (homeowner-chat). Owner-gated.

A thread is started, listed and read; a turn is one message in and one reply out;
a gated action pauses the turn until the owner answers `yes` or `no` on the
thread. The response models are the only exit: they have no field for a model, a
prompt, a token count, a cost or a file-system path (CLAUDE.md §1).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent import chat, house_file, progress, uploads
from app.api.gate import require_owner
from app.auth.sessions import AuthSessionRecord
from app.blender import storage

logger = logging.getLogger("app")

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_owner)])

MEMORY_DOWN = "the conversation memory is not available right now"


class ThreadIn(BaseModel):
    title: str = Field(default="", max_length=200)
    package_id: str | None = None


class TurnIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    upload_ids: list[UUID] = Field(default_factory=list)


class ResumeIn(BaseModel):
    confirmation_id: str
    answer: Literal["yes", "no"]
    reason: str | None = Field(default=None, max_length=1000)


class PendingOut(BaseModel):
    confirmation_id: str
    subject: str
    summary: str
    proposal: dict[str, Any]


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


class MessageOut(BaseModel):
    role: Literal["owner", "assistant"]
    text: str


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
        subject=pending.subject,
        summary=pending.summary,
        proposal=pending.proposal,
    )


def _load_thread(request: Request, thread_id: UUID) -> Any:
    with Session(request.app.state.engine) as session:
        thread = house_file.get_thread(session, thread_id)
        if thread is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        session.expunge(thread)
        return thread


def _check_uploads(request: Request, thread_id: UUID, upload_ids: list[UUID]) -> None:
    """Every attached id must be an upload of this thread, and within the per-turn limit."""
    limit = request.app.state.settings.turn_max_images
    if len(upload_ids) > limit:
        raise _refusal(422, "too_many_images", f"a turn takes at most {limit} images")
    if not upload_ids:
        return
    with Session(request.app.state.engine) as session:
        owned = {upload.id for upload in uploads.list_uploads(session, thread_id)}
    for upload_id in upload_ids:
        if upload_id not in owned:
            raise _refusal(422, "unknown_upload", f"upload {upload_id} does not belong to this conversation")


def _current_pending(request: Request, graph: Any, thread_id: UUID, owner: UUID) -> chat.Pending | None:
    try:
        return chat.pending(graph, thread_id=thread_id, owner_id=owner)
    except psycopg.OperationalError as error:
        logger.error("chat memory unavailable", extra={"context": {"error_type": type(error).__name__}})
        raise _refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MEMORY_DOWN) from None


def _run(request: Request, thread: Any, owner: UUID, message: str, work) -> TurnOut:
    """Run `work(run_config)` inside the turn's trace and answer from its result."""
    tracing = request.app.state.tracing
    with tracing.turn(
        owner_id=str(owner),
        session_id=str(thread.id),
        project_id=thread.package_id,
        input=message,
    ) as (config, trace_id):
        run_config = dict(config or {})
        run_config["configurable"] = {"trace_id": trace_id, "package_id": thread.package_id}
        result: chat.TurnResult = work(run_config)
        tracing.record_output(result)

    if result.failure_class is not None:
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if result.failure_class == "unavailable"
            else status.HTTP_502_BAD_GATEWAY
        )
        raise _refusal(code, result.failure_class, result.failure_reason or "the turn failed")

    with Session(request.app.state.engine) as session:
        house_file.touch_thread(session, thread.id)
        session.commit()
    return TurnOut(
        reply=result.reply or "",
        specialist=result.specialist,
        pending=_pending_out(result.pending),
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
    try:
        messages = chat.history(graph, thread_id=thread_id, owner_id=login.user_id)
        waiting = chat.pending(graph, thread_id=thread_id, owner_id=login.user_id)
    except psycopg.OperationalError as error:
        logger.error("chat memory unavailable", extra={"context": {"error_type": type(error).__name__}})
        raise _refusal(status.HTTP_503_SERVICE_UNAVAILABLE, "unavailable", MEMORY_DOWN) from None
    return ThreadDetailOut(
        **_thread_out(thread).model_dump(),
        messages=[MessageOut(**m) for m in messages],
        pending=_pending_out(waiting),
    )


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


@router.post("/threads/{thread_id}/turns")
def send_turn(
    thread_id: UUID,
    body: TurnIn,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> TurnOut:
    thread = _load_thread(request, thread_id)
    graph = _graph(request)
    _check_uploads(request, thread_id, body.upload_ids)
    waiting = _current_pending(request, graph, thread_id, login.user_id)
    if waiting is not None:
        raise _refusal(
            status.HTTP_409_CONFLICT,
            "confirmation_pending",
            f"answer the pending {waiting.subject} confirmation first",
        )
    return _run(
        request,
        thread,
        login.user_id,
        body.message,
        lambda run_config: chat.answer(
            graph,
            thread_id=thread_id,
            owner_id=login.user_id,
            message=body.message,
            upload_ids=body.upload_ids,
            run_config=run_config,
        ),
    )


@router.post("/threads/{thread_id}/resume")
def answer_confirmation(
    thread_id: UUID,
    body: ResumeIn,
    request: Request,
    login: Annotated[AuthSessionRecord, Depends(require_owner)],
) -> TurnOut:
    thread = _load_thread(request, thread_id)
    graph = _graph(request)
    waiting = _current_pending(request, graph, thread_id, login.user_id)
    if waiting is None or waiting.confirmation_id != body.confirmation_id:
        raise _refusal(
            status.HTTP_409_CONFLICT,
            "no_such_confirmation",
            "there is no pending confirmation with that id",
        )
    return _run(
        request,
        thread,
        login.user_id,
        body.answer,
        lambda run_config: chat.resume(
            graph,
            thread_id=thread_id,
            owner_id=login.user_id,
            answer_value=body.answer,
            reason=body.reason,
            run_config=run_config,
        ),
    )
