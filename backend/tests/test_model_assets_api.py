"""model-assets: the owner-gated library routes, with a fake Blender check."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.blender import storage
from tests import model_fixtures as fx
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_failure_launch, fake_pipeline_launch
from tests.conftest import clean_house_file

SIZE = {"name": "armchair", "width_mm": "800", "depth_mm": "700", "height_mm": "900"}


@pytest.fixture
def upload_root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


def _client(migrated_database, render_root, fake_blender, upload_root, launch) -> TestClient:
    c = make_client(migrated_database, render_root, fake_blender, launch)
    c.app.state.settings.upload_root = upload_root
    clean_house_file(c.app.state.engine)
    return c


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, upload_root: Path) -> Iterator[TestClient]:
    c = _client(migrated_database, render_root, fake_blender, upload_root, fake_pipeline_launch())
    sign_in(c)
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def upload(client: TestClient, content: bytes, name: str = "armchair.glb", **form):
    return client.post("/models", data={**SIZE, **form}, files={"file": (name, content, "application/octet-stream")})


def test_a_glb_is_uploaded_checked_and_listed_ready(client: TestClient, upload_root: Path) -> None:
    response = upload(client, fx.glb())
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["kind"], body["state"], body["files"]) == ("glb", "checking", ["model.glb"])
    assert (body["width_mm"], body["depth_mm"], body["height_mm"]) == (800, 700, 900)
    listed = client.get("/models").json()
    assert [(m["model_id"], m["state"]) for m in listed] == [(body["model_id"], "ready")]
    ready = client.get(f"/models/{body['model_id']}").json()
    assert ready["triangles"] == 12 and ready["measured_mm"] == {"x": 900.0, "y": 800.0, "z": 1000.0}


def test_a_crashing_check_leaves_the_model_refused(
    migrated_database: str, render_root: Path, fake_blender: Path, upload_root: Path
) -> None:
    c = _client(migrated_database, render_root, fake_blender, upload_root, fake_failure_launch)
    sign_in(c)
    try:
        model_id = upload(c, fx.glb()).json()["model_id"]
        model = c.get(f"/models/{model_id}").json()
        assert model["state"] == "refused" and "could not be imported" in model["reason"]
    finally:
        clean_house_file(c.app.state.engine)
        c.__exit__(None, None, None)


def test_a_model_over_the_triangle_limit_is_refused(client: TestClient) -> None:
    client.app.state.settings.model_max_triangles = 10
    model = client.get(f"/models/{upload(client, fx.glb()).json()['model_id']}").json()
    assert model["state"] == "refused" and model["reason"] == "the model has 12 triangles; at most 10 are allowed"


@pytest.mark.parametrize(
    ("content", "status", "failure_class"),
    [
        (b"BLENDER-v405" + b"\x00" * 64, 415, "unsupported_type"),
        (fx.gltf_zip("https://example.com/wood.png"), 415, "unsupported_type"),
    ],
    ids=["blend", "remote-uri"],
)
def test_refusals_carry_their_status_and_store_nothing(
    client: TestClient, upload_root: Path, content: bytes, status: int, failure_class: str
) -> None:
    response = upload(client, content)
    assert response.status_code == status
    assert response.json()["detail"]["failure_class"] == failure_class
    assert client.get("/models").json() == []


def test_an_oversized_model_is_413(client: TestClient) -> None:
    client.app.state.settings.model_max_bytes = 500
    response = upload(client, fx.glb())
    assert response.status_code == 413 and response.json()["detail"]["failure_class"] == "too_large"
    assert client.get("/models").json() == []


def test_a_size_outside_the_range_is_refused_naming_the_field(client: TestClient) -> None:
    response = upload(client, fx.glb(), height_mm="0")
    assert response.status_code == 422 and response.json()["detail"]["field"] == "height_mm"


def test_files_are_served_by_exact_name_with_a_fixed_type(client: TestClient) -> None:
    model_id = upload(client, fx.obj_zip(), "box.zip").json()["model_id"]
    served = client.get(f"/models/{model_id}/files/box.obj")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("text/plain")
    assert served.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/models/{model_id}/files/wood.png").headers["content-type"] == "image/png"
    for name in ("check.json", "../box.obj", "missing.png", "BOX.OBJ"):
        assert client.get(f"/models/{model_id}/files/{name}").status_code == 404, name


def test_delete_removes_the_model_and_its_files(client: TestClient, upload_root: Path) -> None:
    model_id = upload(client, fx.glb()).json()["model_id"]
    assert client.delete(f"/models/{model_id}").status_code == 204
    assert client.get(f"/models/{model_id}").status_code == 404
    assert not (upload_root / "models" / model_id).exists()


def test_a_model_placed_in_a_composition_cannot_be_deleted(client: TestClient, render_root: Path) -> None:
    model_id = upload(client, fx.glb()).json()["model_id"]
    folder = storage.composition_version_dir(render_root, "wohnen", 2)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps({
        "kind": "room_composition", "scope": {"room": "Wohnen"},
        "items": [{"id": "armchair", "type": "model", "model_id": model_id}],
    }), encoding="utf-8")
    response = client.delete(f"/models/{model_id}")
    assert response.status_code == 409
    assert response.json()["detail"]["failure_class"] == "in_use"
    assert "Wohnen v2" in response.json()["detail"]["reason"]
    assert client.get(f"/models/{model_id}").status_code == 200


def test_every_model_route_needs_the_owner(
    migrated_database: str, render_root: Path, fake_blender: Path, upload_root: Path
) -> None:
    c = _client(migrated_database, render_root, fake_blender, upload_root, fake_pipeline_launch())
    try:
        some = "00000000-0000-0000-0000-000000000000"
        for method, path in (("post", "/models"), ("get", "/models"), ("get", f"/models/{some}"),
                             ("get", f"/models/{some}/files/model.glb"), ("delete", f"/models/{some}")):
            assert getattr(c, method)(path).status_code == 401, path
    finally:
        c.__exit__(None, None, None)
