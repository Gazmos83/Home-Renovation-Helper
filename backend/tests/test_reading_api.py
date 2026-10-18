"""installation-reading routes: owner-only, approved versions only, and no model or tracing traffic."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.agent import house_file
from app.db.models import KnowledgeSource, KnowledgeSourceVersion, Piece
from app.engineering.reading import NOTICE, _Rule
from app.engineering.registry import register_source
from app.engineering.schemas import Collection, SourceIn
from tests.api_helpers import create, desk, make_client, sign_in
from tests.blender_fakes import fake_success_launch
from tests.conftest import clean_house_file

PACKAGE = "wall-unit"


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    sign_in(c)
    clean_house_file(c.app.state.engine)
    yield c
    with Session(c.app.state.engine) as session:
        piece = session.get(Piece, PACKAGE)
        if piece is not None:
            session.delete(piece)
        session.commit()
    c.__exit__(None, None, None)


@pytest.fixture
def source(client: TestClient) -> Iterator[SimpleNamespace]:
    """One metadata-only source under a unique furniture tag that the rules point at."""
    tag = f"t-{uuid4().hex[:10]}"
    client.app.state.reading_rules = {
        "wall_shelf": _Rule(applicable_furniture=[f"{tag}-shelf"]),
        "wall_module": _Rule(applicable_furniture=[tag]),
    }
    with Session(client.app.state.engine) as session:
        version = register_source(
            session,
            SourceIn(
                key=f"reading-api-{uuid4().hex}",
                collections=[Collection.STANDARDS],
                metadata={"title": "Wall cabinet standard", "applicable_furniture": [tag],
                          "source_url": "https://example.org/std"},
            ),
        )
        ids = SimpleNamespace(id=version.id, source_id=version.source_id)
        session.commit()
    yield ids
    with Session(client.app.state.engine) as session:
        session.execute(delete(KnowledgeSourceVersion).where(KnowledgeSourceVersion.id == ids.id))
        session.execute(delete(KnowledgeSource).where(KnowledgeSource.id == ids.source_id))
        session.commit()


def _wall_unit(client: TestClient, *, approve: bool, mounting: str | None = "wall") -> None:
    spec = desk()
    if mounting:
        spec["modules"][0]["mounting"] = mounting
    assert create(client, PACKAGE, spec).status_code in (200, 201, 202)
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, PACKAGE, "Wall unit")
        house_file.record_version(session, PACKAGE, 1)
        session.commit()
    if approve:
        assert client.put(f"/packages/{PACKAGE}/versions/1/approval").status_code == 200


def test_an_approved_version_lists_reading_for_its_wall_module(client: TestClient, source) -> None:
    _wall_unit(client, approve=True)

    response = client.get(f"/packages/{PACKAGE}/versions/1/reading")

    assert response.status_code == 200
    body = response.json()
    assert body["notice"] == NOTICE
    (entry,) = body["entries"]
    assert entry["version_id"] == str(source.id)
    assert entry["source_url"] == "https://example.org/std"
    assert entry["items"] == [desk()["modules"][0]["id"]]


def test_an_unapproved_version_is_refused(client: TestClient, source) -> None:
    _wall_unit(client, approve=False)

    response = client.get(f"/packages/{PACKAGE}/versions/1/reading")

    assert response.status_code == 409
    assert "must be approved first" in response.json()["detail"]["reason"]


def test_no_wall_hung_items_says_so(client: TestClient, source) -> None:
    _wall_unit(client, approve=True, mounting=None)

    body = client.get(f"/packages/{PACKAGE}/versions/1/reading").json()

    assert body["entries"] == [] and body["message"] == "This version has no wall-hung items"


def test_a_listed_link_only_source_gives_its_reason(client: TestClient, source) -> None:
    _wall_unit(client, approve=True)

    response = client.get(f"/packages/{PACKAGE}/versions/1/reading/sources/{source.id}/blocks")

    assert response.status_code == 200
    assert response.json()["reason"] == "rights pending" and response.json()["blocks"] == []


def test_a_source_not_on_the_list_is_refused(client: TestClient, source) -> None:
    _wall_unit(client, approve=False)

    response = client.get(f"/packages/{PACKAGE}/versions/1/reading/sources/{source.id}/blocks")

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path", ["/packages/x/versions/1/reading", f"/packages/x/versions/1/reading/sources/{uuid4()}/blocks"]
)
def test_the_reading_routes_need_the_owner_cookie(
    migrated_database: str, render_root: Path, fake_blender: Path, path: str
) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    assert c.get(path).status_code == 401
    c.__exit__(None, None, None)


def test_reading_makes_no_network_call_and_leaves_checkpoints_alone(
    client: TestClient, source, monkeypatch
) -> None:
    _wall_unit(client, approve=True)

    def checkpoints() -> int:
        with Session(client.app.state.engine) as session:
            return session.execute(text("SELECT count(*) FROM checkpoints")).scalar_one()

    before = checkpoints()
    calls: list[object] = []

    def refuse(self, address):  # OpenRouter and Langfuse would both need an outbound socket
        calls.append(address)
        raise OSError("network disabled for this test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    listed = client.get(f"/packages/{PACKAGE}/versions/1/reading")
    read = client.get(f"/packages/{PACKAGE}/versions/1/reading/sources/{source.id}/blocks")
    monkeypatch.undo()

    assert listed.status_code == 200 and read.status_code == 200
    assert calls == []
    assert checkpoints() == before
