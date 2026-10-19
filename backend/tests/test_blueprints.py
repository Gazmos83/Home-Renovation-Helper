"""render-now-blueprints-verdict-note: a confirmed plan's images are kept as the apartment's blueprints."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.agent.tools.base import ToolContext, ToolDeps
from plugins.intake.tool import run_plan
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import png_bytes
from tests.conftest import clean_house_file
from tests.test_record_plan import PLAN


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, tmp_path: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, None)
    c.app.state.settings.upload_root = tmp_path / "uploads"
    clean_house_file(c.app.state.engine)
    sign_in(c)
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def _thread(client: TestClient) -> str:
    return client.post("/chat/threads", json={}).json()["thread_id"]


def _attach(client: TestClient, thread: str, name: str, content: bytes) -> None:
    response = client.post(f"/chat/threads/{thread}/uploads", files={"file": (name, content, "image/png")})
    assert response.status_code == 201


def _plan(client: TestClient, thread: str, *, approved: bool = True) -> object:
    ctx = ToolContext(deps=ToolDeps(client.app.state), owner_id=uuid4(), thread_id=UUID(thread))
    return run_plan(PLAN, replace(ctx, approved=approved))


def _listed(client: TestClient) -> list[dict]:
    response = client.get("/rooms/Bedroom/blueprints")
    assert response.status_code == 200
    return response.json()


def test_a_confirmed_plan_keeps_its_image_and_it_downloads(client: TestClient) -> None:
    thread = _thread(client)
    image = png_bytes(40, 30)
    _attach(client, thread, "grundriss.png", image)
    _plan(client, thread)
    [blueprint] = _listed(client)
    assert blueprint["original_name"] == "grundriss.png" and blueprint["kind"] == "png"
    download = client.get(blueprint["href"])
    assert download.status_code == 200 and download.content == image
    assert download.headers["content-type"] == "image/png"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"].startswith("attachment")
    assert "grundriss.png" in download.headers["content-disposition"]


def test_the_blueprint_outlives_its_conversation(client: TestClient) -> None:
    thread = _thread(client)
    _attach(client, thread, "grundriss.png", png_bytes(40, 30))
    _plan(client, thread)
    assert client.delete(f"/chat/threads/{thread}").status_code == 204
    [blueprint] = _listed(client)
    assert client.get(blueprint["href"]).status_code == 200


def test_a_declined_plan_keeps_nothing(client: TestClient) -> None:
    thread = _thread(client)
    _attach(client, thread, "grundriss.png", png_bytes(40, 30))
    _plan(client, thread, approved=False)
    assert client.get("/rooms/Bedroom/blueprints").status_code == 404


def test_a_plan_read_again_adds_the_new_image_first_and_keeps_none_twice(client: TestClient) -> None:
    thread = _thread(client)
    _attach(client, thread, "grundriss.png", png_bytes(40, 30))
    _plan(client, thread)
    _attach(client, thread, "grundriss-v2.png", png_bytes(50, 30))
    _plan(client, thread)
    assert [b["original_name"] for b in _listed(client)] == ["grundriss-v2.png", "grundriss.png"]


def test_a_room_with_no_apartment_lists_none(client: TestClient) -> None:
    from sqlalchemy.orm import Session

    from app.agent import house_file

    with Session(client.app.state.engine) as session:
        house_file.upsert_room(session, "Hall", [[0, 0], [2000, 0], [2000, 1500], [0, 1500]], 2500)
        session.commit()
    assert client.get("/rooms/Hall/blueprints").json() == []


def test_the_routes_need_the_cookie_and_answer_404_when_unknown(client: TestClient) -> None:
    assert client.get("/rooms/Nowhere/blueprints").status_code == 404
    assert client.get(f"/blueprints/{uuid4()}").status_code == 404
    client.cookies.clear()
    assert client.get("/rooms/Bedroom/blueprints").status_code == 401
    assert client.get(f"/blueprints/{uuid4()}").status_code == 401
