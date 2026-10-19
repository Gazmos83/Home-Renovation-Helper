"""rooms-page: the measured rooms are listed with their details and deleted after a warning."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent import house_file
from app.blender import storage
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_success_launch, write_composition_files
from tests.conftest import clean_house_file, wait_for_status

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


# --- duplicate-room ----------------------------------------------------------------------

BENCH = {"id": "bench", "type": "stand-in", "name": "Bench", "width_mm": 1200, "depth_mm": 400, "height_mm": 450,
         "colour": "#a08060", "placement": {"wall": 0, "offset_mm": 500}}


def _hall_layout(client: TestClient, items: list[dict]) -> None:
    """Hall with layout version 1 holding `items`, written as a built version would be."""
    root = client.app.state.settings.render_root
    with Session(client.app.state.engine) as session:
        house_file.upsert_room(session, "Hall", SQUARE, 2500)
        composition = house_file.record_composition(session, "room", "Hall")
        house_file.record_composition_version(session, composition, 1, None, [])
        session.commit()
    folder = storage.composition_version_dir(root, "hall", 1)
    folder.mkdir(parents=True)
    document = {"kind": "room_composition", "schema_version": 1, "units": "mm", "scope": {"room": "Hall"}, "items": items}
    (folder / storage.INPUT_FILE).write_text(json.dumps(document), encoding="utf-8")
    storage.write_status(folder, status="succeeded")


def test_a_room_is_duplicated_with_its_layout_and_the_copy_builds(client: TestClient) -> None:
    client.app.state.blender_launch = fake_success_launch(lambda out, _argv: write_composition_files(out))
    _hall_layout(client, [BENCH])
    response = client.post("/rooms/Hall/duplicate", json={"name": "Hall (copy)", "version": 1})
    assert response.status_code == 201, response.text
    assert response.json() == {"room": "Hall (copy)", "composition": {"slug": "hall-copy", "version": 1}}
    listed = {r["name"]: r for r in client.get("/rooms").json()}
    assert listed["Hall (copy)"]["composition"] == {"slug": "hall-copy", "versions": [1]}
    assert listed["Hall"]["composition"] == {"slug": "hall", "versions": [1]}
    folder = storage.composition_version_dir(client.app.state.settings.render_root, "hall-copy", 1)
    wait_for_status(folder)


def test_a_room_is_duplicated_without_a_layout(client: TestClient) -> None:
    _hall_layout(client, [BENCH])
    response = client.post("/rooms/Hall/duplicate", json={"name": "Hall B"})
    assert response.status_code == 201
    assert response.json() == {"room": "Hall B", "composition": None}


@pytest.mark.parametrize(
    ("source", "body", "code", "failure"),
    [
        ("Nowhere", {"name": "B"}, 404, None),
        ("Hall", {"name": "HALL"}, 409, "name_taken"),
        ("Hall", {"name": "  "}, 422, "invalid_name"),
        ("Hall", {"name": "Hall B", "version": 1}, 409, "layout_refused"),
    ],
)
def test_a_refused_duplicate_answers_and_writes_nothing(client: TestClient, source, body, code, failure) -> None:
    # The layout holds a piece version that is not approved.
    _hall_layout(client, [{"id": "ghost", "type": "piece", "package_id": "ghost", "version": 1,
                           "placement": {"wall": 0, "offset_mm": 500}}])
    response = client.post(f"/rooms/{source}/duplicate", json=body)
    assert response.status_code == code
    if failure:
        assert response.json()["detail"]["failure_class"] == failure
    assert [r["name"] for r in client.get("/rooms").json()] == ["Hall"]
