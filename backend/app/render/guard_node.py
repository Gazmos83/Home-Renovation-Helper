"""The render guard as a graph node (render-guard design decision 1).

For `final`, the node pauses with LangGraph's `interrupt()` carrying the
estimate; the run resumes only with the owner's answer, and only an exact "yes"
mints a ticket. A draft runs straight through.

A `RenderTicket` is deliberately not serialisable (it is a live, single-use
capability), so it never enters checkpointed state: the node stores it in the
in-process `TicketBook` and puts only its id in state. The node that launches
the render calls `book.take(ticket_id)`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4

from langgraph.types import interrupt

from app.render.benchmark_store import Benchmark
from app.render.estimate import DEFAULT_CYCLES_MULTIPLIER
from app.render.guard import RenderRefused, RenderTicket, authorise, quote
from app.render.tiers import Tiers


class TicketBook:
    """Holds minted tickets until the launching node takes them (once)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tickets: dict[str, RenderTicket] = {}

    def add(self, ticket: RenderTicket) -> str:
        ticket_id = uuid4().hex
        with self._lock:
            self._tickets[ticket_id] = ticket
        return ticket_id

    def take(self, ticket_id: str) -> RenderTicket | None:
        with self._lock:
            return self._tickets.pop(ticket_id, None)


def make_guard_node(
    *,
    tiers: Tiers,
    book: TicketBook,
    benchmark: Callable[[], Benchmark | None],
    cycles_multiplier: Callable[[], float] = lambda: DEFAULT_CYCLES_MULTIPLIER,
) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """A node reading `state["render_request"]` and returning either
    `{"ticket_id": ...}` or `{"refusal": reason}`.

    The request holds `package_id`, `version`, `kind`, `tier`, optional `room`
    and `raw_fields` (the names the caller supplied, so raw knobs are refused).
    """

    def node(state: Mapping[str, Any]) -> dict[str, Any]:
        request = dict(state["render_request"])
        common = {
            "package_id": request["package_id"],
            "version": request["version"],
            "kind": request["kind"],
            "tier": request.get("tier"),
            "tiers": tiers,
            "benchmark": benchmark(),
            "cycles_multiplier": cycles_multiplier(),
            "room": bool(request.get("room", False)),
            "raw_fields": request.get("raw_fields", ()),
        }
        try:
            priced = quote(**common)
            approval = None
            if priced.tier.name == "final":
                # Pauses the run; nothing has been launched. Resumes with the
                # owner's answer.
                approval = interrupt(
                    {
                        "type": "render_approval",
                        "tier": priced.tier.name,
                        "estimate_seconds": priced.estimate_seconds,
                        "estimate": priced.estimate_text,
                        "summary": priced.summary,
                    }
                )
            ticket = authorise(**common, approval=approval)
        except RenderRefused as refusal:
            return {"refusal": refusal.reason, "ticket_id": None}
        return {"ticket_id": book.add(ticket), "refusal": None}

    return node
