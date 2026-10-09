"""design-guidelines: hardware data sheets are cited, keep ranges as ranges and reach the corpus."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.chunk_store import count_chunks
from plugins.guidelines.tool import run
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch

pytestmark = pytest.mark.usefixtures("clean_chunks")

TOOM_PAGE = "https://www.toom.de/p/topfband-110/123456"
HINGE = {
    "key": "hinge-concealed-110", "kind": "hinge", "maker": "Hettich", "model": "Sensys 110",
    "values": {"cup_diameter_mm": {"value": 35}, "cup_depth_mm": {"value": 13}},
    "source_kind": "toom", "page_url": TOOM_PAGE,
}
PIN = {
    "key": "shelf-pin", "kind": "shelf_pin", "maker": "Hafele", "model": "Pin 5",
    "values": {"pitch_mm": {"value": 32}, "pins_per_shelf": 4},
    "source_kind": "manual", "citation": "Hafele leaflet 2024, p. 3",
}


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, fake_embedder) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    with Session(c.app.state.engine) as session:
        session.execute(text("DELETE FROM hardware_data_sheets"))
        session.commit()
    sign_in(c)
    yield c
    with Session(c.app.state.engine) as session:
        session.execute(text("DELETE FROM hardware_data_sheets"))
        session.commit()
    c.__exit__(None, None, None)


def chunks_of(client: TestClient, key: str) -> int:
    with Session(client.app.state.engine) as session:
        return count_chunks(session, url=f"owner-datasheet:{key}")


def reason(response) -> str:
    return response.json()["detail"]["reason"]


def test_every_route_needs_the_session(client: TestClient) -> None:
    anonymous = TestClient(client.app)
    assert anonymous.get("/hardware-data").status_code == 401
    assert anonymous.post("/hardware-data", json=HINGE).status_code == 401


def test_a_toom_hinge_sheet_is_found_with_its_citation(client: TestClient, make_ctx) -> None:
    created = client.post("/hardware-data", json=HINGE)
    assert created.status_code == 201
    assert created.json()["citation"] == TOOM_PAGE
    assert chunks_of(client, "hinge-concealed-110") >= 1
    result = run({"query": "hinge-concealed-110 Hettich Sensys 110 cup diameter"}, make_ctx())
    assert "hinge-concealed-110" in result and TOOM_PAGE in result


def test_a_manual_pin_sheet_needs_a_citation(client: TestClient) -> None:
    assert client.post("/hardware-data", json=PIN).status_code == 201
    refused = client.post("/hardware-data", json=PIN | {"key": "pin-b", "citation": " ", "model": "Pin 6"})
    assert refused.status_code == 422 and "citation" in reason(refused)


def test_another_models_source_is_refused_naming_its_maker_and_model(client: TestClient) -> None:
    client.post("/hardware-data", json=HINGE)
    other = client.post("/hardware-data", json=HINGE | {"key": "hinge-b", "model": "Intermat 95"})
    assert other.status_code == 422
    assert "Hettich Sensys 110" in reason(other)
    same = client.post("/hardware-data", json=HINGE | {"key": "hinge-c"})
    assert same.status_code == 201


def test_a_page_off_toom_is_refused_naming_the_host(client: TestClient) -> None:
    response = client.post("/hardware-data", json=HINGE | {"page_url": "https://www.example.com/p/1"})
    assert response.status_code == 422 and "www.example.com" in reason(response)


def test_a_ranged_end_distance_is_stored_and_mirrored_as_a_range(client: TestClient) -> None:
    values = {"end_distance_mm": {"min": 80, "max": 120}}
    created = client.post("/hardware-data", json=HINGE | {"values": values})
    assert created.status_code == 201
    assert created.json()["values"] == values
    with Session(client.app.state.engine) as session:
        stored = session.execute(
            text("SELECT content FROM chunks WHERE url = 'owner-datasheet:hinge-concealed-110'")
        ).scalars().all()
    assert any("80–120 mm" in content for content in stored)


@pytest.mark.parametrize("bad", [{"min": 120, "max": 80}, {"min": 80, "max": 80}])
def test_a_range_with_min_not_below_max_is_refused_naming_the_field(client: TestClient, bad: dict) -> None:
    response = client.post("/hardware-data", json=HINGE | {"values": {"end_distance_mm": bad}})
    assert response.status_code == 422 and "end_distance_mm" in reason(response)


def test_a_range_on_pins_per_shelf_is_refused_as_a_count(client: TestClient) -> None:
    response = client.post("/hardware-data", json=PIN | {"values": {"pins_per_shelf": {"min": 4, "max": 6}}})
    assert response.status_code == 422
    assert "pins_per_shelf" in reason(response) and "count" in reason(response)


def test_delete_removes_the_passage(client: TestClient) -> None:
    sheet_id = client.post("/hardware-data", json=HINGE).json()["id"]
    assert client.delete(f"/hardware-data/{sheet_id}").status_code == 204
    assert chunks_of(client, "hinge-concealed-110") == 0
    assert client.delete(f"/hardware-data/{sheet_id}").status_code == 404


def test_edit_replaces_the_values_and_the_passage(client: TestClient) -> None:
    sheet_id = client.post("/hardware-data", json=HINGE).json()["id"]
    body = {k: v for k, v in HINGE.items() if k != "key"} | {"values": {"cup_diameter_mm": {"value": 26}}}
    assert client.put(f"/hardware-data/{sheet_id}", json=body).json()["values"] == {"cup_diameter_mm": {"value": 26}}
    with Session(client.app.state.engine) as session:
        stored = session.execute(
            text("SELECT content FROM chunks WHERE url = 'owner-datasheet:hinge-concealed-110'")
        ).scalars().all()
    assert any("26 mm" in c for c in stored) and not any("35 mm" in c for c in stored)


def test_a_refusal_names_the_field_it_is_about(client: TestClient) -> None:
    off_host = client.post("/hardware-data", json=HINGE | {"page_url": "https://www.example.com/p/1"})
    assert off_host.json()["detail"]["field"] == "page_url"
    no_citation = client.post("/hardware-data", json=PIN | {"citation": ""})
    assert no_citation.json()["detail"]["field"] == "citation"
    bad_value = client.post("/hardware-data", json=PIN | {"values": {"pins_per_shelf": {"min": 4, "max": 6}}})
    assert bad_value.json()["detail"]["field"] == "values"
