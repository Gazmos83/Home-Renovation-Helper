"""homeowner-chat: GET/PUT /chat/threads/{id}/tools."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> TestClient:
    app_client = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    sign_in(app_client)
    yield app_client
    app_client.__exit__(None, None, None)


def _thread(client: TestClient) -> str:
    response = client.post("/chat/threads", json={"title": "Hall"})
    assert response.status_code == 201
    return response.json()["thread_id"]


def test_a_new_thread_lists_toggleable_plugins_at_their_defaults(client: TestClient) -> None:
    thread_id = _thread(client)
    response = client.get(f"/chat/threads/{thread_id}/tools")
    assert response.status_code == 200
    body = response.json()
    by_name = {row["plugin"]: row for row in body}
    assert "room_fit" in by_name
    assert by_name["room_fit"]["enabled"] is True
    assert by_name["room_fit"]["toggleable"] is True
    assert by_name["create_piece"]["enabled"] is True
    assert by_name["create_piece"]["toggleable"] is False
    assert "model" not in str(body).lower() or all("model" not in row for row in body)
    for row in body:
        assert "token" not in row
        assert "model" not in row
        assert set(row) == {"plugin", "description", "enabled", "toggleable"}


def test_a_change_applies_from_the_next_turn(client: TestClient) -> None:
    thread_id = _thread(client)
    response = client.put(
        f"/chat/threads/{thread_id}/tools/room_fit", json={"enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    listed = client.get(f"/chat/threads/{thread_id}/tools").json()
    assert next(row for row in listed if row["plugin"] == "room_fit")["enabled"] is False


def test_switching_off_create_piece_is_409(client: TestClient) -> None:
    thread_id = _thread(client)
    response = client.put(
        f"/chat/threads/{thread_id}/tools/create_piece", json={"enabled": False}
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["failure_class"] == "not_toggleable"
    assert "create_piece" in detail["reason"]


def test_a_globally_disabled_plugin_is_409_and_hidden(client: TestClient, migrated_database: str) -> None:
    from sqlalchemy.orm import Session

    from app.db.session import make_engine
    from app.plugins.enablement import set_global_enabled

    engine = make_engine(migrated_database)
    with Session(engine) as session:
        set_global_enabled(session, "room_fit", False)
        session.commit()
    try:
        thread_id = _thread(client)
        listed = client.get(f"/chat/threads/{thread_id}/tools").json()
        assert "room_fit" not in {row["plugin"] for row in listed}
        response = client.put(
            f"/chat/threads/{thread_id}/tools/room_fit", json={"enabled": True}
        )
        assert response.status_code == 409
        assert response.json()["detail"]["failure_class"] == "globally_disabled"
    finally:
        with Session(engine) as session:
            set_global_enabled(session, "room_fit", True)
            session.commit()
        engine.dispose()


def test_no_model_or_token_in_the_body(client: TestClient) -> None:
    thread_id = _thread(client)
    for response in (
        client.get(f"/chat/threads/{thread_id}/tools"),
        client.put(f"/chat/threads/{thread_id}/tools/cut_list", json={"enabled": False}),
    ):
        dumped = response.text.lower()
        assert "openai/" not in dumped
        assert "deepseek/" not in dumped
        assert "token" not in dumped
        assert "gpt-" not in dumped
