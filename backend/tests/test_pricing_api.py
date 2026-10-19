"""cut-list-pricing: the pricing, remnant and home-store routes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.pricing import price_list
from app.pricing.store import StoreCapture, upsert_store
from tests.api_helpers import create, make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.pricing_helpers import approve_version, clean_pricing
from tests.test_pricing import KEY, price_the_desk

PRICINGS = "/packages/hall-bench/versions/1/pricings"


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    clean_pricing(c.app.state.engine)
    sign_in(c)
    assert create(c).status_code == 202
    yield c
    clean_pricing(c.app.state.engine)
    c.__exit__(None, None, None)


def seed(client: TestClient, *, store: bool = True, approved: bool = True) -> None:
    with Session(client.app.state.engine) as session:
        if approved:
            approve_version(session, "hall-bench", 1)
        if store:
            upsert_store(session, StoreCapture(store_key=KEY, name="Friedrichshain", url="https://toom.de/m/x/", offers_cutting=True))
        price_the_desk(session)
        session.commit()


def test_every_route_needs_the_session(client: TestClient) -> None:
    anonymous = TestClient(client.app)
    for method, path in (("post", PRICINGS), ("get", PRICINGS), ("get", "/remnants"), ("get", "/stores/home"),
                         ("post", "/remnants"), ("put", "/stores/home/restrictions/max_thickness_mm")):
        assert getattr(anonymous, method)(path).status_code == 401, path


def test_a_version_is_priced_and_the_record_is_readable_and_listed(client: TestClient) -> None:
    seed(client)
    created = client.post(PRICINGS, json={})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["complete"] is True and body["version"] == 1 and body["total_cents"] > 0
    assert client.get(f"/pricings/{body['id']}").json()["total_cents"] == body["total_cents"]
    assert [p["id"] for p in client.get(PRICINGS).json()] == [body["id"]]


def test_repricing_makes_a_second_record(client: TestClient) -> None:
    seed(client)
    first = client.post(PRICINGS, json={}).json()
    client.put("/price-list/panel:oak-veneer-birch:18/override", json={"cents": 1000})
    second = client.post(PRICINGS, json={}).json()
    assert second["id"] != first["id"] and second["total_cents"] < first["total_cents"]
    assert client.get(f"/pricings/{first['id']}").json()["total_cents"] == first["total_cents"]


def test_the_cut_charge_choice_and_delivery_are_carried(client: TestClient) -> None:
    seed(client)
    body = client.post(PRICINGS, json={"cut_charge_mode": "per_cut", "delivery_key": "delivery:10km"}).json()
    assert body["cut_charge_mode"] == "per_cut" and body["delivery_cents"] == 5499
    assert client.post(PRICINGS, json={"cut_charge_mode": "weekly"}).status_code == 422


def test_a_missing_home_store_is_404_naming_it_and_a_missing_version_is_not_found(client: TestClient) -> None:
    seed(client, store=False)
    missing = client.post(PRICINGS, json={})
    assert missing.status_code == 404 and "berlin-friedrichshain" in missing.json()["detail"]["reason"]
    assert client.post("/packages/hall-bench/versions/9/pricings", json={}).status_code == 404
    assert client.get("/pricings/00000000-0000-0000-0000-000000000000").status_code == 404


def test_the_remnant_rack_is_added_listed_and_removed(client: TestClient) -> None:
    added = client.post("/remnants", json={
        "material_key": "panel:oak-veneer-birch:18", "length_mm": 600, "width_mm": 400, "grain_axis": "length",
    })
    assert added.status_code == 201
    assert [r["quantity"] for r in client.get("/remnants").json()] == [1]
    assert client.post("/remnants", json={
        "material_key": "x", "length_mm": 0, "width_mm": 400, "grain_axis": "length",
    }).status_code == 422
    assert client.delete(f"/remnants/{added.json()['id']}").status_code == 204
    assert client.delete(f"/remnants/{added.json()['id']}").status_code == 404


def test_the_home_store_is_read_and_its_restrictions_outrank_the_pages(client: TestClient) -> None:
    assert client.get("/stores/home").status_code == 404
    seed(client)
    home = client.get("/stores/home").json()
    assert home["store_key"] == KEY
    assert {s["service"]: s["availability"] for s in home["services"]}["gerader_zuschnitt"] == "performed"

    put = client.put("/stores/home/restrictions/max_thickness_mm", json={"numeric_value": 25, "note": "counter"})
    assert put.status_code == 200 and put.json()["recorded_by"] == "owner@example.com"
    assert client.get("/stores/home").json()["restrictions"][0]["numeric_value"] == 25
    assert client.put("/stores/home/restrictions/max_thickness_mm", json={}).status_code == 422
    assert client.put("/stores/home/restrictions/nope", json={"numeric_value": 1}).status_code == 422
    assert client.delete("/stores/home/restrictions/max_thickness_mm").status_code == 204
    assert client.delete("/stores/home/restrictions/max_thickness_mm").status_code == 404


def test_a_used_entry_cannot_be_deleted_after_a_pricing(client: TestClient) -> None:
    seed(client)
    client.post(PRICINGS, json={})
    response = client.delete("/price-list/hinge-flap")
    assert response.status_code == 409 and "hall-bench version 1" in response.json()["detail"]["reason"]
    with Session(client.app.state.engine) as session:
        assert price_list.get_entry(session, "hinge-flap") is not None


# --- only an approved version is priced -------------------------------------------------------


def test_an_unapproved_version_is_refused_with_409_and_writes_no_record(client: TestClient) -> None:
    seed(client, approved=False)
    response = client.post(PRICINGS, json={})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["failure_class"] == "not_approved"
    assert "approve it first in the version's inspector" in detail["reason"]
    assert client.get(PRICINGS).json() == []


def test_a_pricing_is_readable_after_unapproval_and_says_so(client: TestClient) -> None:
    seed(client)
    created = client.post(PRICINGS, json={}).json()
    assert created["version_approved"] is True
    with Session(client.app.state.engine) as session:
        from app.agent import house_file

        house_file.unapprove_version(session, "hall-bench", 1)
        session.commit()
    read = client.get(f"/pricings/{created['id']}").json()
    assert read["version_approved"] is False and read["total_cents"] == created["total_cents"]
    assert client.get(PRICINGS).json()[0]["version_approved"] is False
    assert client.post(PRICINGS, json={}).status_code == 409
