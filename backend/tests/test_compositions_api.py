"""room-composition: the Rooms page's routes — compositions listed with approval, files by exact name."""

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
from tests.blender_fakes import fake_pipeline_launch, png_bytes
from tests.conftest import clean_house_file


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    clean_house_file(c.app.state.engine)
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def seed(client: TestClient, render_root: Path, *, approved: bool) -> Path:
    with Session(client.app.state.engine) as session:
        house_file.record_piece(session, "wall", "Wall")
        house_file.record_version(session, "wall", 4)
        if approved:
            house_file.approve_version(session, "wall", 4)
        composition = house_file.record_composition(session, "room", "Wohnen")
        house_file.record_composition_version(session, composition, 1, None, [])
        session.commit()
    folder = storage.composition_version_dir(render_root, "wohnen", 1)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps({
        "kind": "room_composition", "scope": {"room": "Wohnen"},
        "items": [{"id": "wall", "type": "piece", "package_id": "wall", "version": 4},
                  {"id": "sofa", "type": "stand-in", "name": "Sofa"}],
    }), encoding="utf-8")
    (folder / "screenshot.png").write_bytes(png_bytes(800, 500))
    (folder / "report.json").write_text("{}", encoding="utf-8")
    storage.write_status(folder, status="succeeded")
    return folder


def test_compositions_list_their_items_approval_and_picture(client: TestClient, render_root: Path) -> None:
    sign_in(client)
    seed(client, render_root, approved=False)
    [listed] = client.get("/compositions").json()
    assert (listed["name"], listed["latest_version"], listed["status"]) == ("Wohnen", 1, "succeeded")
    assert listed["picture"] == "/compositions/wohnen/versions/1/files/screenshot.png"
    assert listed["viewer"] is None
    wall, sofa = listed["items"]
    assert wall["name"] == "wall v4" and wall["no_longer_approved"] is True
    assert sofa == {"id": "sofa", "type": "stand-in", "name": "Sofa"}
    text = json.dumps(listed).lower()
    for word in ("deepseek", "gpt-", "token", "cost", "/home/"):
        assert word not in text


def test_version_files_are_served_by_exact_name_only(client: TestClient, render_root: Path) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    base = "/compositions/wohnen/versions/1/files"
    shot = client.get(f"{base}/screenshot.png")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"
    assert client.get(f"{base}/report.json").status_code == 200
    for name in ("input.json", "../../wall/v4/model.glb", "nothing.png"):
        assert client.get(f"{base}/{name}").status_code == 404, name
    assert client.get("/compositions/wohnen/versions/9/files/screenshot.png").status_code == 404


def test_the_routes_need_the_owner(client: TestClient) -> None:
    assert client.get("/compositions").status_code == 401
    assert client.get("/compositions/wohnen/versions/1/files/screenshot.png").status_code == 401


def test_the_latest_version_with_a_model_offers_it_and_its_surface_map(client: TestClient, render_root: Path) -> None:
    from tests.blender_fakes import COMPOSITION_SURFACES, glb_bytes

    sign_in(client)
    folder = seed(client, render_root, approved=True)
    [older] = client.get("/compositions").json()
    assert older["model"] is None and older["surfaces"] is None

    (folder / "model.glb").write_bytes(glb_bytes(["Floor"]))
    (folder / "report.json").write_text(json.dumps({"surfaces": COMPOSITION_SURFACES}), encoding="utf-8")
    [listed] = client.get("/compositions").json()
    assert listed["model"] == "/compositions/wohnen/versions/1/files/model.glb"
    assert listed["surfaces"] == "/compositions/wohnen/versions/1/files/report.json"
    model = client.get(listed["model"])
    assert model.status_code == 200 and model.headers["content-type"] == "model/gltf-binary"
    assert client.get(listed["surfaces"]).json()["surfaces"] == COMPOSITION_SURFACES
