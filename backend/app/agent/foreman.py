"""The Foreman graph: one supervisor, three specialist sub-graphs.

`load_house` reads the house file and the thread, `foreman` chooses one
specialist (a structured decision from the `foreman` slot's model, then bounded
by code rules), and the chosen specialist — Intake, Designer or Builder — runs
its own bounded `agent ⇄ tools` loop. One compiled graph on one checkpointer
thread means a paused confirmation resumes inside the specialist that raised it.

Gated tools pause with `interrupt()` before they run: the first gated call in a
round is previewed by code, and only the owner's `yes` runs it. The model never
sees or changes a token budget, a model name or a path (CLAUDE.md §1, §4).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any, Final, Literal, TypedDict
from uuid import UUID

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.instructions import AgentInstruction, load_instructions
from app.agent.models.openrouter_client import gateway_errors
from app.agent.prompts import TOOL_ROUND_CAP_NOTE, compose_agent_prompt, house_note
from app.agent.tools import all_tools
from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolDeps,
    ToolOutput,
)
from app.config import Settings
from app.observability.usage import UsageRecorder

logger = logging.getLogger("app")

MAX_TOOL_ROUNDS: Final = 6
HISTORY_WINDOW: Final = 40
SPECIALISTS: Final = ("intake", "designer", "builder")

TEMPLATES_DIR: Final = Path(__file__).resolve().parents[2] / "fixtures" / "packages" / "templates"

ONE_AT_A_TIME_NOTE: Final = (
    "Not run: only one confirmable action can be handled at a time. "
    "Propose any further action in a later step."
)
NOT_AVAILABLE_NOTE: Final = "this tool is not available to you"
DECLINED: Final[dict[str, str]] = {
    "brief": "The brief was not saved.",
    "create_piece": "The piece was not created.",
    "revise": "No revision was created.",
    "final_render": "The final render was not started.",
}

ModelProvider = Callable[[str], Any]
ModelIds = Callable[[str], str]


class ChatState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    specialist: str
    reason: str
    house_note: str
    facts: str
    round_count: int
    package_id: str | None
    piece_ready: bool
    brief: dict[str, Any]


class Decision(BaseModel):
    """The Foreman's choice for this turn."""

    specialist: Literal["intake", "designer", "builder"]
    reason: str = Field(description="one sentence")


def window(messages: list[AnyMessage], size: int = HISTORY_WINDOW) -> list[AnyMessage]:
    """The last `size` messages, never starting on a tool result whose call was cut."""
    if len(messages) <= size:
        return list(messages)
    kept = list(messages[-size:])
    while kept and isinstance(kept[0], ToolMessage):
        kept.pop(0)
    return kept


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


def _last_human_text(state: ChatState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _designer_note() -> str:
    templates = []
    for name in ("fold-down-desk", "blank-build"):
        document = json.loads((TEMPLATES_DIR / f"{name}.json").read_text(encoding="utf-8"))
        templates.append(f"Template {name}:\n{json.dumps(document, separators=(',', ':'))}")
    return (
        "A custom_build document is positioned modules (boxes, in whole millimetres) with "
        "shelves and fronts (door, drawer, flap), drawing materials from named slots. "
        "Start from one of these templates and change only what the brief supports.\n\n"
        + "\n\n".join(templates)
    )


def _confirmation_payload(confirmation: Confirmation, tool: str) -> dict[str, Any]:
    return {
        "tool": tool,
        "subject": confirmation.subject,
        "summary": confirmation.summary,
        "proposal": confirmation.proposal,
    }


def build_graph(
    engine: Engine,
    settings: Settings,
    *,
    model_provider: ModelProvider,
    model_ids: ModelIds,
    checkpointer: Any,
    deps: ToolDeps,
    instructions: dict[str, AgentInstruction] | None = None,
):
    """Compile the Foreman graph on `checkpointer`."""
    loaded = instructions or load_instructions()
    tools_by_name = all_tools()
    designer_note = _designer_note()

    # --- context ------------------------------------------------------------

    def load_house(state: ChatState, config: RunnableConfig) -> dict[str, Any]:
        configurable = config.get("configurable", {})
        with Session(engine) as session:
            rooms = [house_file.describe_room(room) for room in house_file.rooms(session)]
            preferences = house_file.preferences(session)
            pieces = house_file.pieces(session, settings.render_root)
            requests = [
                {"field": r.field, "request": r.request}
                for r in house_file.open_extension_requests(session)
            ]
            thread = None
            raw_thread = configurable.get("chat_thread")
            if raw_thread:
                thread = house_file.get_thread(session, UUID(str(raw_thread)))
        package_id = thread.package_id if thread and thread.package_id else state.get("package_id")
        bound = next((p for p in pieces if p["package_id"] == package_id), None)
        piece_ready = bool(bound and bound["latest_version"])

        if bound:
            latest = f"version {bound['latest_version']}" if bound["latest_version"] else "no version"
            status = f", {bound['status']}" if bound["status"] else ""
            piece_line = f"{package_id} ({latest}{status})"
        else:
            piece_line = "none"
        confirmed = "yes" if state.get("brief") else "no"
        return {
            "house_note": house_note(rooms, preferences, pieces, requests) or "",
            "facts": f"This conversation: piece {piece_line}; confirmed brief: {confirmed}.",
            "package_id": package_id,
            "piece_ready": piece_ready,
            "round_count": 0,
            "specialist": "",
        }

    # --- the Foreman ----------------------------------------------------------

    def recorder(slot: str, config: RunnableConfig) -> UsageRecorder:
        configurable = config.get("configurable", {})
        return UsageRecorder(
            engine,
            model_id=model_ids(slot),
            owner_user_id=UUID(str(configurable["owner_id"])),
            trace_id=configurable.get("trace_id"),
        )

    def foreman(
        state: ChatState, config: RunnableConfig
    ) -> Command[Literal["intake", "designer", "builder"]]:
        instruction = loaded["foreman"]
        system = compose_agent_prompt(instruction.text, state.get("facts", ""), state.get("house_note", ""))
        prompt = [SystemMessage(system), *window(state.get("messages", []), 12)]
        with gateway_errors(operation="chat.foreman"):
            decision = (
                model_provider(instruction.slot)
                .with_structured_output(Decision)
                .invoke(prompt, config=with_callbacks(config, recorder(instruction.slot, config)))
            )
        chosen = getattr(decision, "specialist", None)
        if chosen not in SPECIALISTS:
            chosen = "intake"
        reason = getattr(decision, "reason", "") or ""

        # Application rules bound the model's choice (design-agents spec).
        if not state.get("piece_ready") and chosen == "builder":
            chosen = "designer" if state.get("brief") else "intake"
        if not state.get("piece_ready") and not state.get("brief"):
            chosen = "intake"
        return Command(update={"specialist": chosen, "reason": reason}, goto=chosen)

    # --- a specialist ------------------------------------------------------------

    def specialist_graph(name: str):
        instruction = loaded[name]
        bound_tools: dict[str, AgentTool] = {t: tools_by_name[t] for t in instruction.tools}

        def agent(state: ChatState, config: RunnableConfig) -> Command[Literal["tools", "__end__"]]:
            round_count = state.get("round_count", 0)
            notes = [state.get("facts", "")]
            if name in ("intake", "designer"):
                notes.append(state.get("house_note", ""))
            if name == "designer":
                notes.append(designer_note)
            capped = round_count >= MAX_TOOL_ROUNDS
            if capped:
                notes.append(TOOL_ROUND_CAP_NOTE)
            system = compose_agent_prompt(instruction.text, *notes)
            prompt = [SystemMessage(system), *window(state.get("messages", []))]
            selected = [] if capped else [tool.structured() for tool in bound_tools.values()]
            with gateway_errors(operation=f"chat.{name}"):
                reply = (
                    model_provider(instruction.slot)
                    .bind_tools(selected)
                    .invoke(prompt, config=with_callbacks(config, recorder(instruction.slot, config)))
                )
            goto: Literal["tools", "__end__"] = "tools" if getattr(reply, "tool_calls", None) else END
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
            )
            calls = _last_ai_tool_calls(state)

            # The round's first gated call decides whether the turn pauses. Its
            # preview is code, so an invalid call is refused with no pause; the
            # interrupt comes before any tool runs, so a resume replays only
            # this check and then runs the round for the first time.
            first_gated = next(
                (c for c in calls if c.get("name") in bound_tools and bound_tools[c["name"]].gated),
                None,
            )
            outcome: Confirmation | str | None = None
            answer: Any = None
            if first_gated is not None:
                tool = bound_tools[first_gated["name"]]
                outcome = tool.preview(first_gated.get("args") or {}, ctx)  # type: ignore[misc]
                if isinstance(outcome, Confirmation):
                    answer = interrupt(_confirmation_payload(outcome, tool.name))

            approved = isinstance(answer, dict) and answer.get("answer") == "yes"
            reason = answer.get("reason") if isinstance(answer, dict) else None
            reason = reason.strip() if isinstance(reason, str) and reason.strip() else None

            messages: list[ToolMessage] = []
            update: dict[str, Any] = {}
            for call in calls:
                call_id = call.get("id") or ""
                tool = bound_tools.get(call.get("name") or "")
                if tool is None:
                    messages.append(ToolMessage(NOT_AVAILABLE_NOTE, tool_call_id=call_id))
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
                else:
                    messages.append(ToolMessage(result, tool_call_id=call_id))
            return Command(update={"messages": messages, **update}, goto="agent")

        builder = StateGraph(ChatState)
        builder.add_node("agent", agent)
        builder.add_node("tools", tools_node)
        builder.add_edge(START, "agent")
        builder.add_edge("tools", "agent")
        return builder.compile()

    # --- the whole graph -----------------------------------------------------------

    graph = StateGraph(ChatState)
    graph.add_node("load_house", load_house)
    graph.add_node("foreman", foreman)
    for name in SPECIALISTS:
        graph.add_node(name, specialist_graph(name))
        graph.add_edge(name, END)
    graph.add_edge(START, "load_house")
    graph.add_edge("load_house", "foreman")
    return graph.compile(checkpointer=checkpointer)


def last_reply(state: dict[str, Any]) -> str:
    """The text of the turn's last assistant message."""
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""
