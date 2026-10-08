"""The render notice: one line code posts into a conversation when a render that a
specialist's tool started there ends (studio-layout).

Written from the render's quote and outcome only, so it never carries error text, a
host path, a model slug or a token figure. It is stored beside the thread, never in the
checkpointed messages, so no model call ever reads it.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.agent import chat, house_file
from app.feedback import runs as feedback_runs
from app.render.guard import RenderQuote

logger = logging.getLogger("app")

PANEL_SENTENCE = " You can also check it in the Project panel."


def _what(quote: RenderQuote) -> str:
    kind = "still" if quote.kind == "still" else "turntable"
    return f"detail {kind}" if quote.source == "detail" else kind


def _label(quote: RenderQuote) -> str:
    if quote.record == "shell":
        return f"the {quote.package_id} shell"
    return quote.package_id


def notice_text(quote: RenderQuote, outcome: str) -> str:
    """The notice's words, built here and nowhere else."""
    subject = f"The {quote.tier.name} {_what(quote)} of {_label(quote)} version {quote.version}"
    if outcome != "succeeded":
        return f"{subject} did not finish, so nothing new was published. You can ask for it again."
    return f"{subject} is ready." + (PANEL_SENTENCE if quote.record == "piece" else "")


def post(deps: Any, thread_id: UUID | None, quote: RenderQuote, outcome: str) -> None:
    """Record the notice for a finished render. Never raises: a failure is logged and the
    render's own outcome stands."""
    if thread_id is None:
        return
    try:
        graph = deps.graph
        if graph is None:
            raise RuntimeError("the conversation memory is not available")
        snapshot = graph.get_state({"configurable": {"thread_id": chat.checkpoint_thread(thread_id)}})
        count = len(snapshot.values.get("messages", []))
        piece = quote.record == "piece"
        with deps.session() as session:
            house_file.add_notice(
                session,
                thread_id,
                after_messages=count,
                outcome="succeeded" if outcome == "succeeded" else "failed",
                tier=quote.tier.name,
                text=notice_text(quote, outcome),
                package_id=quote.package_id if piece else None,
                version=quote.version if piece else None,
            )
            session.commit()
    except Exception:
        logger.exception("could not post a render notice")


def finished(deps: Any, thread_id: UUID | None, run_id: Any, quote: RenderQuote, outcome: str) -> None:
    """What a conversation's render does when it ends: close its feedback run, then post
    the notice. The run is closed first so a notice problem never leaves it open."""
    feedback_runs.finish_run(deps.engine, run_id, outcome)
    post(deps, thread_id, quote, outcome)
