"""design-guidelines: the owner's notes reach the corpus, need a citation, and are searched with their source."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.prompts import CLOSE_TOKEN, OPEN_PREFIX
from app.db.chunk_store import count_chunks
from plugins.guidelines.tool import NOTHING_FOUND, run
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch

pytestmark = pytest.mark.usefixtures("clean_chunks")

NOTE = {
    "title": "Passage vor dem Kleiderschrank",
    "body": "Vor einem Kleiderschrank bleibt ein freier Durchgang für das Öffnen der Türen.",
    "value": 900, "unit": "mm", "citation": "Neufert, Bauentwurfslehre, S. 123",
}


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, fake_embedder) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    with Session(c.app.state.engine) as session:
        session.execute(text("DELETE FROM guideline_notes"))
        session.commit()
    sign_in(c)
    yield c
    with Session(c.app.state.engine) as session:
        session.execute(text("DELETE FROM guideline_notes"))
        session.commit()
    c.__exit__(None, None, None)


def chunks_of(client: TestClient, note_id: str) -> int:
    with Session(client.app.state.engine) as session:
        return count_chunks(session, url=f"owner-note:{note_id}")


def test_every_route_needs_the_session(client: TestClient) -> None:
    anonymous = TestClient(client.app)
    assert anonymous.get("/guideline-notes").status_code == 401
    assert anonymous.post("/guideline-notes", json=NOTE).status_code == 401


def test_create_edit_and_delete_reach_the_corpus(client: TestClient) -> None:
    created = client.post("/guideline-notes", json=NOTE)
    assert created.status_code == 201
    note_id = created.json()["id"]
    assert chunks_of(client, note_id) >= 1

    edited = client.put(f"/guideline-notes/{note_id}", json=NOTE | {"body": "Neuer Text zum Durchgang."})
    assert edited.status_code == 200 and edited.json()["body"] == "Neuer Text zum Durchgang."
    with Session(client.app.state.engine) as session:
        stored = session.execute(
            text("SELECT content FROM chunks WHERE url = :u"), {"u": f"owner-note:{note_id}"}
        ).scalars().all()
    assert any("Neuer Text" in content for content in stored)
    assert not any("freier Durchgang" in content for content in stored)

    assert [n["id"] for n in client.get("/guideline-notes").json()] == [note_id]
    assert client.delete(f"/guideline-notes/{note_id}").status_code == 204
    assert chunks_of(client, note_id) == 0
    assert client.get("/guideline-notes").json() == []
    assert client.delete(f"/guideline-notes/{note_id}").status_code == 404


@pytest.mark.parametrize("change", [{"citation": ""}, {"citation": "   "}, {"title": " "}, {"unit": None}])
def test_a_note_without_a_citation_title_or_unit_is_refused(client: TestClient, change: dict) -> None:
    response = client.post("/guideline-notes", json=NOTE | change)
    assert response.status_code == 422
    assert client.get("/guideline-notes").json() == []


def test_search_returns_the_note_wrapped_with_its_source(client: TestClient, tool_deps, make_ctx) -> None:
    client.post("/guideline-notes", json=NOTE)
    result = run({"query": "Passage vor dem Kleiderschrank freier Durchgang Türen"}, make_ctx())
    assert OPEN_PREFIX in result and CLOSE_TOKEN in result
    assert 'source="owner"' in result and "Neufert, Bauentwurfslehre, S. 123" in result
    assert "name its source" in result


def test_search_says_when_nothing_matched(client: TestClient, make_ctx) -> None:
    assert run({"query": "Quantenverschränkung Kaffeemaschine"}, make_ctx()) == NOTHING_FOUND
