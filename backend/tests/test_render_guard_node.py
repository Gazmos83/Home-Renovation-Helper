"""render-guard: the graph node pauses a final for approval and never earlier."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.render.benchmark_store import Benchmark
from app.render.guard_node import TicketBook, make_guard_node
from app.render.tiers import load_tiers

TIERS = load_tiers()
BENCH = Benchmark(2.5, "t", "5.2.1 LTS")


class State(TypedDict, total=False):
    render_request: dict[str, Any]
    ticket_id: str | None
    refusal: str | None
    launched: bool


def _graph(book: TicketBook, launches: list[str]):
    def launch(state: State) -> dict[str, Any]:
        ticket = book.take(state["ticket_id"]) if state.get("ticket_id") else None
        if ticket is None:
            return {"launched": False}
        ticket.consume()
        launches.append(ticket.quote.tier.name)
        return {"launched": True}

    builder = StateGraph(State)
    builder.add_node("guard", make_guard_node(tiers=TIERS, book=book, benchmark=lambda: BENCH))
    builder.add_node("launch", launch)
    builder.add_edge(START, "guard")
    builder.add_edge("guard", "launch")
    builder.add_edge("launch", END)
    return builder.compile(checkpointer=InMemorySaver())


def _request(tier: str) -> dict[str, Any]:
    return {
        "render_request": {"package_id": "desk", "version": 1, "kind": "turntable", "tier": tier}
    }


def _config(name: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": name}}


def test_a_draft_runs_straight_through() -> None:
    launches: list[str] = []
    result = _graph(TicketBook(), launches).invoke(_request("draft"), _config("t-draft"))
    assert launches == ["draft"]
    assert result["launched"] is True and "__interrupt__" not in result


def test_a_final_interrupts_with_the_estimate_before_any_launch() -> None:
    launches: list[str] = []
    result = _graph(TicketBook(), launches).invoke(_request("final"), _config("t-final"))
    [pause] = result["__interrupt__"]
    assert pause.value["type"] == "render_approval"
    assert pause.value["tier"] == "final"
    assert pause.value["estimate"] == "about 101 minutes"
    assert launches == [], "nothing launched while waiting for approval"


def test_resuming_a_final_with_yes_launches_it() -> None:
    launches: list[str] = []
    graph = _graph(TicketBook(), launches)
    config = _config("t-yes")
    graph.invoke(_request("final"), config)
    result = graph.invoke(Command(resume="yes"), config)
    assert launches == ["final"]
    assert result["launched"] is True and result["refusal"] is None


def test_resuming_a_final_with_no_is_a_refusal() -> None:
    launches: list[str] = []
    graph = _graph(TicketBook(), launches)
    config = _config("t-no")
    graph.invoke(_request("final"), config)
    result = graph.invoke(Command(resume="no"), config)
    assert launches == []
    assert result["launched"] is False
    assert "not approved" in result["refusal"]


def test_a_refused_request_is_stated_and_launches_nothing() -> None:
    launches: list[str] = []
    result = _graph(TicketBook(), launches).invoke(_request("ultra"), _config("t-bad"))
    assert launches == [] and "ultra" in result["refusal"]


def test_a_ticket_can_be_taken_once() -> None:
    book = TicketBook()
    launches: list[str] = []
    graph = _graph(book, launches)
    result = graph.invoke(_request("draft"), _config("t-once"))
    assert book.take(result["ticket_id"]) is None, "the launch node already took it"
