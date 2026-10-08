"""A compiled Foreman graph on `InMemorySaver` with one fake model per slot."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agent import house_file
from app.agent.foreman import build_graph
from app.agent.models.slots import LOOP_SLOTS
from app.agent.tools.base import ToolDeps
from tests.fakes import FakeChatModel


def fake_models(**scripts: dict[str, Any]) -> dict[str, FakeChatModel]:
    """One `FakeChatModel` per loop slot; `scripts[slot]` seeds its fields."""
    return {slot: FakeChatModel(**scripts.get(slot, {})) for slot in LOOP_SLOTS}


@dataclass
class Harness:
    graph: Any
    models: dict[str, FakeChatModel]
    state: SimpleNamespace
    owner_id: UUID = field(default_factory=uuid4)
    thread: UUID | None = None
    room: str | None = None

    def start(self, package_id: str | None = None) -> UUID:
        """A new conversation, in the harness's confirmed room, about `package_id` if given."""
        with ToolDeps(self.state).session() as session:
            thread = house_file.create_thread(session, "test", package_id=package_id)
            if package_id:
                house_file.add_build(session, thread.id, package_id)
            session.commit()
            self.thread = thread.id
        if self.room:
            confirm_room(self, self.room)
            if package_id:
                place_in_room(self, package_id)
        return self.thread

    @property
    def config(self) -> dict[str, Any]:
        assert self.thread is not None, "call start() first"
        return {
            "configurable": {
                "thread_id": f"chat:{self.thread}",
                "owner_id": str(self.owner_id),
                "chat_thread": str(self.thread),
            }
        }

    def turn(self, text: str) -> dict[str, Any]:
        from langchain_core.messages import HumanMessage

        return self.graph.invoke({"messages": [HumanMessage(text)]}, config=self.config)

    def answer(self, answer: str, reason: str | None = None) -> dict[str, Any]:
        return self.graph.invoke(Command(resume={"answer": answer, "reason": reason}), config=self.config)

    def snapshot(self):
        return self.graph.get_state(self.config)


def confirm_room(harness: Harness, name: str = "Hall") -> None:
    """Store a room and make it the thread's confirmed room, as an owner's `yes` would."""
    with ToolDeps(harness.state).session() as session:
        room = house_file.room_by_name(session, name) or house_file.upsert_room(
            session, name, [[0, 0], [3000, 0], [3000, 2000], [0, 2000]], 2500
        )
        house_file.set_thread_room(session, harness.thread, room)
        session.commit()


def place_in_room(harness: Harness, package_id: str, name: str | None = None) -> None:
    """Put a recorded piece in the harness's confirmed room (or `name`)."""
    with ToolDeps(harness.state).session() as session:
        room = house_file.room_by_name(session, name or harness.room or "Hall")
        house_file.set_piece_room(session, package_id, room)
        session.commit()


def make_harness(
    tool_state: SimpleNamespace,
    models: dict[str, FakeChatModel] | None = None,
    *,
    room: str | None = "Hall",
) -> Harness:
    """A harness whose thread has already confirmed `room`; `room=None` is a new conversation."""
    models = models or fake_models()
    # Nested tool calls (revision_review) read the slot model from ToolDeps.
    tool_state.models = models
    graph = build_graph(
        tool_state.engine,
        tool_state.settings,
        model_provider=models.__getitem__,
        model_ids=lambda slot: f"fake/{slot}",
        checkpointer=InMemorySaver(),
        deps=ToolDeps(tool_state),
    )
    harness = Harness(graph=graph, models=models, state=tool_state, room=room)
    harness.start()
    return harness
