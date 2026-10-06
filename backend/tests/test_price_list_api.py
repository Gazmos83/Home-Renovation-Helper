"""price-list: the owner-gated routes, with a fake retailer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.limits import RateLimiter
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.pricing_helpers import clean_pricing, fixture, make_fetcher

PRODUCT = "/p/hartschaumplatte-eps-040-50-x-100-cm/3150333"
PAGES = {PRODUCT: (200, fixture("toom_product_3150333.html"))}
PANEL = {
    "key": "panel:birch-18", "label": "Birch plywood 18 mm", "category": "panel", "unit": "per_piece",
    "base_cents": 5990, "sheet_length_mm": 2500, "sheet_width_mm": 1250, "thickness_mm": 18,
}


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, fake_embedder) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    clean_pricing(c.app.state.engine)
    sign_in(c)
    fetcher, c.seen = make_fetcher(PAGES)
    c.app.state.live_fetcher = fetcher
    yield c
    clean_pricing(c.app.state.engine)
    c.__exit__(None, None, None)


def test_every_route_needs_the_session(client: TestClient) -> None:
    anonymous = TestClient(client.app)
    for method, path in (("get", "/price-list"), ("post", "/price-list"), ("get", "/price-list/x"),
                         ("post", "/price-list/from-url"), ("get", "/snapshots"), ("post", "/snapshots")):
        assert getattr(anonymous, method)(path).status_code == 401, path


def test_create_read_edit_override_and_delete(client: TestClient) -> None:
    created = client.post("/price-list", json=PANEL)
    assert created.status_code == 201
    assert created.json()["provenance"] == "manual" and created.json()["effective_cents"] == 5990

    assert client.get("/price-list/panel:birch-18").json()["label"] == "Birch plywood 18 mm"
    edited = client.patch("/price-list/panel:birch-18", json={"label": "Birch ply", "base_cents": 6100})
    assert edited.json()["base_cents"] == 6100

    over = client.put("/price-list/panel:birch-18/override", json={"cents": 3500, "note": "mine"}).json()
    assert (over["base_cents"], over["override_cents"], over["effective_cents"]) == (6100, 3500, 3500)
    assert client.delete("/price-list/panel:birch-18/override").json()["effective_cents"] == 6100

    assert client.delete("/price-list/panel:birch-18").status_code == 204
    assert client.get("/price-list/panel:birch-18").status_code == 404


def test_listing_filters_by_category(client: TestClient) -> None:
    client.post("/price-list", json=PANEL)
    keys = [e["key"] for e in client.get("/price-list", params={"category": "panel"}).json()]
    assert keys == ["panel:birch-18"]
    assert client.get("/price-list", params={"category": "timber"}).status_code == 422


def test_a_bad_entry_is_refused_naming_the_problem_and_a_duplicate_is_409(client: TestClient) -> None:
    bad = client.post("/price-list", json={**PANEL, "key": "p2", "sheet_length_mm": None})
    assert bad.status_code == 422 and "sheet length" in bad.json()["detail"]["reason"]
    client.post("/price-list", json=PANEL)
    again = client.post("/price-list", json=PANEL)
    assert again.status_code == 409 and again.json()["detail"]["failure_class"] == "conflict"
    assert client.post("/price-list", json={**PANEL, "base_cents": -1}).status_code == 422


def test_a_pasted_url_makes_a_captured_entry_and_indexes_the_page(client: TestClient) -> None:
    response = client.post(
        "/price-list/from-url",
        json={"url": f"https://toom.de{PRODUCT}", "key": "foam:50x100", "category": "finish"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["provenance"], body["base_cents"], body["source_url"]) == (
        "captured", 3649, f"https://toom.de{PRODUCT}",
    )
    with Session(client.app.state.engine) as session:
        count = session.execute(text("select count(*) from chunks where url = :u"), {"u": body["source_url"]}).scalar()
    assert count and count > 0


def test_another_retailer_is_refused_and_nothing_is_fetched(client: TestClient) -> None:
    response = client.post(
        "/price-list/from-url", json={"url": "https://www.bauhaus.info/p/x/1", "key": "x", "category": "finish"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["failure_class"] == "source_not_permitted"
    assert "www.bauhaus.info" in response.json()["detail"]["reason"]
    assert client.seen == []


def test_a_403_is_an_answer_and_creates_nothing(client: TestClient) -> None:
    fetcher, _ = make_fetcher({PRODUCT: (403, "denied")})
    client.app.state.live_fetcher = fetcher
    response = client.post(
        "/price-list/from-url", json={"url": f"https://toom.de{PRODUCT}", "key": "foam:x", "category": "finish"}
    )
    assert response.status_code == 409 and response.json()["detail"]["failure_class"] == "refused"
    assert client.get("/price-list/foam:x").status_code == 404


def test_refreshing_a_captured_entry_keeps_its_override(client: TestClient) -> None:
    client.post("/price-list/from-url", json={"url": f"https://toom.de{PRODUCT}", "key": "foam:50x100", "category": "finish"})
    client.put("/price-list/foam:50x100/override", json={"cents": 2800})
    client.patch("/price-list/foam:50x100", json={"label": "Foam"})
    refreshed = client.post("/price-list/foam:50x100/refresh").json()
    assert refreshed["outcome"] == "ok"
    assert (refreshed["entry"]["base_cents"], refreshed["entry"]["override_cents"]) == (3649, 2800)


def test_refreshing_a_manual_entry_says_there_is_no_source(client: TestClient) -> None:
    client.post("/price-list", json=PANEL)
    refreshed = client.post("/price-list/panel:birch-18/refresh").json()
    assert refreshed["outcome"] == "no_source" and "no page to read" in refreshed["reason"]


def test_the_fetching_routes_are_rate_limited(client: TestClient) -> None:
    client.app.state.price_rate_limiter = RateLimiter(2, 60)
    client.post("/price-list", json=PANEL)
    codes = [client.post("/price-list/panel:birch-18/refresh").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_a_used_entry_cannot_be_deleted(client: TestClient) -> None:
    client.post("/price-list", json=PANEL)
    with Session(client.app.state.engine) as session:
        session.execute(text(
            "INSERT INTO stores (store_key, source_site, name, url) VALUES ('s','toom','S','https://toom.de') "
            "ON CONFLICT DO NOTHING"
        ))
        pricing_id = session.execute(text(
            "INSERT INTO cut_list_pricings (id, package_id, version, store_key, materials_cents, cut_service_cents, "
            "total_cents, complete, result) VALUES (gen_random_uuid(), 'hall-bench', 1, 's', 0, 0, 0, true, '{}') RETURNING id"
        )).scalar()
        session.execute(text(
            "INSERT INTO cut_list_pricing_entries (id, pricing_id, entry_id, cents_used) "
            "SELECT gen_random_uuid(), :p, id, 5990 FROM supplier_prices WHERE key = 'panel:birch-18'"
        ), {"p": pricing_id})
        session.commit()
    response = client.delete("/price-list/panel:birch-18")
    assert response.status_code == 409 and "hall-bench version 1" in response.json()["detail"]["reason"]
