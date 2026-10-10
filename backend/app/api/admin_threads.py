"""Developer panel: one conversation's model calls (dev-panel; studio-chat-polish).

Every usage row records the conversation it was made for; this route lists a
conversation's rows newest first with the slot, the model slug and the token
figures. It sits behind the developer gate and no homeowner route links to it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import house_file
from app.api.gate import require_dev
from app.db.models import ModelUsage

router = APIRouter(prefix="/admin/threads", tags=["admin"], dependencies=[Depends(require_dev)])

# Calls made on the Foreman slot outside its routing decision.
FOREMAN_OPERATIONS = frozenset({"chat.title", "chat.summary"})


class CallOut(BaseModel):
    time: str
    slot: str
    operation: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    # True when the gateway reported no figures and `input_tokens` is the counted estimate.
    estimated: bool
    # The call's Langfuse trace page; `None` when tracing is off or the call has no trace (dev-panel-insights).
    trace_url: str | None = None


def slot_of(operation: str) -> str:
    """`chat.designer` → `designer`; a title or summary call is the Foreman's."""
    if operation in FOREMAN_OPERATIONS:
        return "foreman"
    return operation.removeprefix("chat.")


def _call(row: ModelUsage, tracing: Any = None) -> CallOut:
    estimated = row.input_tokens is None and row.output_tokens is None
    return CallOut(
        time=row.created_at.isoformat(),
        slot=slot_of(row.operation),
        operation=row.operation,
        model=row.model_id,
        input_tokens=row.estimated_tokens if estimated else row.input_tokens,
        output_tokens=None if estimated else row.output_tokens,
        estimated=estimated,
        trace_url=tracing.trace_url(row.trace_id) if tracing is not None else None,
    )


@router.get("/{thread_id}/calls")
def thread_calls(thread_id: UUID, request: Request) -> list[CallOut]:
    with Session(request.app.state.engine) as session:
        if house_file.get_thread(session, thread_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
        rows = session.scalars(
            select(ModelUsage)
            .where(ModelUsage.thread_id == thread_id)
            .order_by(ModelUsage.created_at.desc(), ModelUsage.id)
        ).all()
        tracing = getattr(request.app.state, "tracing", None)
        return [_call(row, tracing) for row in rows]
