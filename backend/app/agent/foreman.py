"""The Foreman graph: one supervisor, four specialist sub-graphs.

`load_house` reads the house file and the thread, `foreman` chooses one
specialist (a structured decision from the `foreman` slot's model, then bounded
by code rules), and the chosen specialist — Intake, Designer, Builder,
Reviewer or Researcher — runs its own bounded `agent ⇄ tools` loop. One compiled graph on one
checkpointer thread means a paused confirmation resumes inside the specialist
that raised it.

Gated tools pause with `interrupt()` before they run: the first gated call in a
round is previewed by code, and only the owner's `yes` runs it. The model never
sees or changes a token budget, a model name or a path (CLAUDE.md §1, §4).
"""

from __future__ import annotations

import base64
import json
import logging
import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any, Final, Literal, TypedDict
from uuid import UUID

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app import compositions as composition_docs
from app.agent import house_file, progress, summaries, uploads
from app.agent.budget import BudgetRefused, RequestBudget, prepare, refusal_message
from app.agent.instructions import AgentInstruction, load_instructions
from app.agent.memory_settings import read_memory_settings
from app.agent.models.budgets import Budgets
from app.agent.models.openrouter_client import gateway_errors
from app.agent.models.routing import IMAGE_SLOTS
from app.agent.prompts import (
    DESIGNER_SHELF_DEPTHS_NOTE,
    DESIGNER_SIDE_FOLDS_NOTE,
    EMPTY_ANSWER_NOTE,
    FORMATTING_NOTE,
    OPEN_QUESTION_NOTE,
    TOOL_ROUND_CAP_NOTE,
    compose_agent_prompt,
    composition_note,
    house_note,
    neutralise,
    piece_note,
    render_feedback_note,
    wrap_note,
)
from app.agent.tools import loaded_plugins
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    Questions,
    ToolContext,
    ToolDeps,
    ToolOutput,
)
from app.agent.tools.shared import read_input
from app.assets import models as model_library
from app.blender import storage
from app.config import Settings
from app.design_import import unwrap
from app.engineering import chat as engineering_chat
from app.feedback import ratings, verdicts
from app.observability.usage import UsageRecorder, tokens_today
from app.packages.placements import read_placement
from app.plugins.binding import bound_tool_names
from app.plugins.loader import Plugins

logger = logging.getLogger("app")

MAX_TOOL_ROUNDS: Final = 6
SPECIALISTS: Final = ("intake", "designer", "builder", "lighting", "reviewer", "researcher")

TEMPLATES_DIR: Final = Path(__file__).resolve().parents[2] / "fixtures" / "packages" / "templates"

ONE_AT_A_TIME_NOTE: Final = (
    "Not run: only one confirmable action can be handled at a time. "
    "Propose any further action in a later step."
)
# How a refusal names the specialist that owns a tool (design-agents).
SPECIALIST_LABELS: Final[dict[str, str]] = {
    "intake": "Intake",
    "designer": "the Designer",
    "builder": "the Builder",
    "lighting": "Lighting & materials",
    "reviewer": "the Reviewer",
    "researcher": "the Researcher",
}
# The Foreman's fixed replies, composed by the application.
ROOM_QUESTION: Final = "Which room is this for?"
# Asked first; "Which room is this for?" follows only a yes (optional-room-question).
ROOM_OFFER: Final = "Would you like to view this piece in a room?"
ROOM_YES_WORDS: Final = frozenset({"yes", "ja", "yeah", "sure", "ok", "okay"})
# Kept so older threads that asked this still recognise the reply as the Foreman's.
WHICH_PIECE: Final = "Which piece do you mean: {names}?"
WHICH_PIECE_PREFIX: Final = "Which piece do you mean"
PIECE_HAS_CONVERSATION: Final = (
    "{piece} already has a conversation. Open it from the Pieces page."
)
# A design file named like an existing piece, in a conversation with no piece (delete-piece).
DESIGN_MATCHES_PIECE: Final = (
    "The attached design `{file}` matches your piece {name} (`{package_id}`). {update} "
    "To start over, delete {name} on the Pieces page, then attach the file again. "
    "To keep both, change the design's name and attach it again."
)
DESIGN_UPDATE_IN_CONVERSATION: Final = (
    "To update that piece, attach the file in its conversation (Pieces page → {name}) "
    "and it becomes the next version."
)
DESIGN_UPDATE_HERE: Final = "To update that piece, name {package_id} here and attach the file again."
# The turn's reply when a specialist answers empty twice (piece-versions-and-chat-delete).
EMPTY_REPLY: Final = "{role} gave no answer. Please rephrase your message or ask again."
_TOOL_NAME: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def tool_refusal(tool: str, specialist: str, owners: dict[str, list[str]]) -> str:
    """The fixed text for a call to a tool `specialist` has not bound; nothing ran."""
    named = owners.get(tool, [])
    if specialist in named:
        return f"`{tool}` is switched off for the whole service. Nothing was done."
    if named:
        who = " and ".join(SPECIALIST_LABELS.get(n, n) for n in named)
        return f"`{tool}` belongs to {who}, not to you. Nothing was done or saved."
    if _TOOL_NAME.match(tool):
        return f"There is no tool `{tool}`. Nothing was done."
    return "There is no such tool. Nothing was done."
DECLINED: Final[dict[str, str]] = {
    "brief": "The brief was not saved.",
    "plan": "The plan was not saved.",
    "create_piece": "The piece was not created.",
    "import_design": "The design was not imported.",
    "compose_room": "No room version was created.",
    "revise": "No revision was created.",
    "final_render": "The final render was not started.",
    "detail_pass": "The detail pass was not started.",
    "detail_render": "The detail render was not started.",
    "render_feedback": "The rating was not recorded.",
    "version_verdict": "The verdict was not recorded.",
    "remnant": "The remnant rack was not changed.",
}

ModelProvider = Callable[[str], Any]
ModelIds = Callable[[str], str]


def brief_line(brief: dict[str, Any]) -> str:
    """The brief's settings in one line for the agents' facts, `""` when it holds none."""
    parts = [
        ("room", brief.get("room")),
        ("purpose", brief.get("purpose")),
        ("highest the piece may be", f"{brief['max_piece_height_mm']:g} mm" if brief.get("max_piece_height_mm") else None),
        ("style", brief.get("style")),
        ("budget", f"{brief['budget_eur']:g} EUR" if brief.get("budget_eur") is not None else None),
    ]
    return "; ".join(f"{label}: {value}" for label, value in parts if value)


class ChatState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    specialist: str
    reason: str
    house_note: str
    piece_note: str
    feedback_note: str
    facts: str
    round_count: int
    package_id: str | None
    piece_ready: bool
    shell_ready: bool
    composition_ready: bool
    compose_ready: bool
    composition_note: str
    review_ready: bool
    detail_ready: bool
    image_attached: bool
    design_attached: bool
    # The piece an attached design file is named like, `{package_id, name, file, has_conversation}`.
    design_matches_piece: dict[str, Any] | None
    # A design file attached while no room was confirmed, `{"upload_id", "name"}`; Intake's turn
    # that confirms the room hands it to the Designer (pending-design-import).
    pending_design: dict[str, str] | None
    handoff_design: dict[str, str] | None
    piece_named: bool
    room_confirmed: bool
    room_named: bool
    room_asked: bool
    # The owner's answer to ROOM_OFFER on this turn: "room", "yes" or "no"; `None` otherwise.
    room_answer: str | None
    room_declined: bool
    build_room_ok: bool
    # view-piece-in-room: the latest version has a saved place in the confirmed room; the turn
    # asks to see the piece in it; `ask_placement` saved a place during this turn.
    placement_ready: bool
    views_in_room: bool
    placement_saved: bool
    ambiguous_pieces: list[str]
    piece_has_conversation: str | None
    brief: dict[str, Any]
    bound_tools: dict[str, list[str]]
    engineering_turn: bool
    # An open question asked before any room is settled; the Designer answers it with only
    # its guideline search (open-question-first-turn).
    open_question_turn: bool
    engineering_evidence_ids: list[str]
    engineering_metadata_ids: list[str]
    engineering_report_ids: list[str]
    engineering_assessment_ids: list[str]


class Decision(BaseModel):
    """The Foreman's choice for this turn."""

    specialist: Literal["intake", "designer", "builder", "lighting", "reviewer", "researcher"]
    reason: str = Field(description="one sentence")
    composes_room: bool = Field(
        default=False,
        description="true when the owner wants a room furnished or composed, not a piece designed",
    )
    engineering_question: bool = Field(default=False, description="asks for engineering evidence, strength, load capacity, deflection, anchorage or safety")
    requests_revision: bool = Field(default=False, description="asks to revise an existing piece, rather than only ask an engineering question")
    asks_help: bool = Field(
        default=False,
        description="true when the owner asks how to use the app, not for design, build, render, review or price work",
    )
    views_in_room: bool = Field(
        default=False,
        description="true when the owner wants to see the conversation's piece in its room (placed there, or a picture of it there)",
    )
    open_question: bool = Field(
        default=False,
        description="true when the owner asks a question or thinks aloud about a piece (sizes, heights, materials, ideas) without asking yet for anything to be designed, imported, built, rendered, reviewed or priced",
    )


def _image_blocks(
    engine: Engine, settings: Settings, upload_ids: list[str]
) -> tuple[list[dict[str, Any]], int]:
    """`image_url` blocks for the stored uploads, and how many could not be read."""
    blocks: list[dict[str, Any]] = []
    missing = 0
    with Session(engine) as session:
        for raw in upload_ids:
            upload = uploads.get_upload(session, UUID(raw))
            path = (
                uploads.upload_path(settings.upload_root, upload.thread_id, upload.id, upload.kind)
                if upload
                else None
            )
            if upload is None or path is None or not path.is_file():
                missing += 1
                continue
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            media = uploads.MEDIA_TYPES[upload.kind]
            blocks.append({"type": "image_url", "image_url": {"url": f"data:{media};base64,{data}"}})
    return blocks, missing


def _attached(engine: Engine, messages: list[AnyMessage]) -> tuple[bool, bool]:
    """Whether the newest owner message carries (an image, a design file)."""
    newest = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    ids = newest.additional_kwargs.get("upload_ids") if newest is not None else None
    if not ids:
        return False, False
    images, designs, _notes = _designs(engine, list(ids))
    return bool(images), bool(designs)


def _pending_design(engine: Engine, messages: list[AnyMessage]) -> dict[str, str] | None:
    """The newest design file any owner message carries, as `{"upload_id", "name"}`."""
    for message in reversed(messages):
        ids = message.additional_kwargs.get("upload_ids") if isinstance(message, HumanMessage) else None
        if ids:
            _images, designs, _notes = _designs(engine, list(ids))
            if designs:
                upload_id, name = designs[-1]
                return {"upload_id": upload_id, "name": name}
    return None


def _attached_design(engine: Engine, settings: Settings, messages: list[AnyMessage]) -> tuple[str, str | None] | None:
    """`(file name, name inside the design)` of the newest design file the newest owner
    message carries, read from the stored upload, never by a model; `None` without one."""
    newest = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    ids = newest.additional_kwargs.get("upload_ids") if newest is not None else None
    if not ids:
        return None
    _images, designs, _notes = _designs(engine, list(ids))
    if not designs:
        return None
    upload_id, file_name = designs[-1]
    with Session(engine) as session:
        upload = uploads.get_upload(session, UUID(upload_id))
        path = uploads.upload_path(settings.upload_root, upload.thread_id, upload.id, upload.kind) if upload else None
    try:
        document = json.loads(path.read_text(encoding="utf-8")) if path is not None else None
    except (OSError, ValueError):
        document = None
    build, _refusal = unwrap(document)
    name = build.get("name") if isinstance(build, dict) else None
    return file_name, name.strip() if isinstance(name, str) and name.strip() else None


def design_match(file_name: str, design_name: str | None, pieces: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The first piece the design file is named like: its file name without `.json` is the
    piece's id, its name made into an id is the id, or its name is the piece's name
    (ignoring case)."""
    stem = file_name[:-5] if file_name.casefold().endswith(".json") else file_name
    slug = None
    if design_name:
        try:
            slug = storage.apartment_slug(design_name)
        except storage.InvalidPackageId:
            slug = None
    for piece in pieces:
        if stem == piece["package_id"] or slug == piece["package_id"] or (
            design_name and design_name.casefold() == str(piece["name"]).casefold()
        ):
            return piece
    return None


def _designs(
    engine: Engine, upload_ids: list[str]
) -> tuple[list[str], list[tuple[str, str]], list[tuple[str, UUID, UUID]]]:
    """Among `upload_ids`: the image ids, `(id, file name)` of each design file, and
    `(file name, thread id, upload id)` of each text note."""
    images: list[str] = []
    designs: list[tuple[str, str]] = []
    notes: list[tuple[str, UUID, UUID]] = []
    with Session(engine) as session:
        for raw in upload_ids:
            upload = uploads.get_upload(session, UUID(raw))
            if upload is not None and upload.kind == "design":
                designs.append((raw, upload.original_name))
            elif upload is not None and upload.kind == "text":
                notes.append((upload.original_name, upload.thread_id, upload.id))
            else:
                images.append(raw)
    return images, designs, notes


def _note_text(name: str, path: Path) -> str:
    """One attached note as a delimited untrusted block, or a line saying it is gone."""
    if not path.is_file():
        return f"\n(The owner attached the note '{neutralise(name)}', which is no longer available.)"
    return "\n\n" + wrap_note(name, path.read_text(encoding="utf-8"))


def with_attachments(
    messages: list[AnyMessage], *, capable: bool, engine: Engine, settings: Settings, engineering: bool = False
) -> list[AnyMessage]:
    """Expand attached upload ids for the model call; the stored messages are untouched.

    An image-capable slot receives each image beside the owner's text; any other
    slot receives a note that images were attached, never the images. A design
    file is never sent: every slot receives a note naming it and its upload id.
    Every slot receives each text note's content inside the untrusted-content
    delimiters, named by its file (studio-chat-polish).
    """
    expanded: list[AnyMessage] = []
    for message in messages:
        ids = message.additional_kwargs.get("upload_ids") if isinstance(message, HumanMessage) else None
        if not ids:
            expanded.append(message)
            continue
        image_ids, designs, notes = _designs(engine, list(ids))
        text = _text_of(message.content)
        for upload_id, name in designs:
            text += (
                f"\n(The owner attached the design file '{neutralise(name)}' as upload {upload_id}; "
                "import it with import_design.)"
            )
        for name, thread_id, upload_id in notes:
            if engineering:
                text += "\nAttached note content is unavailable as engineering evidence until registered with documented source rights."
            else:
                text += _note_text(name, uploads.upload_path(settings.upload_root, thread_id, upload_id, "text"))
        if not image_ids:
            content: Any = text
        elif capable:
            blocks, missing = _image_blocks(engine, settings, image_ids)
            if missing:
                text += f"\n(The owner attached {missing} image(s) that are no longer available.)"
            content = [{"type": "text", "text": text}, *blocks]
        else:
            content = f"{text}\n(The owner attached {len(image_ids)} image(s); Intake reads them.)"
        expanded.append(HumanMessage(content, id=message.id, additional_kwargs=message.additional_kwargs))
    return expanded


def _text_of(content: Any) -> str:
    return content if isinstance(content, str) else str(content)


def is_empty_answer(reply: Any) -> bool:
    """A final answer with no tool call and no text (string or text blocks) for the owner."""
    if getattr(reply, "tool_calls", None):
        return False
    content = getattr(reply, "content", "")
    if isinstance(content, str):
        return not content.strip()
    texts = [
        part if isinstance(part, str) else str(part.get("text", ""))
        for part in content
        if isinstance(part, str) or (isinstance(part, dict) and part.get("type") == "text")
    ]
    return not "".join(texts).strip()


def with_callbacks(config: RunnableConfig, *handlers: Any) -> RunnableConfig:
    """`config` with extra callback handlers, whatever form its callbacks take."""
    existing = config.get("callbacks")
    if existing is None:
        merged: Any = list(handlers)
    elif isinstance(existing, list):
        merged = [*existing, *handlers]
    else:  # a callback manager: copy it so the node's own is untouched
        merged = existing.copy()
        for handler in handlers:
            merged.add_handler(handler, inherit=True)
    return {**config, "callbacks": merged}


def _last_ai_tool_calls(state: ChatState) -> list[dict[str, Any]]:
    for message in reversed(state.get("messages", [])):
        if getattr(message, "type", None) == "ai":
            return list(getattr(message, "tool_calls", None) or [])
    return []


def _latest_texts(messages: list[AnyMessage]) -> tuple[str, str]:
    """The owner's latest message and the last reply with text before it."""
    owner = ""
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and not owner:
            owner = _text_of(message.content)
        elif owner and isinstance(message, AIMessage) and _text_of(message.content).strip():
            return owner, _text_of(message.content)
    return owner, ""


def _whole_word(word: str, lowered: str) -> bool:
    return bool(word) and bool(re.search(rf"(?<![\w-]){re.escape(word.casefold())}(?![\w-])", lowered))


def _pieces_in(text: str, pieces: list[dict[str, Any]]) -> list[str]:
    """The package ids `text` names: by package id (a whole word) first, else by name."""
    lowered = text.casefold()
    by_id = [str(p["package_id"]) for p in pieces if _whole_word(str(p["package_id"]), lowered)]
    if by_id:
        return by_id
    return [
        str(p["package_id"])
        for p in pieces
        if (name := str(p.get("name") or "").casefold().strip()) and name in lowered
    ]


def piece_named(messages: list[AnyMessage], pieces: list[dict[str, Any]]) -> list[str]:
    """The house-file pieces the owner's latest message names; when it names none, the ones
    the last reply before it names (not the reply that asked which piece, or the owner's
    answer to it would be asked again). By package id as a whole word, else by name."""
    owner, reply = _latest_texts(messages)
    found = _pieces_in(owner, pieces)
    if found or not reply or reply.startswith(WHICH_PIECE_PREFIX):
        return found
    return _pieces_in(reply, pieces)


def room_named(
    messages: list[AnyMessage], rooms: list[dict[str, Any]], apartments: list[dict[str, Any]]
) -> bool:
    """Whether the owner's latest message names a room or apartment of the house file as a
    whole word, in any case."""
    lowered = _latest_texts(messages)[0].casefold()
    return any(_whole_word(str(item["name"]), lowered) for item in [*rooms, *apartments])


def room_answer(messages: list[AnyMessage], *, names_room: bool) -> str | None:
    """How the owner's latest message answers ROOM_OFFER, read by code: "room" when it names
    a room (or carries a plan or photo, `names_room`), "yes" when its first word is a yes,
    else "no"; `None` when the last reply was not ROOM_OFFER."""
    owner, reply = _latest_texts(messages)
    if reply.strip() != ROOM_OFFER:
        return None
    if names_room:
        return "room"
    words = owner.split()
    first = re.sub(r"[^\w]", "", words[0]).casefold() if words else ""
    return "yes" if first in ROOM_YES_WORDS else "no"


def room_question_asked(messages: list[AnyMessage]) -> bool:
    """Whether the last reply with text before the owner's message was the room question."""
    return _latest_texts(messages)[1].strip() == ROOM_QUESTION


def _last_human_text(state: ChatState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _designer_note() -> str:
    templates = []
    for name in ("custom-build", "fold-down-desk", "blank-build"):
        document = json.loads((TEMPLATES_DIR / f"{name}.json").read_text(encoding="utf-8"))
        templates.append(f"Template {name}:\n{json.dumps(document, separators=(',', ':'))}")
    return (
        "A custom_build document is positioned modules (boxes, in whole millimetres) with "
        "shelves, fronts (door, drawer, flap) and optional side_folds (a carcass-side bend: "
        "side, from_mm, along, angle_deg, towards), drawing materials from named slots. "
        "Start from the custom-build template unless another one fits the brief better, and "
        "change only what the brief supports.\n\n"
        + "\n\n".join(templates)
    )


def _confirmation_payload(confirmation: Confirmation, tool: str) -> dict[str, Any]:
    return {
        "kind": "confirmation",
        "tool": tool,
        "subject": confirmation.subject,
        "summary": confirmation.summary,
        "proposal": confirmation.proposal,
    }


def _questions_payload(questions: Questions, tool: str) -> dict[str, Any]:
    payload = {"kind": "questions", "tool": tool, "questions": questions.questions}
    if questions.layout:
        payload["layout"] = questions.layout
    return payload


def _answered_rows(questions: Questions, answer: Any) -> dict[str, Any]:
    """An answered question set as the owner saw it, kept for the history (studio-chat-polish)."""
    answer = answer if isinstance(answer, dict) else {}
    declined = answer.get("declined")
    if isinstance(declined, str) and declined.strip():
        return {"rows": [], "declined": declined.strip()}
    given = list(answer.get("answers") or [])
    rows = []
    for index, question in enumerate(questions.questions):
        value = str(given[index]) if index < len(given) else ""
        unit = question.get("unit")
        rows.append({"question": question["text"], "answer": f"{value} {unit}" if unit and value else value})
    return {"rows": rows, "declined": None}


def build_graph(
    engine: Engine,
    settings: Settings,
    *,
    model_provider: ModelProvider,
    model_ids: ModelIds,
    checkpointer: Any,
    deps: ToolDeps,
    instructions: dict[str, AgentInstruction] | None = None,
    plugins: Plugins | None = None,
    budgets: Budgets | None = None,
):
    """Compile the Foreman graph on `checkpointer`."""
    loaded = instructions or load_instructions()
    # Which specialists' headers name each tool, for an honest refusal of a call outside the bound set.
    owners: dict[str, list[str]] = {}
    for specialist in SPECIALISTS:
        for tool_name in loaded[specialist].tools:
            owners.setdefault(tool_name, []).append(specialist)
    loaded_plugins_set = plugins or loaded_plugins()
    budget_store = budgets or Budgets(engine)
    tools_by_name = dict(loaded_plugins_set.builtin_tools())
    for plugin in loaded_plugins_set.https_plugins():
        tools_by_name.update(plugin.tools)
    designer_note = _designer_note()

    def plugin_name(tool: str) -> str:
        """The plugin a tool comes from, named to the owner while it runs (studio-chat-polish)."""
        plugin = loaded_plugins_set.plugin_for_tool(tool)
        return plugin.name if plugin is not None else tool

    # --- context ------------------------------------------------------------

    def load_house(state: ChatState, config: RunnableConfig) -> dict[str, Any]:
        configurable = config.get("configurable", {})
        messages = state.get("messages", [])
        # What the conversation's slice includes (conversation-memory-settings); the room and
        # conversation scoping below is not behind any setting.
        memory = read_memory_settings(engine)
        with Session(engine) as session:
            stored_rooms = house_file.rooms(session)
            preferences = house_file.preferences(session) if memory.include_preferences else {}
            all_pieces = house_file.pieces(session, settings.render_root)
            piece_rooms = house_file.piece_room_names(session)
            thread = None
            raw_thread = configurable.get("chat_thread")
            if raw_thread:
                thread = house_file.get_thread(session, UUID(str(raw_thread)))
            thread_id = thread.id if thread else None
            scope_room, scope_apartment = (
                house_file.thread_scope(session, thread_id) if thread_id else (None, None)
            )
            scope_rooms = (
                [scope_room]
                if scope_room is not None
                else (house_file.rooms_of(session, scope_apartment) if scope_apartment is not None else [])
            )
            scope_room_names = {room.name for room in scope_rooms}
            # Plain names: a commit below expires the rows, and they are read after the session.
            scope_room_name = scope_room.name if scope_room is not None else None
            scope_apartment_name = scope_apartment.name if scope_apartment is not None else None
            apartments = []
            if scope_apartment is not None:
                try:
                    built = storage.shell_versions(
                        settings.render_root, storage.apartment_slug(scope_apartment.name)
                    )
                except storage.InvalidPackageId:
                    built = []
                apartments.append(
                    {
                        "name": scope_apartment.name,
                        "rooms": len(scope_rooms),
                        "shell_version": built[-1] if built else None,
                    }
                )
            # One piece per conversation: bind only while unbound, and only when the named
            # piece has no conversation of its own yet.
            active = thread.package_id if thread and thread.package_id else None
            matches = piece_named(messages, all_pieces)
            piece_taken: str | None = None
            if active is None and len(matches) == 1 and thread_id is not None:
                named = matches[0]
                existing = house_file.thread_id_for_piece(session, named)
                if existing is None:
                    house_file.set_active_build(session, thread_id, named)
                    session.commit()
                    active = named
                elif existing != thread_id:
                    piece_taken = named
            build_ids = [active] if active else []
            ambiguous: list[str] = []
            requests = [
                {"field": r.field, "request": r.request}
                for r in house_file.open_extension_requests(
                    session, package_ids=build_ids, thread_id=thread_id
                )
            ] if memory.include_extension_requests else []
            tools_this_turn = {
                name: bound_tool_names(
                    session,
                    loaded_plugins_set,
                    thread_id=thread_id,
                    role=name,
                    header_tools=loaded[name].tools,
                )
                for name in SPECIALISTS
            }
            approved = {
                p["package_id"]: p["approved_version"] for p in all_pieces if p["approved_version"]
            }
            room_confirmed = scope_room is not None or scope_apartment is not None
            room_is_named = room_named(
                messages,
                [house_file.describe_room(r) for r in stored_rooms],
                [{"name": a.name} for a in house_file.apartments(session)],
            )
            # The answer to "Would you like to view this piece in a room?" (optional-room-question).
            room_declined = bool(thread is not None and thread.room_declined)
            answer = None
            if not room_confirmed and not room_declined:
                answer = room_answer(messages, names_room=room_is_named or _attached(engine, messages)[0])
                if answer == "no" and thread_id is not None:
                    house_file.decline_room(session, thread_id)
                    session.commit()
                    room_declined = True
        package_id = active or state.get("package_id")
        bound = next((p for p in all_pieces if p["package_id"] == package_id), None)
        piece_ready = bool(bound and bound["latest_version"])
        review_ready = progress.review_ready(
            settings.render_root, package_id, bound["latest_version"] if bound else None
        )
        detail_ready = progress.detail_ready(
            settings.render_root, package_id, bound["latest_version"] if bound else None
        )
        piece_text = ""
        if bound and bound["latest_version"]:
            try:
                document = read_input(storage.version_dir(settings.render_root, package_id, bound["latest_version"]))
            except ValueError:
                document = None
            piece_text = piece_note(package_id, bound["latest_version"], document)
            from app.engineering.reports import active_report_statuses
            with Session(engine) as session:
                report_statuses = active_report_statuses(session, settings.render_root, package_id)
            if report_statuses:
                piece_text += "\nEngineering report IDs/status (fetch complete current evidence; visual approval does not verify engineering): " + json.dumps(report_statuses)
        placement_ready = bool(
            bound
            and bound["latest_version"]
            and scope_room_name is not None
            and read_placement(storage.version_dir(settings.render_root, package_id, bound["latest_version"]), scope_room_name)
        )
        open_review = []
        recent_feedback: list[dict[str, Any]] = []
        open_verdicts: list[dict[str, Any]] = []
        if package_id:
            with Session(engine) as session:
                # The approved version's review, else the latest's; an older version's items stay stored.
                current = bound["approved_version"] or bound["latest_version"] if bound else None
                if memory.include_review_items and current:
                    open_review = house_file.latest_open_items(session, package_id, current)
                if memory.render_ratings:
                    recent_feedback = ratings.recent_for_piece(session, package_id, memory.render_ratings)
                if memory.include_version_verdicts:
                    open_verdicts = verdicts.open_for_piece(session, package_id)

        def with_room(piece: dict[str, Any]) -> dict[str, Any]:
            return {**piece, "room": piece_rooms.get(piece["package_id"])}

        if bound:
            latest = f"version {bound['latest_version']}" if bound["latest_version"] else "no version"
            status = f", {bound['status']}" if bound["status"] else ""
            approved_text = f"v{bound['approved_version']}" if bound["approved_version"] else "none"
            piece_line = f"{package_id} ({latest}{status}, approved: {approved_text})"
        else:
            piece_line = "none"
        confirmed = "yes" if state.get("brief") else "no"
        if scope_room_name is not None:
            room_fact = f"room {scope_room_name}"
        elif scope_apartment_name is not None:
            room_fact = f"apartment {scope_apartment_name}"
        elif room_declined:
            room_fact = "no room (the owner chose not to view this piece in a room; do not ask for one)"
        else:
            room_fact = "no room confirmed yet"
        shell_ready = any(a["shell_version"] for a in apartments)
        with Session(engine) as session:
            composed = [
                c
                for c in house_file.compositions(session, settings.render_root)
                if (c["scope"] == "room" and c["name"] in scope_room_names)
                or (c["scope"] == "apartment" and c["name"] == scope_apartment_name)
            ]
            ready_models = [
                {"id": str(m.id), "name": m.name, "width_mm": m.width_mm, "depth_mm": m.depth_mm, "height_mm": m.height_mm}
                for m in model_library.list_models(session)
                if m.state == "ready"
            ]
        composition_ready = any(c["status"] == "succeeded" for c in composed)
        # Something to compose a room from: the confirmed room when the owner's message names
        # it (it may be composed empty, rooms-page), an approved piece version in the confirmed
        # scope, or a composition there.
        compose_ready = (
            bool(composed)
            or (scope_room_name is not None and room_named(messages, [{"name": scope_room_name}], []))
            or any(piece_rooms.get(piece_id) in scope_room_names for piece_id in approved)
        )
        facts = f"This conversation: piece {piece_line}; confirmed brief: {confirmed}; {room_fact}."
        # The owner's brief settings, as last saved in the chat or the Brief panel (split-project-panel).
        brief_text = brief_line(state.get("brief") or (bound["brief"] if bound else None) or {})
        if brief_text:
            facts += f" Brief: {brief_text}."
        if apartments:
            listed = ", ".join(
                f"{a['name']} ({a['rooms']} room(s), "
                + (f"shell v{a['shell_version']}" if a["shell_version"] else "no shell yet")
                + ")"
                for a in apartments
            )
            facts += f" Apartments: {listed}."
        image_attached, design_attached = _attached(engine, messages)
        design_conflict = None
        if design_attached and package_id is None:
            attached = _attached_design(engine, settings, messages)
            matched = design_match(attached[0], attached[1], all_pieces) if attached else None
            if matched is not None:
                with Session(engine) as session:
                    has_conversation = house_file.thread_id_for_piece(session, matched["package_id"]) is not None
                design_conflict = {
                    "package_id": matched["package_id"],
                    "name": matched["name"],
                    "file": attached[0],
                    "has_conversation": has_conversation,
                }
        pending_design = None
        if thread_id is not None and not room_confirmed and package_id is None:
            with Session(engine) as session:
                unbuilt = not house_file.builds_of(session, thread_id)
            pending_design = _pending_design(engine, messages) if unbuilt else None
        bound_room = piece_rooms.get(package_id) if package_id else None
        # One piece per conversation: never list other builds, even from legacy rows.
        other_builds: list[dict[str, Any]] = []
        described_rooms = [house_file.describe_room(r) for r in scope_rooms]
        with Session(engine) as session:
            if scope_apartment_name is not None:
                apartment_dims = composition_docs.dimensions_of_scope(
                    session, settings.render_root, scope="apartment", name=scope_apartment_name
                )
                if apartment_dims is not None and apartments:
                    apartments = [{**apartments[0], "dimensions": apartment_dims}]
            else:
                for index, room in enumerate(described_rooms):
                    room_dims = composition_docs.dimensions_of_scope(
                        session, settings.render_root, scope="room", name=room["name"]
                    )
                    if room_dims is not None:
                        described_rooms[index] = {**room, "dimensions": room_dims}
        return {
            "house_note": house_note(
                described_rooms,
                preferences,
                [with_room(bound)] if bound else [],
                requests,
                apartments,
                open_review,
                other_builds=other_builds,
                no_room=not room_confirmed,
                open_verdicts=open_verdicts,
            )
            or "",
            "piece_note": piece_text,
            "feedback_note": render_feedback_note(recent_feedback),
            "facts": facts,
            "package_id": package_id,
            "piece_ready": piece_ready,
            "shell_ready": shell_ready,
            "composition_ready": composition_ready,
            "compose_ready": compose_ready,
            "composition_note": composition_note(composed, ready_models),
            "review_ready": review_ready,
            "detail_ready": detail_ready,
            "image_attached": image_attached,
            "design_attached": design_attached,
            "design_matches_piece": design_conflict,
            "pending_design": pending_design,
            "handoff_design": None,
            "piece_named": bool(matches) and active is None and piece_taken is None,
            "room_confirmed": room_confirmed,
            "room_named": room_is_named,
            "room_asked": room_question_asked(messages),
            "room_answer": answer,
            "room_declined": room_declined,
            # A conversation that declined a room places no piece (optional-room-question).
            "build_room_ok": package_id is None
            or room_declined
            or (bound_room is not None and bound_room in scope_room_names),
            "placement_ready": placement_ready,
            "views_in_room": False,
            "placement_saved": False,
            "ambiguous_pieces": ambiguous,
            "piece_has_conversation": piece_taken,
            "round_count": 0,
            "specialist": "",
            "bound_tools": tools_this_turn,
            "engineering_turn": engineering_chat.engineering_intent(_last_human_text(state)),
            "open_question_turn": False,
            "engineering_evidence_ids": [],
            "engineering_metadata_ids": [],
            "engineering_report_ids": [],
            "engineering_assessment_ids": [],
        }

    # --- the Foreman ----------------------------------------------------------

    def recorder(slot: str, config: RunnableConfig, *, estimated_tokens: int | None = None) -> UsageRecorder:
        configurable = config.get("configurable", {})
        return UsageRecorder(
            engine,
            model_id=model_ids(slot),
            owner_user_id=UUID(str(configurable["owner_id"])),
            trace_id=configurable.get("trace_id"),
            estimated_tokens=estimated_tokens,
            # The conversation the call is made for (studio-chat-polish).
            thread_id=UUID(str(configurable["chat_thread"])) if configurable.get("chat_thread") else None,
            private_tracing=deps.tracing if configurable.get("engineering_trace") else None,
        )

    def prompt_for(
        slot: str, system: str, state: ChatState, tools: list, config: RunnableConfig | None = None
    ) -> tuple[list, int]:
        slug = model_ids(slot)
        restrictions = budget_store.for_model(slug)
        model = model_provider(slot)
        max_tokens = getattr(model, "max_tokens", None)
        budget = RequestBudget.for_model(
            slug,
            context_budget_tokens=restrictions.context_budget_tokens,
            max_output_tokens=max_tokens if isinstance(max_tokens, int) else None,
        )
        engineering = bool(state.get("engineering_turn"))
        engineering_enabled = any("search_engineering_knowledge" in names for names in (state.get("bound_tools") or {}).values())
        with Session(engine) as session:
            safe_history = engineering_chat.request_history(session, list(state.get("messages", [])), engineering=engineering, enabled=engineering_enabled, routing=slot == "foreman", render_root=settings.render_root)
        history = with_attachments(
            safe_history,
            capable=slot in IMAGE_SLOTS,
            engine=engine,
            settings=settings,
            engineering=engineering or slot == "foreman",
        )
        used = tokens_today(engine, slug, settings.budget_timezone)
        # Dropped exchanges are summarised for the thread; the summary call itself is a
        # side call with no summarizer, so it cannot recurse.
        raw_thread = (config or {}).get("configurable", {}).get("chat_thread")
        memory = read_memory_settings(engine)
        summarize = None
        through = None
        if raw_thread and not engineering and slot != "foreman":

            def call(summary_system: str, messages: list, max_output: int) -> str:
                return side_call("chat.summary", summary_system, messages, max_output, config or {})

            summarize = summaries.summarizer(
                engine, UUID(str(raw_thread)), call, state.get("package_id"), memory
            )
            through = summaries.covered_through(engine, UUID(str(raw_thread)), state.get("package_id"))
        elif raw_thread and not engineering:
            # Routing reads the stored note but never writes one (conversation-recent-inputs).
            summarize = summaries.stored_note(engine, UUID(str(raw_thread)), state.get("package_id"))
            through = summaries.covered_through(engine, UUID(str(raw_thread)), state.get("package_id"))
        fitted, _counted = prepare(
            budget,
            system,
            history,
            tools=tools or None,
            used_today=used,
            daily_ceiling=restrictions.daily_token_ceiling,
            summarize=summarize,
            trigger_percent=memory.trigger_percent,
            keep_turns=memory.keep_turns,
            covered_through=through,
            recent_inputs=0 if engineering else memory.recent_inputs,
        )
        # Recheck after fitting/summary work, immediately before dispatch. Refit
        # whole packets if current rights or reviewed properties changed.
        with Session(engine) as session:
            final_copy = engineering_chat.request_history(session, fitted, engineering=engineering, enabled=engineering_enabled, routing=slot == "foreman", render_root=settings.render_root)
        return prepare(budget, system, final_copy[1:], tools=tools or None, used_today=used, daily_ceiling=restrictions.daily_token_ceiling)

    def side_call(
        operation: str, system: str, messages: list[AnyMessage], max_output: int, config: RunnableConfig
    ) -> str:
        """One tool-less call on the Foreman slot (a title, a summary), counted, capped and
        metered like any other. Raises `BudgetRefused` or `GatewayError`; the caller falls back."""
        slot = loaded["foreman"].slot
        slug = model_ids(slot)
        restrictions = budget_store.for_model(slug)
        budget = RequestBudget.for_model(
            slug, context_budget_tokens=restrictions.context_budget_tokens, max_output_tokens=max_output
        )
        raw_thread = config.get("configurable", {}).get("chat_thread")
        if raw_thread:
            with Session(engine) as session:
                if engineering_chat.has_engineering_history(session, UUID(str(raw_thread))):
                    # Summaries have no reliable per-sentence source mapping. Keep
                    # stored notes locally, but do not re-export them as evidence.
                    if operation == "chat.summary":
                        return "Engineering evidence is stored by source ID and must be fetched again; capacity is NOT VERIFIED."
                    messages = engineering_chat.request_history(session, messages, engineering=True, enabled=False, render_root=settings.render_root)
        prompt, counted = prepare(
            budget,
            system,
            messages,
            used_today=tokens_today(engine, slug, settings.budget_timezone),
            daily_ceiling=restrictions.daily_token_ceiling,
        )
        with gateway_errors(operation=operation):
            reply = model_provider(slot).invoke(
                prompt,
                config=with_callbacks(config, recorder(slot, config, estimated_tokens=counted)),
                max_tokens=max_output,
                # A note or title is short text: reasoning would spend the whole cap and leave it empty.
                extra_body={"reasoning": {"enabled": False}},
            )
        return _text_of(getattr(reply, "content", ""))

    def foreman(
        state: ChatState, config: RunnableConfig
    ) -> Command[
        Literal["intake", "designer", "builder", "lighting", "reviewer", "researcher", "__end__"]
    ]:
        # A design file named like an existing piece is answered by code, before any model
        # call or specialist, and nothing is imported (delete-piece).
        conflict = state.get("design_matches_piece")
        if conflict:
            update_way = (DESIGN_UPDATE_IN_CONVERSATION if conflict["has_conversation"] else DESIGN_UPDATE_HERE).format(
                name=conflict["name"], package_id=conflict["package_id"]
            )
            fixed = DESIGN_MATCHES_PIECE.format(
                file=conflict["file"], name=conflict["name"], package_id=conflict["package_id"], update=update_way
            )
            return Command(update={"messages": [AIMessage(fixed)], "specialist": ""}, goto=END)
        instruction = loaded["foreman"]
        system = compose_agent_prompt(
            instruction.text, state.get("facts", ""), state.get("house_note", ""), state.get("composition_note", "")
        )
        try:
            prompt, counted = prompt_for(instruction.slot, system, state, [], config)
        except BudgetRefused as error:
            return Command(
                update={"messages": [AIMessage(refusal_message("foreman", error))], "specialist": ""},
                goto=END,
            )
        with gateway_errors(operation="chat.foreman"):
            decision = (
                model_provider(instruction.slot)
                .with_structured_output(Decision)
                .invoke(
                    prompt,
                    config=with_callbacks(
                        config, recorder(instruction.slot, config, estimated_tokens=counted)
                    ),
                )
            )
        chosen = getattr(decision, "specialist", None)
        if chosen not in SPECIALISTS:
            chosen = "intake"
        reason = getattr(decision, "reason", "") or ""
        # A plain question about the expected height is answered by code, whatever the model flagged.
        if engineering_chat.height_question(_last_human_text(state)):
            return Command(
                update={"messages": [AIMessage(engineering_chat.HEIGHT_REPLY)], "specialist": ""}, goto=END
            )
        # A placement in the room is not engineering on the model's flag alone (short-engineering-reply).
        flagged = bool(getattr(decision, "engineering_question", False)) and not engineering_chat.placement_request(
            _last_human_text(state)
        )
        engineering = bool(state.get("engineering_turn")) or flagged
        if engineering:
            changing = bool(state.get("package_id")) and (engineering_chat.revision_intent(_last_human_text(state)) or bool(getattr(decision, "requests_revision", False)))
            chosen = "designer" if changing else "researcher"

        # A question about how to use the app is Intake's, with or without a room, before the
        # room question; a turn with a plan, photo or design file is never one (help-center).
        if (
            chosen != "researcher"
            and not engineering
            and getattr(decision, "asks_help", False) is True
            and not (state.get("image_attached") or state.get("design_attached"))
        ):
            return Command(update={"specialist": "intake", "reason": reason, "engineering_turn": False}, goto="intake")

        # An open question before any room is settled is answered by the Designer, before the
        # room offer; a turn with a plan, photo or design file is never one (open-question-first-turn).
        if (
            chosen != "researcher"
            and not engineering
            and getattr(decision, "open_question", False) is True
            and not (state.get("image_attached") or state.get("design_attached"))
            and not state.get("room_confirmed")
            and not state.get("room_declined")
        ):
            return Command(
                update={
                    "specialist": "designer",
                    "reason": reason,
                    "engineering_turn": False,
                    "open_question_turn": True,
                },
                goto="designer",
            )

        # Application rules bound the model's choice (design-agents spec). A price or product
        # question is the Researcher's whatever else holds; then the two fixed questions.
        if chosen != "researcher":
            fixed = None
            if state.get("piece_has_conversation"):
                fixed = PIECE_HAS_CONVERSATION.format(piece=state["piece_has_conversation"])
            elif state.get("ambiguous_pieces"):
                fixed = WHICH_PIECE.format(names=", ".join(state["ambiguous_pieces"]))
            elif (
                not state.get("room_confirmed")
                and not state.get("room_declined")
                and not (state.get("image_attached") or state.get("room_named") or state.get("room_asked"))
            ):
                # The room is offered first; "Which room is this for?" follows only a yes.
                fixed = ROOM_QUESTION if state.get("room_answer") == "yes" else ROOM_OFFER
            if fixed is not None:
                return Command(update={"messages": [AIMessage(fixed)], "specialist": ""}, goto=END)
        # On the turn the owner declines a room, a design file sent before it is the Designer's to
        # import, as on the turn that confirms a room (optional-room-question).
        pending = state.get("pending_design")
        if state.get("room_answer") == "no" and pending and not state.get("package_id"):
            return Command(
                update={
                    "specialist": "designer",
                    "reason": reason,
                    "engineering_turn": False,
                    "handoff_design": pending,
                    "pending_design": None,
                },
                goto="designer",
            )
        # A piece with a version, or an apartment with a shell, gives the Builder something to work on.
        buildable = state.get("piece_ready") or state.get("shell_ready") or state.get("composition_ready")
        if not buildable and chosen == "builder":
            chosen = "designer" if state.get("brief") else "intake"
        if chosen == "reviewer" and not state.get("review_ready"):
            chosen = "builder" if buildable else ("designer" if state.get("brief") else "intake")
        if chosen == "lighting" and not state.get("detail_ready"):
            chosen = "builder" if buildable else ("designer" if state.get("brief") else "intake")
        # A room the conversation has confirmed may be composed whether or not the message names
        # it, when the model reads the request as composing a room (app-check-2026-10-09).
        room_wish = bool(getattr(decision, "composes_room", False)) and bool(state.get("room_confirmed"))
        if room_wish and chosen == "intake":
            chosen = "designer"
        composing = chosen == "designer" and (state.get("compose_ready") or room_wish)
        # A piece the owner or the last reply names can be revised, rebuilt or given an imported
        # version by the Designer, even here (piece-versions-and-chat-delete).
        naming = chosen == "designer" and state.get("piece_named")
        if (
            not buildable
            and not state.get("brief")
            and chosen not in ("reviewer", "researcher")
            and not composing
            and not naming
        ):
            chosen = "intake"
        # Seeing the built piece in the confirmed room: the Builder renders it where it was placed,
        # and without a place the Designer asks for one first (view-piece-in-room). A conversation
        # that declined a room is asked which room.
        views = bool(getattr(decision, "views_in_room", False)) and bool(state.get("detail_ready")) and not engineering
        if views and not state.get("room_confirmed"):
            return Command(update={"messages": [AIMessage(ROOM_QUESTION)], "specialist": ""}, goto=END)
        if views:
            chosen = "builder" if state.get("placement_ready") else "designer"
        # Only Intake reads plans and photos, so an image turn the model gave the Designer goes to Intake.
        if chosen == "designer" and state.get("image_attached"):
            chosen = "intake"
        # With a room confirmed, an attached design file is the Designer's to import,
        # whatever else the thread holds (design-import).
        if state.get("design_attached") and (state.get("room_confirmed") or state.get("room_declined")):
            chosen = "designer"
        # A build with no room, or in a room outside the conversation's, is placed first.
        if chosen in ("designer", "builder", "reviewer", "lighting") and not state.get("build_room_ok", True):
            chosen = "intake"
        return Command(
            update={
                "specialist": chosen,
                "reason": reason,
                "engineering_turn": engineering,
                "views_in_room": views and chosen in ("designer", "builder"),
            },
            goto=chosen,
        )

    # --- a specialist ------------------------------------------------------------

    def specialist_graph(name: str):
        instruction = loaded[name]

        def bound_for(state: ChatState) -> dict[str, AgentTool]:
            names = (state.get("bound_tools") or {}).get(name)
            if names is None:
                names = list(instruction.tools)
            # An open question changes nothing: the Designer may only search the guidelines.
            if state.get("open_question_turn"):
                names = [tool for tool in names if tool == "search_guidelines"]
            return {tool: tools_by_name[tool] for tool in names if tool in tools_by_name and (tool not in {"search_engineering_knowledge", "record_assessment_inputs", "calculate_engineering", "get_engineering_report"} or state.get("engineering_turn")) and (not state.get("engineering_turn") or tool not in {"search_catalog_knowledge", "check_live_listing", "compare_products"})}

        def agent(state: ChatState, config: RunnableConfig) -> Command[Literal["tools", "__end__"]]:
            round_count = state.get("round_count", 0)
            notes = [state.get("facts", "")]
            if name in ("intake", "designer"):
                notes.append(state.get("house_note", ""))
            if name == "designer":
                notes.append(state.get("piece_note", ""))
                notes.append(DESIGNER_SIDE_FOLDS_NOTE)
                notes.append(DESIGNER_SHELF_DEPTHS_NOTE)
            if name in ("intake", "designer", "builder"):
                notes.append(state.get("composition_note", ""))
            if name in ("designer", "lighting"):
                notes.append(state.get("feedback_note", ""))
            handoff = state.get("handoff_design") if name == "designer" else None
            if handoff:
                when = (
                    "and chose not to view the piece in a room"
                    if state.get("room_declined") and not state.get("room_confirmed")
                    else "before the room was confirmed; it is now confirmed"
                )
                notes.append(
                    f"(The owner attached the design file '{neutralise(handoff['name'])}' as upload "
                    f"{handoff['upload_id']} {when}. Import it with import_design.)"
                )
            if state.get("views_in_room") and name == "designer":
                notes.append(
                    "(The owner wants to see the piece in this conversation's room and it has no place "
                    "there yet. Call ask_placement now; do not explain what is missing.)"
                )
            if state.get("views_in_room") and name == "builder":
                notes.append(
                    "(The owner wants to see the piece in this conversation's room, and its place there is "
                    'saved. Start a draft still now: call render_turntable with the piece\'s package_id, kind "still", '
                    'tier "draft" and in_room true.)'
                )
            if state.get("open_question_turn") and name == "designer":
                notes.append(OPEN_QUESTION_NOTE)
            # The templates only for a new piece: a revision sees only the active build's figures.
            elif name == "designer" and not state.get("package_id"):
                notes.append(designer_note)
            notes.append(FORMATTING_NOTE)
            if state.get("engineering_turn"):
                notes.append(engineering_chat.ANSWER_NOTE)
            capped = round_count >= MAX_TOOL_ROUNDS
            if capped:
                notes.append(TOOL_ROUND_CAP_NOTE)
            bound_tools = bound_for(state)
            selected = [] if capped else [tool.structured() for tool in bound_tools.values()]

            def answer(extra: list[str]) -> Any:
                system = compose_agent_prompt(instruction.text, *notes, *extra)
                prompt, counted = prompt_for(instruction.slot, system, state, selected, config)
                with gateway_errors(operation=f"chat.{name}"):
                    return (
                        model_provider(instruction.slot)
                        .bind_tools(selected)
                        .invoke(
                            prompt,
                            config=with_callbacks(
                                config, recorder(instruction.slot, config, estimated_tokens=counted)
                            ),
                        )
                    )

            try:
                reply = answer([])
                # An empty answer is asked for once more, then replaced: the owner always
                # sees an answer (piece-versions-and-chat-delete).
                if is_empty_answer(reply):
                    reply = answer([EMPTY_ANSWER_NOTE])
                    if is_empty_answer(reply):
                        role = SPECIALIST_LABELS.get(name, name)
                        reply = AIMessage(EMPTY_REPLY.format(role=role[:1].upper() + role[1:]))
            except BudgetRefused as error:
                return Command(
                    update={"messages": [AIMessage(refusal_message(name, error))]},
                    goto=END,
                )
            goto: Literal["tools", "__end__"] = "tools" if getattr(reply, "tool_calls", None) else END
            if state.get("engineering_turn"):
                if goto == END:
                    with Session(engine) as session:
                        rendered = engineering_chat.render_answer(_text_of(reply.content), session, state.get("engineering_evidence_ids", []), _last_human_text(state), enabled="search_engineering_knowledge" in bound_tools, metadata_ids=state.get("engineering_metadata_ids", []), report_ids=state.get("engineering_report_ids", []), calculators_enabled="calculate_engineering" in bound_tools, render_root=settings.render_root)
                    reply = reply.model_copy(update={"content": rendered})
                else:
                    # Early prose beside tool calls is not a validated claim.
                    reply = reply.model_copy(update={"content": ""})
                reply.additional_kwargs["engineering"] = True
                reply.additional_kwargs["engineering_evidence_ids"] = list(state.get("engineering_evidence_ids", []))
                reply.additional_kwargs["engineering_report_ids"] = list(state.get("engineering_report_ids", []))
            return Command(
                update={"messages": [reply], "round_count": round_count + 1}, goto=goto
            )

        def tools_node(state: ChatState, config: RunnableConfig) -> Command[Literal["agent"]]:
            configurable = config.get("configurable", {})
            ctx = ToolContext(
                deps=deps,
                owner_id=UUID(str(configurable["owner_id"])),
                thread_id=UUID(str(configurable["chat_thread"])) if configurable.get("chat_thread") else None,
                package_id=state.get("package_id"),
                brief=dict(state.get("brief") or {}),
                last_message=_last_human_text(state),
                history=tuple(state.get("messages", [])),
                trace_id=configurable.get("trace_id"),
                slot=instruction.slot,
                model=model_ids(instruction.slot),
                engineering_turn=bool(state.get("engineering_turn")),
                engineering_enabled="search_engineering_knowledge" in (state.get("bound_tools") or {}).get(name, []),
                calculators_enabled="calculate_engineering" in (state.get("bound_tools") or {}).get(name, []),
            )
            calls = _last_ai_tool_calls(state)
            bound_tools = bound_for(state)
            # Each tool is reported as it starts, by its plugin's plain name only; a
            # gated tool starts with its preview, so a pause still names it.
            writer = get_stream_writer()

            # The round's first gated call decides whether the turn pauses. Its
            # preview is code, so an invalid call is refused with no pause; the
            # interrupt comes before any tool runs, so a resume replays only
            # this check and then runs the round for the first time.
            first_gated = next(
                (c for c in calls if c.get("name") in bound_tools and bound_tools[c["name"]].gated),
                None,
            )
            outcome: Confirmation | Questions | str | None = None
            answer: Any = None
            if first_gated is not None:
                tool = bound_tools[first_gated["name"]]
                writer({"tool": plugin_name(tool.name)})
                outcome = tool.preview(first_gated.get("args") or {}, ctx)  # type: ignore[misc]
                if isinstance(outcome, Confirmation):
                    answer = interrupt(_confirmation_payload(outcome, tool.name))
                elif isinstance(outcome, Questions):
                    answer = interrupt(_questions_payload(outcome, tool.name))

            approved = isinstance(answer, dict) and answer.get("answer") == "yes"
            reason = answer.get("reason") if isinstance(answer, dict) else None
            reason = reason.strip() if isinstance(reason, str) and reason.strip() else None

            messages: list[ToolMessage] = []
            update: dict[str, Any] = {}
            for call in calls:
                call_id = call.get("id") or ""
                tool = bound_tools.get(call.get("name") or "")
                if tool is None:
                    messages.append(
                        ToolMessage(tool_refusal(call.get("name") or "", name, owners), tool_call_id=call_id)
                    )
                    continue
                args = call.get("args") or {}
                if tool.gated and call is not first_gated:
                    messages.append(ToolMessage(ONE_AT_A_TIME_NOTE, tool_call_id=call_id))
                    continue
                if call is first_gated:
                    if isinstance(outcome, str):
                        messages.append(ToolMessage(outcome, tool_call_id=call_id))
                        continue
                    if isinstance(outcome, Confirmation) and not approved:
                        text = DECLINED.get(outcome.subject, "Not done.")
                        if reason:
                            text += f" Reason: {reason}"
                        messages.append(ToolMessage(text, tool_call_id=call_id))
                        continue
                run_ctx = replace(ctx, approved=True) if isinstance(outcome, Confirmation) else ctx
                if call is first_gated and isinstance(outcome, Questions):
                    run_ctx = replace(ctx, answer=answer if isinstance(answer, dict) else {})
                if call is not first_gated:
                    writer({"tool": plugin_name(tool.name)})
                try:
                    result = tool.run(args, run_ctx)
                except Exception as error:  # noqa: BLE001 - a tool must not end the turn
                    logger.warning(
                        "tool failed",
                        extra={"context": {"tool": tool.name, "error_type": type(error).__name__}},
                    )
                    messages.append(
                        ToolMessage(f"The {tool.name} tool failed and returned no data.", tool_call_id=call_id)
                    )
                    continue
                if isinstance(result, ToolOutput):
                    update.update(result.update)
                    ctx = replace(
                        ctx,
                        brief=update.get("brief", ctx.brief),
                        package_id=update.get("package_id", ctx.package_id),
                    )
                    messages.append(ToolMessage(result.text, tool_call_id=call_id))
                    if "engineering_evidence_ids" in result.update:
                        messages[-1].additional_kwargs.update({"engineering_source": True, "engineering_evidence_ids": result.update["engineering_evidence_ids"], "engineering_metadata_ids": result.update.get("engineering_metadata_ids", [])})
                    if "engineering_report_ids" in result.update:
                        messages[-1].additional_kwargs["engineering_report_ids"] = list(result.update["engineering_report_ids"])
                else:
                    messages.append(ToolMessage(result, tool_call_id=call_id))
            # An answered confirmation stays in the history as one line (homeowner-chat); the
            # model never sees these kwargs, only the tool result's text.
            if isinstance(outcome, Confirmation) and first_gated is not None:
                answered = {
                    "subject": outcome.subject,
                    "summary": outcome.summary,
                    "answer": "yes" if approved else "no",
                    "reason": reason,
                }
                for message in messages:
                    if message.tool_call_id == (first_gated.get("id") or ""):
                        message.additional_kwargs["confirmation"] = answered
            if isinstance(outcome, Questions) and first_gated is not None:
                for message in messages:
                    if message.tool_call_id == (first_gated.get("id") or ""):
                        message.additional_kwargs["answers"] = _answered_rows(outcome, answer)
            if state.get("engineering_turn"):
                for message in messages:
                    message.additional_kwargs["engineering"] = True
                update["engineering_evidence_ids"] = list(dict.fromkeys([*state.get("engineering_evidence_ids", []), *update.get("engineering_evidence_ids", [])]))
                update["engineering_metadata_ids"] = list(dict.fromkeys([*state.get("engineering_metadata_ids", []), *update.get("engineering_metadata_ids", [])]))
                update["engineering_report_ids"] = list(dict.fromkeys([*state.get("engineering_report_ids", []), *update.get("engineering_report_ids", [])]))
            update.pop("engineering_turn", None)
            return Command(update={"messages": messages, **update}, goto="agent")

        builder = StateGraph(ChatState)
        builder.add_node("agent", agent)
        builder.add_node("tools", tools_node)
        builder.add_edge(START, "agent")
        builder.add_edge("tools", "agent")
        return builder.compile()

    # --- the whole graph -----------------------------------------------------------

    def after_intake(state: ChatState, config: RunnableConfig) -> Command[Literal["designer", "__end__"]]:
        """Hand a design file attached before the room was confirmed to the Designer, on the
        Intake turn that confirmed the room, while the conversation has no piece
        (pending-design-import). Decided here, never by a model."""
        pending = state.get("pending_design")
        raw_thread = config.get("configurable", {}).get("chat_thread")
        if not pending or not raw_thread:
            return Command(goto=END)
        thread_id = UUID(str(raw_thread))
        with Session(engine) as session:
            thread = house_file.get_thread(session, thread_id)
            room, apartment = house_file.thread_scope(session, thread_id)
            unbuilt = thread is not None and not thread.package_id and not house_file.builds_of(session, thread_id)
            scope = f"room {room.name}" if room is not None else (
                f"apartment {apartment.name}" if apartment is not None else None
            )
        if scope is None or not unbuilt:
            return Command(goto=END)
        return Command(
            update={
                "specialist": "designer",
                "round_count": 0,
                "handoff_design": pending,
                "pending_design": None,
                # The slice was read before the room was confirmed; only its room line changes.
                "room_confirmed": True,
                "facts": state.get("facts", "").replace("no room confirmed yet", scope),
                "house_note": state.get("house_note", "").replace(
                    "No room is confirmed in this conversation yet.", f"This conversation now works in the {scope}."
                ),
            },
            goto="designer",
        )

    def after_designer(state: ChatState, config: RunnableConfig) -> Command[Literal["builder", "__end__"]]:
        """When the owner asked to see the piece in the room and `ask_placement` saved its place
        this turn, the same turn goes on to the Builder for a draft still in the room
        (view-piece-in-room). Decided here, never by a model."""
        if not (state.get("views_in_room") and state.get("placement_saved")):
            return Command(goto=END)
        return Command(
            update={"specialist": "builder", "round_count": 0, "placement_saved": False, "placement_ready": True},
            goto="builder",
        )

    graph = StateGraph(ChatState)
    graph.add_node("load_house", load_house)
    graph.add_node("foreman", foreman)
    for name in SPECIALISTS:
        graph.add_node(name, specialist_graph(name))
        if name not in ("intake", "designer"):
            graph.add_edge(name, END)
    graph.add_node("after_intake", after_intake)
    graph.add_edge("intake", "after_intake")
    graph.add_node("after_designer", after_designer)
    graph.add_edge("designer", "after_designer")
    graph.add_edge(START, "load_house")
    graph.add_edge("load_house", "foreman")
    compiled = graph.compile(checkpointer=checkpointer)
    # Calls outside a turn's graph run (the conversation's title) share its budgets and metering.
    compiled.side_call = side_call
    return compiled


def last_reply(state: dict[str, Any]) -> str:
    """The text of the turn's last assistant message."""
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""
