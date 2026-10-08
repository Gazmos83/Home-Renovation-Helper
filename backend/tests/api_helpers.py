"""Helpers for the route tests: an app with a fake launcher, signed in."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import make_engine
from app.main import create_app
from conftest import OWNER_EMAIL, OWNER_PASSWORD

TEMPLATE = Path(__file__).resolve().parents[1] / "fixtures/packages/templates/fold-down-desk.json"
ROOM = Path(__file__).resolve().parents[1] / "fixtures/packages/room-scene-rectangle.json"


def reset_owner(database_url: str) -> None:
    """The database is shared across tests: an earlier test may have left the
    owner with a changed password. Start from none, so the lifespan creates the
    owner from the configured password."""
    engine = make_engine(database_url)
    with Session(engine) as session:
        session.execute(text("TRUNCATE TABLE users CASCADE"))
        session.commit()
    engine.dispose()


def make_client(database_url: str, render_root: Path, binary: Path, launch) -> TestClient:
    settings = Settings(
        database_url=database_url,
        openrouter_api_key="sk-or-test",
        cors_origins="http://localhost:5173",
        owner_email=OWNER_EMAIL,
        owner_password=OWNER_PASSWORD,
        gateway_probe_enabled=False,
        render_root=render_root,
        blender_bin=binary,
        _env_file=None,
    )
    reset_owner(database_url)
    app = create_app(settings)
    app.state.blender_launch = launch
    client = TestClient(app)
    client.__enter__()  # runs the lifespan, which creates the owner
    return client


def sign_in(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    assert response.status_code == 200


def desk() -> dict:
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def room_document(kind: str, **output: object) -> dict:
    document = json.loads(ROOM.read_text(encoding="utf-8"))
    document["output"] = {"kind": kind, **output}
    return document


def create(client: TestClient, package_id: str = "hall-bench", spec: dict | None = None):
    return client.post("/packages", json={"package_id": package_id, "spec": spec or desk()})


def confirm_thread_room(client: TestClient, thread_id: str, name: str = "Hall") -> None:
    """Store a room and make it the conversation's confirmed room, as an owner's `yes` would;
    the thread's bound piece, when it has one, is put in the room."""
    from uuid import UUID

    from sqlalchemy.orm import Session

    from app.agent import house_file

    with Session(client.app.state.engine) as session:
        room = house_file.room_by_name(session, name) or house_file.upsert_room(
            session, name, [[0, 0], [3000, 0], [3000, 2000], [0, 2000]], 2500
        )
        house_file.set_thread_room(session, UUID(thread_id), room)
        bound = house_file.get_thread(session, UUID(thread_id)).package_id
        if bound and not house_file.set_piece_room(session, bound, room):
            house_file.record_piece(session, bound, bound, room_id=room.id)
        session.commit()
