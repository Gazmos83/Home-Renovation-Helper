"""homeowner-chat: a turn is traced under the owner, thread and piece, and metered per slot."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelUsage
from app.observability.langfuse import SESSION_ID_KEY, USER_ID_KEY, Tracing
from tests.api_helpers import create, make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.conftest import clean_house_file
from tests.fakes import tool_call
from tests.graph_helpers import fake_models
from tests.test_chat_api import HALL, install, start
from tests.test_langfuse_tracing import FakeClient, FakeHandler, _configured


class SpyGraph:
    """Records the run config of every invocation, then delegates."""

    def __init__(self, graph: Any) -> None:
        self._graph = graph
        self.configs: list[dict[str, Any]] = []

    def invoke(self, value: Any, config: Any = None, **kwargs: Any) -> Any:
        self.configs.append(config)
        return self._graph.invoke(value, config=config, **kwargs)

    def stream(self, value: Any, config: Any = None, **kwargs: Any) -> Any:
        # Turns run through `graph.stream` (studio-chat-polish), streamed or not.
        self.configs.append(config)
        return self._graph.stream(value, config=config, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._graph, name)


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    clean_house_file(c.app.state.engine)
    sign_in(c)
    c.app.state.tracing = Tracing(_configured(), handler_factory=lambda _s: (FakeClient(), FakeHandler()))
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def test_the_turns_run_config_carries_owner_thread_and_piece_and_usage_names_each_slot(
    client: TestClient,
) -> None:
    assert create(client, "hall-bench").status_code == 202
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}]},
        intake={"steps": [[tool_call("record_brief", HALL)], "Saved."]},
    ))
    spy = SpyGraph(client.app.state.graph)
    client.app.state.graph = spy
    thread = start(client, package_id="hall-bench")

    paused = client.post(f"/chat/threads/{thread}/turns", json={"message": "a hall bench"}).json()
    client.post(
        f"/chat/threads/{thread}/resume",
        json={"confirmation_id": paused["pending"]["confirmation_id"], "answer": "yes"},
    )

    me = client.get("/auth/me")
    owner_id = me.json().get("id") or me.json().get("user_id")
    for config in spy.configs:
        assert config["metadata"][USER_ID_KEY] == owner_id
        assert config["metadata"][SESSION_ID_KEY] == thread
        assert config["metadata"]["langfuse_project_id"] == "hall-bench"
        assert config["configurable"]["thread_id"] == f"chat:{thread}"
        assert config["configurable"]["package_id"] == "hall-bench"
    assert len(spy.configs) == 2  # the turn and the resume, each its own trace

    routing = client.app.state.routing
    with Session(client.app.state.engine) as session:
        rows = session.scalars(
            select(ModelUsage).where(ModelUsage.trace_id.is_not(None)).order_by(ModelUsage.created_at)
        ).all()
    mine = [row for row in rows if str(row.user_id) == owner_id]
    assert {row.model_id for row in mine} == {routing.model_for("foreman"), routing.model_for("intake")}
    assert all(len(row.trace_id) == 32 for row in mine)
    # The untitled thread's first turn is followed by its title call (studio-chat-polish).
    assert {row.operation for row in mine} == {"chat.foreman", "chat.intake", "chat.title"}
    # The turn and its resume are separate traces.
    assert len({row.trace_id for row in mine}) == 2
