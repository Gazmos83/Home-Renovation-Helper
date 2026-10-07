"""dev-panel: one conversation's model calls, behind the developer gate."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api_helpers import sign_in
from tests.conftest import clean_house_file
from tests.graph_helpers import fake_models
from tests.test_admin_models_api import _client
from tests.test_chat_api import install


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    app_client = _client(migrated_database, render_root, fake_blender, dev=True)
    clean_house_file(app_client.app.state.engine)
    sign_in(app_client)
    yield app_client
    clean_house_file(app_client.app.state.engine)
    app_client.__exit__(None, None, None)


def _first_turn(client: TestClient) -> str:
    install(client, fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "t"}], "replies": ["Hall bench"]},
        intake={"replies": ["How wide is the hall?"]},
    ))
    thread = client.post("/chat/threads", json={}).json()["thread_id"]
    turn = client.post(f"/chat/threads/{thread}/turns", json={"message": "a bench for the hall"})
    assert turn.status_code == 200, turn.text
    return thread


def test_a_first_turn_lists_the_foreman_intake_and_title_calls_newest_first(client: TestClient) -> None:
    thread = _first_turn(client)
    calls = client.get(f"/admin/threads/{thread}/calls")
    assert calls.status_code == 200
    rows = calls.json()
    routing = client.app.state.routing
    assert [(r["slot"], r["operation"]) for r in rows] == [
        ("foreman", "chat.title"),
        ("intake", "chat.intake"),
        ("foreman", "chat.foreman"),
    ]
    assert [r["model"] for r in rows] == [
        routing.model_for("foreman"), routing.model_for("intake"), routing.model_for("foreman"),
    ]
    for row in rows:
        assert row["input_tokens"] == 5 and row["output_tokens"] == 5 and row["estimated"] is False

    # Usage stays when the conversation goes, without the link.
    assert client.delete(f"/chat/threads/{thread}").status_code == 204
    assert client.get(f"/admin/threads/{thread}/calls").status_code == 404


def test_no_homeowner_response_names_a_model(client: TestClient) -> None:
    thread = _first_turn(client)
    routing = client.app.state.routing
    for path in ("/chat/threads", f"/chat/threads/{thread}"):
        body = json.dumps(client.get(path).json())
        for slug in routing.distinct_slugs():
            assert slug not in body


def test_an_unknown_thread_is_not_found(client: TestClient) -> None:
    assert client.get(f"/admin/threads/{uuid4()}/calls").status_code == 404


def test_the_route_is_hidden_when_the_panel_is_disabled(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    closed = _client(migrated_database, render_root, fake_blender, dev=False)
    try:
        sign_in(closed)
        thread = closed.post("/chat/threads", json={}).json()["thread_id"]
        assert closed.get(f"/admin/threads/{thread}/calls").status_code == 404
    finally:
        clean_house_file(closed.app.state.engine)
        closed.__exit__(None, None, None)
