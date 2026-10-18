"""The render notice: one line code posts into a conversation when a render that a
specialist's tool started there ends (studio-layout). The build notice: the same for a
build of a piece version (version-cleanup-and-inspection).

Written from the render's quote (or the build's piece and version) and outcome only, so
it never carries error text, a host path, a model slug or a token figure. It is stored
beside the thread, never in the checkpointed messages, so no model call ever reads it.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.agent import chat, house_file
from app.blender import storage
from app.feedback import runs as feedback_runs
from app.render.guard import RenderQuote

logger = logging.getLogger("app")

PANEL_SENTENCE = " You can also check it in the Piece panel."
ROOMS_SENTENCE = " You can also find it on the Rooms page."


def _what(quote: RenderQuote) -> str:
    kind = "still" if quote.kind == "still" else "turntable"
    if quote.source == "restyle":
        return "restyle"
    return f"detail {kind}" if quote.source == "detail" else kind


def _label(quote: RenderQuote) -> str:
    if quote.record == "shell":
        return f"the {quote.package_id} shell"
    return quote.package_id


def _message_count(deps: Any, thread_id: UUID) -> int:
    """How many checkpointed messages the thread holds, so history can place a notice."""
    graph = deps.graph
    if graph is None:
        raise RuntimeError("the conversation memory is not available")
    snapshot = graph.get_state({"configurable": {"thread_id": chat.checkpoint_thread(thread_id)}})
    return len(snapshot.values.get("messages", []))


def notice_text(quote: RenderQuote, outcome: str) -> str:
    """The notice's words, built here and nowhere else."""
    subject = f"The {quote.tier.name} {_what(quote)} of {_label(quote)} version {quote.version}"
    if outcome != "succeeded" and quote.source == "restyle":
        return f"{subject} did not finish for every variant; the ones that finished are ready. You can ask for the rest again."
    if outcome != "succeeded":
        return f"{subject} did not finish, so nothing new was published. You can ask for it again."
    if quote.record == "room":
        return f"{subject} is ready.{ROOMS_SENTENCE}"
    return f"{subject} is ready." + (PANEL_SENTENCE if quote.record == "piece" else "")


def post(deps: Any, thread_id: UUID | None, quote: RenderQuote, outcome: str) -> None:
    """Record the notice for a finished render. Never raises: a failure is logged and the
    render's own outcome stands."""
    if thread_id is None:
        return
    try:
        count = _message_count(deps, thread_id)
        piece = quote.record == "piece"
        room = quote.record == "room"
        key = storage.render_key(quote.kind, quote.room, quote.source)
        with deps.session() as session:
            house_file.add_notice(
                session,
                thread_id,
                after_messages=count,
                outcome="succeeded" if outcome == "succeeded" else "failed",
                tier=quote.tier.name,
                text=notice_text(quote, outcome),
                package_id=quote.package_id if piece else None,
                version=quote.version if piece or room else None,
                composition_slug=quote.package_id if room else None,
                render_key=key if room else None,
            )
            if room:
                house_file.stop_following_room_render(session, thread_id, quote.package_id, quote.version, key)
            session.commit()
    except Exception:
        logger.exception("could not post a render notice")


def follow_room(deps: Any, thread_id: UUID | None, quote: RenderQuote) -> None:
    """Record a room or apartment composition render the conversation started, so the
    thread's progress follows it until its notice is posted (room-render-notices). Never
    raises: a failure is logged and the render goes ahead."""
    if thread_id is None or quote.record != "room":
        return
    try:
        with deps.session() as session:
            house_file.follow_room_render(
                session, thread_id, quote.package_id, quote.version,
                storage.render_key(quote.kind, quote.room, quote.source),
            )
            session.commit()
    except Exception:
        logger.exception("could not record a room render to follow")


def finished(deps: Any, thread_id: UUID | None, run_id: Any, quote: RenderQuote, outcome: str) -> None:
    """What a conversation's render does when it ends: close its feedback run, then post
    the notice. The run is closed first so a notice problem never leaves it open."""
    feedback_runs.finish_run(deps.engine, run_id, outcome)
    post(deps, thread_id, quote, outcome)


# --- build notices (version-cleanup-and-inspection) -------------------------------------


def build_text(package_id: str, version: int, outcome: str) -> str:
    """A build notice's words, built here and nowhere else."""
    if outcome != "succeeded":
        return f"{package_id} version {version} did not build. You can ask for it again."
    return f"{package_id} version {version} is built."


def post_build(deps: Any, thread_id: UUID | None, package_id: str, version: int, outcome: str) -> None:
    """Record the notice for a finished build of a piece version. Never raises: a failure is
    logged and the build's own outcome stands."""
    if thread_id is None:
        return
    try:
        count = _message_count(deps, thread_id)
        outcome = "succeeded" if outcome == "succeeded" else "failed"
        with deps.session() as session:
            house_file.add_notice(
                session,
                thread_id,
                after_messages=count,
                outcome=outcome,
                kind="build",
                tier=None,
                text=build_text(package_id, version, outcome),
                package_id=package_id,
                version=version,
            )
            session.commit()
    except Exception:
        logger.exception("could not post a build notice")


def follow_build(deps: Any, thread_id: UUID | None, future: Any, package_id: str, version: int) -> None:
    """Post a build notice to the thread once the build `future` is done; the outcome is read
    from the version's status. Nothing for a build with no thread or no future."""
    if thread_id is None or future is None:
        return

    def done(_future: Any) -> None:
        try:
            state = storage.read_status(storage.version_dir(deps.render_root, package_id, version)) or {}
        except ValueError:
            state = {}
        post_build(deps, thread_id, package_id, version, str(state.get("status")))

    future.add_done_callback(done)


# --- revision notices (revision-link-button) -------------------------------------------


def revision_text(package_id: str, version: int) -> str:
    """A revision notice's words, built here and nowhere else."""
    return f"{package_id} version {version} is created."


def post_revision(deps: Any, thread_id: UUID | None, package_id: str, version: int) -> None:
    """Record the notice for a version a revision just recorded, before its build ends.
    Never raises: a failure is logged and the revision stands."""
    if thread_id is None:
        return
    try:
        count = _message_count(deps, thread_id)
        with deps.session() as session:
            house_file.add_notice(
                session,
                thread_id,
                after_messages=count,
                outcome="succeeded",
                kind="revision",
                tier=None,
                text=revision_text(package_id, version),
                package_id=package_id,
                version=version,
            )
            session.commit()
    except Exception:
        logger.exception("could not post a revision notice")
