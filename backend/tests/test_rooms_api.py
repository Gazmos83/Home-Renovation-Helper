"""rooms-page: the measured rooms are listed with their details and deleted after a warning."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent import house_file
from app.blender import storage
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_success_launch
from tests.conftest import clean_house_file

SQUARE = [[0, 0], [3000, 0], [3000, 2000], [0, 2000]]


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    clean_house_file(c.app.state.engine)
    sign_in(c)
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def _hall(client: TestClient, *, composition_status: str | None = None) -> None:
    with Session(client.app.state.engine) as session:
        hall = house_file.upsert_room(session, "Hall", SQUARE, 2500)
        house_file.record_piece(session, "hall-bench", "Hall bench", room_id=hall.id)
        if composition_status:
            composition = house_file.record_composition(session, "room", "Hall")
            house_file.record_composition_version(session, composition, 1, None, [])
            folder = storage.composition_version_dir(client.app.state.settings.render_root, composition.slug, 1)
            folder.mkdir(parents=True)
            storage.write_status(folder, status=composition_status)
        session.commit()


@pytest.mark.parametrize(("method", "path"), [("GET", "/rooms"), ("DELETE", "/rooms/Hall")])
def test_both_routes_need_the_owner_cookie(client: TestClient, method: str, path: str) -> None:
    assert TestClient(client.app).request(method, path).status_code == 401


def test_a_room_is_listed_and_deleted_and_its_piece_is_unassigned(client: TestClient) -> None:
    _hall(client, composition_status="succeeded")
    listed = client.get("/rooms").json()
    assert listed[0]["name"] == "Hall" and listed[0]["composition"] == {"slug": "hall", "versions": [1]}
    assert listed[0]["pieces"] == [{"package_id": "hall-bench", "name": "Hall bench"}]

    response = client.delete("/rooms/Hall")
    assert response.status_code == 204
    assert client.get("/rooms").json() == []
    assert client.get("/compositions").json() == []
    with Session(client.app.state.engine) as session:
        assert house_file.piece_room_name(session, "hall-bench") is None


def test_an_unknown_room_is_not_found(client: TestClient) -> None:
    assert client.delete("/rooms/Attic").status_code == 404


def test_a_room_in_an_apartment_is_refused_with_the_reason(client: TestClient) -> None:
    with Session(client.app.state.engine) as session:
        house_file.upsert_apartment(
            session, "Wohnung", 2600, 100, [{"name": "Küche", "corners_mm": SQUARE, "height_mm": None, "openings": []}]
        )
        session.commit()
    response = client.delete("/rooms/Küche")
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "Küche belongs to the apartment Wohnung; it cannot be deleted on its own yet"
    assert [r["name"] for r in client.get("/rooms").json()] == ["Küche"]


def test_a_room_whose_composition_is_building_is_refused(client: TestClient) -> None:
    _hall(client, composition_status="running")
    response = client.delete("/rooms/Hall")
    assert response.status_code == 409 and "building or rendering" in response.json()["detail"]["reason"]
    assert [r["name"] for r in client.get("/rooms").json()] == ["Hall"]
