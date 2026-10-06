"""render-review: GET a version's reviews; PATCH resolve/dismiss."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent import house_file
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.conftest import clean_house_file

ITEM = {
    "aspect": "brief",
    "expected": "two drawers",
    "expected_source": "brief",
    "observed": "one drawer",
    "image": 1,
    "severity": "major",
}


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> TestClient:
    app_client = make_client(
        migrated_database, render_root, fake_blender, fake_pipeline_launch()
    )
    sign_in(app_client)
    clean_house_file(app_client.app.state.engine)
    yield app_client
    app_client.__exit__(None, None, None)


def _seed(client: TestClient, items: list[dict] | None = None) -> tuple[str, str]:
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, "hall-bench", "Hall bench")
        house_file.record_version(session, "hall-bench", 1)
        review = house_file.record_review(
            session, "hall-bench", 1, ["screenshot.png"], items if items is not None else [ITEM]
        )
        session.commit()
        item_id = house_file.items_of(session, review.id)[0].id
        return str(review.id), str(item_id)


def test_listing_returns_the_version_reviews(client: TestClient) -> None:
    review_id, item_id = _seed(client)
    response = client.get("/packages/hall-bench/versions/1/reviews")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == review_id
    assert body[0]["package_id"] == "hall-bench"
    assert body[0]["version"] == 1
    assert body[0]["renders"] == ["screenshot.png"]
    assert body[0]["items"][0]["id"] == item_id
    assert body[0]["items"][0]["status"] == "open"
    assert body[0]["items"][0]["aspect"] == "brief"
    dumped = json.dumps(body).lower()
    assert "openai/" not in dumped
    assert "deepseek/" not in dumped
    assert "anthropic/" not in dumped
    assert "model" not in dumped


def test_resolving_removes_the_item_from_the_designer_context(client: TestClient) -> None:
    review_id, item_id = _seed(client)
    with Session(client.app.state.engine) as session:
        assert len(house_file.latest_open_items(session, "hall-bench")) == 1
    response = client.patch(
        f"/reviews/{review_id}/items/{item_id}", json={"status": "resolved"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    dumped = json.dumps(response.json()).lower()
    assert "model" not in dumped
    with Session(client.app.state.engine) as session:
        assert house_file.latest_open_items(session, "hall-bench") == []
    listed = client.get("/packages/hall-bench/versions/1/reviews").json()
    assert listed[0]["items"][0]["status"] == "resolved"


def test_the_routes_need_the_owner_cookie(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    assert c.get("/packages/hall-bench/versions/1/reviews").status_code == 401
    assert (
        c.patch(
            f"/reviews/{uuid4()}/items/{uuid4()}", json={"status": "resolved"}
        ).status_code
        == 401
    )
    c.__exit__(None, None, None)


def test_no_model_slug_in_any_response(client: TestClient) -> None:
    review_id, item_id = _seed(client)
    listed = client.get("/packages/hall-bench/versions/1/reviews")
    patched = client.patch(
        f"/reviews/{review_id}/items/{item_id}", json={"status": "dismissed"}
    )
    combined = json.dumps(listed.json()) + json.dumps(patched.json())
    assert "openai/" not in combined
    assert "deepseek/" not in combined
    assert "fake/" not in combined
    assert "model" not in combined.lower()
