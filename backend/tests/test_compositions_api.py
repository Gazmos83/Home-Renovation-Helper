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


def test_the_newest_five_versions_are_offered_for_the_dropdown(client: TestClient, render_root: Path) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    with Session(client.app.state.engine) as session:
        composition = house_file.composition_by_scope(session, "room", "Wohnen")
        for number in range(2, 8):
            house_file.record_composition_version(session, composition, number, number - 1, [])
            folder = storage.composition_version_dir(render_root, "wohnen", number)
            folder.mkdir(parents=True)
            storage.write_status(folder, status="succeeded")
            if number == 7:
                (folder / "model.glb").write_bytes(b"glb")
        session.commit()
    [listed] = client.get("/compositions").json()
    assert [v["version"] for v in listed["version_views"]] == [7, 6, 5, 4, 3]
    assert listed["versions"] == [1, 2, 3, 4, 5, 6, 7]
    newest = listed["version_views"][0]
    assert newest["model"] == listed["model"] == "/compositions/wohnen/versions/7/files/model.glb"
    assert newest["dimensions"] == "/compositions/wohnen/versions/7/dimensions"
    assert listed["version_views"][1]["model"] is None


# --- room dimensions (project-room-inspection) ---------------------------------------------

WOHNEN_PLAN = [[0.0, 0.0], [6200.0, 0.0], [6200.0, 5700.0], [3500.0, 5700.0], [1289.0, 6064.0]]


def test_a_room_versions_walls_and_ceiling_are_read_from_its_document(client: TestClient, render_root: Path) -> None:
    sign_in(client)
    folder = seed(client, render_root, approved=True)
    document = json.loads((folder / storage.INPUT_FILE).read_text(encoding="utf-8"))
    document["resolved"] = {
        "rooms": [{"name": "Wohnen", "corners": WOHNEN_PLAN, "height_mm": 2500.0, "wall_thickness_mm": 100.0, "openings": []}],
        "items": [],
    }
    (folder / storage.INPUT_FILE).write_text(json.dumps(document), encoding="utf-8")
    body = client.get("/compositions/wohnen/versions/1/dimensions").json()
    assert [(w["label"], w["length_mm"]) for w in body["walls"]] == [
        ("wall 1", 6200), ("wall 2", 5700), ("wall 3", 2700), ("wall 4", 2241), ("wall 5", 6199),
    ]
    assert body["walls"][0]["from"] == [0.0, 0.0] and body["walls"][0]["to"] == [6200.0, 0.0]
    [ceiling] = body["ceilings"]
    assert (ceiling["room"], ceiling["height_mm"]) == ("Wohnen", 2500)
    assert str(render_root) not in json.dumps(body)


def test_an_apartment_lists_a_shared_wall_once_and_each_rooms_height() -> None:
    from app.compositions import room_dimensions

    shell = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "packages" / "apartment-two-room.json").read_text())
    shell["rooms"][1]["height_mm"] = 2400
    found = room_dimensions({"scope": {"apartment": "Example one-bed"}, "resolved": {"shell": shell, "items": []}})
    assert found is not None
    lengths = [(w["label"], w["length_mm"]) for w in found["walls"]]
    assert len(lengths) == 7  # eight room edges, the shared one once
    assert ("Living room: wall 2", 3800) in lengths
    assert {(c["room"], c["height_mm"]) for c in found["ceilings"]} == {("Living room", 2550), ("Bedroom", 2400)}


def test_dimensions_of_an_unknown_or_unreadable_version_are_not_found(client: TestClient, render_root: Path) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)  # its document has no resolved room plan
    assert client.get("/compositions/wohnen/versions/1/dimensions").status_code == 404
    assert client.get("/compositions/wohnen/versions/9/dimensions").status_code == 404
    assert client.get("/compositions/Bad/versions/1/dimensions").status_code == 404
    assert TestClient(client.app).get("/compositions/wohnen/versions/1/dimensions").status_code == 401


# --- room-version-approval -------------------------------------------------------------------


def _add_version(client: TestClient, render_root: Path, number: int) -> Path:
    with Session(client.app.state.engine) as session:
        composition = house_file.composition_by_slug(session, "wohnen")
        house_file.record_composition_version(session, composition, number, number - 1, [])
        session.commit()
    folder = storage.composition_version_dir(render_root, "wohnen", number)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(
        (storage.composition_version_dir(render_root, "wohnen", 1) / storage.INPUT_FILE).read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    storage.write_status(folder, status="succeeded")
    return folder


def test_a_built_composition_version_is_approved_and_read_back(client: TestClient, render_root: Path) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    response = client.put("/compositions/wohnen/versions/1/approval")
    assert response.status_code == 200
    approved_at = response.json()["approved_at"]
    assert approved_at
    [listed] = client.get("/compositions").json()
    assert listed["approved_version"] == 1
    assert listed["version_views"][0]["approved_at"] == approved_at


def test_unapproving_a_composition_version_clears_the_approval(
    client: TestClient, render_root: Path
) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    client.put("/compositions/wohnen/versions/1/approval")
    for _ in range(2):
        response = client.delete("/compositions/wohnen/versions/1/approval")
        assert response.status_code == 200 and response.json()["approved_at"] is None
    [listed] = client.get("/compositions").json()
    assert listed["approved_version"] is None


def test_a_composition_version_still_building_cannot_be_approved(
    client: TestClient, render_root: Path
) -> None:
    sign_in(client)
    folder = seed(client, render_root, approved=True)
    storage.write_status(folder, status="running")
    response = client.put("/compositions/wohnen/versions/1/approval")
    assert response.status_code == 409
    assert response.json()["detail"]["failure_class"] == "not_built"
    [listed] = client.get("/compositions").json()
    assert listed["approved_version"] is None


def test_approving_a_version_that_places_an_unapproved_piece_is_refused(
    client: TestClient, render_root: Path
) -> None:
    sign_in(client)
    seed(client, render_root, approved=False)
    response = client.put("/compositions/wohnen/versions/1/approval")
    assert response.status_code == 409
    assert response.json()["detail"]["failure_class"] == "unapproved_pieces"
    assert "wall v4" in response.json()["detail"]["reason"]


def test_approving_an_unknown_composition_version_is_not_found(client: TestClient, render_root: Path) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    assert client.put("/compositions/wohnen/versions/9/approval").status_code == 404
    assert client.put("/compositions/nothing/versions/1/approval").status_code == 404
    assert client.delete("/compositions/wohnen/versions/9/approval").status_code == 404


def test_composition_approval_routes_need_the_owner(client: TestClient, render_root: Path) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    unsigned = TestClient(client.app)
    assert unsigned.put("/compositions/wohnen/versions/1/approval").status_code == 401
    assert unsigned.delete("/compositions/wohnen/versions/1/approval").status_code == 401
    assert unsigned.delete("/compositions/wohnen/versions/1").status_code == 401


def test_deleting_an_older_composition_version_leaves_the_rest(
    client: TestClient, render_root: Path
) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    _add_version(client, render_root, 2)
    assert client.delete("/compositions/wohnen/versions/1").status_code == 204
    assert not (render_root / "rooms" / "wohnen" / "v1").exists()
    [listed] = client.get("/compositions").json()
    assert listed["versions"] == [2] and listed["latest_version"] == 2


def test_deleting_an_approved_composition_version_is_refused(
    client: TestClient, render_root: Path
) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    client.put("/compositions/wohnen/versions/1/approval")
    response = client.delete("/compositions/wohnen/versions/1")
    assert response.status_code == 409
    assert "unapprove version 1 first" in response.json()["detail"]["reason"]
    assert client.get("/compositions").json()[0]["latest_version"] == 1


def test_deleting_the_last_composition_version_drops_the_composition(
    client: TestClient, render_root: Path
) -> None:
    sign_in(client)
    seed(client, render_root, approved=True)
    assert client.delete("/compositions/wohnen/versions/1").status_code == 204
    assert client.get("/compositions").json() == []
    assert not (render_root / "rooms" / "wohnen").exists()
