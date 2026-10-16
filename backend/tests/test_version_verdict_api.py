"""version-verdict: the owner's verdict routes and the developer's verdict summary."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.agent import house_file
from app.db.models import Piece
from app.observability.langfuse import Tracing
from tests.api_helpers import sign_in
from tests.test_admin_models_api import _client as dev_client
from tests.test_langfuse_tracing import FakeClient, FakeHandler, _configured

PIECE = "amesbury-wardrobe"
BASE = f"/packages/{PIECE}/versions/4/verdict"
DESIGNER = "~deepseek/deepseek-v4-flash-latest"
DRAWERS = "the side sections lost their 5 drawers"


def _clean(client: TestClient) -> None:
    with Session(client.app.state.engine) as session:
        session.execute(delete(Piece).where(Piece.package_id == PIECE))
        session.commit()


def _versions(client: TestClient) -> None:
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, PIECE, "Amesbury Wardrobe")
        house_file.record_version(session, PIECE, 4)
        house_file.record_version(session, PIECE, 5, slot="designer", model=DESIGNER)
        session.commit()


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = dev_client(migrated_database, render_root, fake_blender, dev=True)
    sign_in(c)
    _clean(c)
    _versions(c)
    yield c
    _clean(c)
    c.__exit__(None, None, None)


def test_a_blockout_version_is_marked_wrong_and_read_back(client: TestClient) -> None:
    assert client.get(BASE).json() == {"verdict": None}
    response = client.put(BASE, json={"verdict": "mismatch", "note": DRAWERS})
    assert response.status_code == 200
    body = response.json()["verdict"]
    assert (body["verdict"], body["note"], body["status"]) == ("mismatch", DRAWERS, "open")
    assert client.get(BASE).json()["verdict"]["note"] == DRAWERS


def test_refusals_carry_their_reason_and_status(client: TestClient) -> None:
    empty = client.put(BASE, json={"verdict": "mismatch", "note": " "})
    assert empty.status_code == 422 and empty.json()["detail"]["reason"] == "a note of what does not match is needed"
    unknown = client.put(f"/packages/{PIECE}/versions/9/verdict", json={"verdict": "matches"})
    assert unknown.status_code == 404 and "version 9" in unknown.json()["detail"]["reason"]
    extra = client.put(BASE, json={"verdict": "matches", "slot": "designer"})
    assert extra.status_code == 422 and "'slot'" in extra.json()["detail"]["reason"]
    nothing = client.patch(f"{BASE}/status", json={"status": "resolved"})
    assert nothing.status_code == 409


def test_resolving_and_clearing(client: TestClient) -> None:
    client.put(BASE, json={"verdict": "mismatch", "note": DRAWERS})
    assert client.patch(f"{BASE}/status", json={"status": "resolved"}).json()["verdict"]["status"] == "resolved"
    assert client.delete(BASE).json() == {"verdict": None}
    assert client.get(BASE).json() == {"verdict": None}


def test_no_slot_or_model_in_the_homeowner_response(client: TestClient) -> None:
    for response in (
        client.put(f"/packages/{PIECE}/versions/5/verdict", json={"verdict": "mismatch", "note": DRAWERS}),
        client.get(f"/packages/{PIECE}/versions/5/verdict"),
    ):
        assert response.status_code == 200
        for secret in ("designer", "deepseek", '"slot"', '"model"'):
            assert secret not in response.text


def test_a_verdict_is_traced_and_survives_tracing_failing(client: TestClient, detach_tracing) -> None:
    langfuse = FakeClient()
    client.app.state.tracing = detach_tracing(
        Tracing(_configured(), handler_factory=lambda _s: (langfuse, FakeHandler()))
    )
    assert client.put(f"/packages/{PIECE}/versions/5/verdict", json={"verdict": "matches"}).status_code == 200
    assert langfuse.opened_with["name"] == "version-verdict"

    def explode(**_kwargs):
        raise ConnectionError("langfuse unreachable")

    langfuse.start_as_current_observation = explode  # type: ignore[method-assign]
    response = client.put(f"/packages/{PIECE}/versions/5/verdict", json={"verdict": "mismatch", "note": DRAWERS})
    assert response.status_code == 200 and response.json()["verdict"]["verdict"] == "mismatch"


def test_the_developer_reads_counts_and_notes_per_slot_and_model(client: TestClient) -> None:
    client.put(BASE, json={"verdict": "mismatch", "note": DRAWERS})
    client.put(f"/packages/{PIECE}/versions/5/verdict", json={"verdict": "matches"})
    rows = {(r["slot"], r["model"]): r for r in client.get("/admin/feedback/verdicts").json()}
    assert (rows[("designer", DESIGNER)]["matches"], rows[("designer", DESIGNER)]["mismatch"]) == (1, 0)
    assert (rows[(None, None)]["matches"], rows[(None, None)]["mismatch"]) == (0, 1)
    ungrouped = client.get("/admin/feedback/verdicts/notes", params={"slot": "", "model": ""}).json()
    assert [(n["package_id"], n["version"], n["note"]) for n in ungrouped] == [(PIECE, 4, DRAWERS)]


def test_every_owner_route_needs_the_session(migrated_database: str, render_root: Path, fake_blender: Path) -> None:
    c = dev_client(migrated_database, render_root, fake_blender, dev=True)
    try:
        assert c.get(BASE).status_code == 401
        assert c.put(BASE, json={"verdict": "matches"}).status_code == 401
        assert c.delete(BASE).status_code == 401
        assert c.patch(f"{BASE}/status", json={"status": "resolved"}).status_code == 401
        assert c.get("/admin/feedback/verdicts").status_code == 401
    finally:
        c.__exit__(None, None, None)


def test_the_developer_routes_answer_404_when_the_panel_is_disabled(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = dev_client(migrated_database, render_root, fake_blender, dev=False)
    sign_in(c)
    try:
        assert c.get("/admin/feedback/verdicts").status_code == 404
        assert c.get("/admin/feedback/verdicts/notes").status_code == 404
    finally:
        c.__exit__(None, None, None)
