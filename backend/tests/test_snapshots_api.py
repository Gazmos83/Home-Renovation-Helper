"""price-list: the snapshot routes."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.pricing_helpers import clean_pricing

URL = "https://www.bauhaus.info/p/siebdruckplatte-15mm/123"


def yesterday() -> str:
    return (datetime.now(UTC).date() - timedelta(days=1)).isoformat()


def body(**over) -> dict:
    values = {
        "retailer": "bauhaus", "url": URL, "product_name": "Siebdruckplatte 15 mm", "price": "49.90",
        "currency": "EUR", "specification": "2500 x 1250 x 15 mm, Birke", "captured_on": yesterday(),
    }
    values.update(over)
    return values


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, fake_embedder) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    clean_pricing(c.app.state.engine)
    sign_in(c)
    yield c
    clean_pricing(c.app.state.engine)
    c.__exit__(None, None, None)


def test_a_snapshot_is_recorded_listed_and_deleted(client: TestClient) -> None:
    created = client.post("/snapshots", json=body())
    assert created.status_code == 201
    assert created.json()["retailer"] == "bauhaus" and created.json()["price"] == "49.90"
    assert [s["url"] for s in client.get("/snapshots").json()] == [URL]
    assert client.delete(f"/snapshots/{created.json()['id']}").status_code == 204
    assert client.get("/snapshots").json() == []


def test_a_snapshot_can_prefill_an_entry(client: TestClient) -> None:
    prefill = {
        "key": "panel:sieb-15", "category": "panel", "unit": "per_piece",
        "sheet_length_mm": 2500, "sheet_width_mm": 1250, "thickness_mm": 15,
    }
    assert client.post("/snapshots", json=body(prefill=prefill)).status_code == 201
    entry = client.get("/price-list/panel:sieb-15").json()
    assert (entry["provenance"], entry["base_cents"]) == ("snapshot", 4990)


def test_a_future_date_is_refused_naming_the_field(client: TestClient) -> None:
    tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    response = client.post("/snapshots", json=body(captured_on=tomorrow))
    assert response.status_code == 422
    assert response.json()["detail"]["field"] == "captured_on"
    assert "future" in response.json()["detail"]["reason"]


def test_a_snapshot_an_entry_was_made_from_cannot_be_deleted(client: TestClient) -> None:
    prefill = {"key": "hw:snap", "category": "hardware", "unit": "per_piece"}
    snapshot = client.post("/snapshots", json=body(prefill=prefill)).json()
    response = client.delete(f"/snapshots/{snapshot['id']}")
    assert response.status_code == 409 and "'hw:snap'" in response.json()["detail"]["reason"]


def test_an_unknown_snapshot_is_not_found(client: TestClient) -> None:
    assert client.delete("/snapshots/00000000-0000-0000-0000-000000000000").status_code == 404
