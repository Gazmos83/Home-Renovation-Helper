"""furniture-packages: the owner-gated routes, with a fake launcher."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.blender import storage
from tests.api_helpers import create, desk, make_client, sign_in
from tests.blender_fakes import (
    BUILD_FILES,
    fake_failure_launch,
    fake_success_launch,
)


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    sign_in(c)
    yield c
    c.__exit__(None, None, None)


# --- create ---------------------------------------------------------------------------------


def test_create_makes_v1_and_the_build_publishes_the_files(client: TestClient, render_root: Path) -> None:
    response = create(client)
    assert response.status_code == 202
    assert response.json() == {"package_id": "hall-bench", "version": 1, "status": "queued"}
    folder = render_root / "hall-bench" / "v1"
    assert (folder / storage.INPUT_FILE).is_file()
    body = client.get("/packages/hall-bench/versions/1").json()
    assert body["status"] == "succeeded" and body["error"] is None
    assert set(storage.BUILD_FILES) <= set(body["files"])


def test_the_stored_input_is_the_validated_document(client: TestClient, render_root: Path) -> None:
    create(client)
    stored = json.loads((render_root / "hall-bench" / "v1" / storage.INPUT_FILE).read_text())
    assert stored["kind"] == "custom_build" and stored["units"] == "mm"


@pytest.mark.parametrize("bad", ["a/b", "..", "Hall", "", "x" * 65, "benchmark"])
def test_an_invalid_package_id_is_refused_and_writes_nothing(
    client: TestClient, render_root: Path, bad: str
) -> None:
    response = create(client, bad)
    assert response.status_code == 422 and response.json()["detail"]["failure_class"] == "invalid_package_id"
    assert list(render_root.iterdir()) == []


def test_a_duplicate_package_id_is_refused_pointing_at_editing(client: TestClient) -> None:
    create(client)
    response = create(client)
    assert response.status_code == 409
    assert "edit" in response.json()["detail"]["reason"]


def test_an_unknown_spec_field_is_refused_by_name_and_creates_nothing(
    client: TestClient, render_root: Path
) -> None:
    spec = desk()
    spec["modules"][0]["bevel_mm"] = 3
    response = create(client, spec=spec)
    assert response.status_code == 422
    assert "bevel_mm" in response.json()["detail"]["reason"]
    assert list(render_root.iterdir()) == []


def test_an_out_of_range_dimension_is_refused_naming_the_field(client: TestClient) -> None:
    spec = desk()
    spec["modules"][0]["width"] = 99_999
    response = create(client, spec=spec)
    assert response.status_code == 422 and "modules.0.width" in response.json()["detail"]["reason"]


def test_a_failed_build_is_recorded_without_a_path(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_failure_launch)
    sign_in(c)
    create(c)
    body = c.get("/packages/hall-bench/versions/1").json()
    assert body["status"] == "failed" and "boom" in body["error"]
    assert str(render_root) not in body["error"]
    assert not any(name in body["files"] for name in storage.BUILD_FILES)
    c.__exit__(None, None, None)


# --- edit -> new version ----------------------------------------------------------------------


def test_editing_the_spec_makes_v2_and_leaves_v1_untouched(client: TestClient, render_root: Path) -> None:
    create(client)
    before = sorted(p.name for p in (render_root / "hall-bench" / "v1").iterdir())
    edited = desk()
    edited["name"] = "Hall bench, wider"
    response = client.put("/packages/hall-bench/spec", json={"spec": edited})
    assert response.status_code == 202 and response.json()["version"] == 2
    assert (render_root / "hall-bench" / "v2").is_dir()
    assert sorted(p.name for p in (render_root / "hall-bench" / "v1").iterdir()) == before
    assert client.get("/packages/hall-bench/versions/2").json()["status"] == "succeeded"


def test_an_invalid_edit_creates_no_version(client: TestClient, render_root: Path) -> None:
    create(client)
    bad = desk()
    bad["modules"][0]["nonsense"] = 1
    response = client.put("/packages/hall-bench/spec", json={"spec": bad})
    assert response.status_code == 422 and "nonsense" in response.json()["detail"]["reason"]
    assert not (render_root / "hall-bench" / "v2").exists()


def test_editing_an_unknown_package_is_not_found(client: TestClient) -> None:
    assert client.put("/packages/nope/spec", json={"spec": desk()}).status_code == 404


# --- listing and reading ----------------------------------------------------------------------


def test_listing_names_each_package_with_versions_newest_first(client: TestClient) -> None:
    create(client, "a-bench")
    client.put("/packages/a-bench/spec", json={"spec": desk()})
    create(client, "b-desk")
    assert client.get("/packages").json() == [
        {"package_id": "a-bench", "versions": [2, 1]},
        {"package_id": "b-desk", "versions": [1]},
    ]


def test_reading_a_package_lists_versions_newest_first(client: TestClient) -> None:
    create(client)
    client.put("/packages/hall-bench/spec", json={"spec": desk()})
    versions = client.get("/packages/hall-bench").json()["versions"]
    assert [v["version"] for v in versions] == [2, 1]


def test_reading_a_version_reports_files_and_renders(client: TestClient, render_root: Path) -> None:
    create(client)
    frames = render_root / "hall-bench" / "v1" / "frames"
    frames.mkdir()
    for i in range(12):
        (frames / f"frame_{i:03d}.png").write_bytes(b"x")
    body = client.get("/packages/hall-bench/versions/1").json()
    assert body["renders"] == {
        "still": False, "turntable_frames": 12, "room_still": False, "room_turntable_frames": 0,
        "detail_still": False, "detail_turntable_frames": 0,
    }


@pytest.mark.parametrize("path", ["/packages/nope", "/packages/hall-bench/versions/9", "/packages/Bad..Id"])
def test_unknown_things_are_not_found(client: TestClient, path: str) -> None:
    create(client)
    assert client.get(path).status_code == 404


# --- files ----------------------------------------------------------------------------------


def test_the_model_is_served_with_its_media_type(client: TestClient) -> None:
    create(client)
    response = client.get("/packages/hall-bench/versions/1/files/model.glb")
    assert response.status_code == 200 and response.headers["content-type"] == "model/gltf-binary"
    assert response.content[:4] == b"glTF"


@pytest.mark.parametrize("name", list(BUILD_FILES))
def test_every_build_file_is_served(client: TestClient, name: str) -> None:
    create(client)
    assert client.get(f"/packages/hall-bench/versions/1/files/{name}").status_code == 200


def test_frames_and_room_files_are_served_by_exact_name(client: TestClient, render_root: Path) -> None:
    create(client)
    folder = render_root / "hall-bench" / "v1"
    (folder / "frames").mkdir()
    (folder / "frames" / "frame_003.png").write_bytes(b"png")
    (folder / "room" / "frames").mkdir(parents=True)
    (folder / "room" / "frames" / "frame_000.png").write_bytes(b"png")
    (folder / "room" / "still.png").write_bytes(b"png")
    base = "/packages/hall-bench/versions/1/files"
    assert client.get(f"{base}/frames/3").status_code == 200
    assert client.get(f"{base}/frames/4").status_code == 404
    assert client.get(f"{base}/room/frames/0").status_code == 200
    assert client.get(f"{base}/room/still.png").status_code == 200


def test_the_detail_outputs_are_served_but_not_the_detail_file_or_log(
    client: TestClient, render_root: Path
) -> None:
    create(client)
    detail = render_root / "hall-bench" / "v1" / "detail"
    (detail / "screens").mkdir(parents=True)
    (detail / "frames").mkdir()
    (detail / "screens" / "screen_000.png").write_bytes(b"png")
    (detail / "frames" / "frame_035.png").write_bytes(b"png")
    for name in ("still.png", "viewer.html", "scene.json"):
        (detail / name).write_bytes(b"x")
    (detail / "detail.blend").write_bytes(b"BLENDER")
    (detail / "log.jsonl").write_text("{}", encoding="utf-8")
    base = "/packages/hall-bench/versions/1/files"
    screen = client.get(f"{base}/detail/screens/0")
    assert screen.status_code == 200 and screen.headers["content-type"] == "image/png"
    assert client.get(f"{base}/detail/screens/1").status_code == 404
    assert client.get(f"{base}/detail/frames/35").status_code == 200
    for name, media in (("still.png", "image/png"), ("viewer.html", "text/html"), ("scene.json", "application/json")):
        response = client.get(f"{base}/detail/{name}")
        assert response.status_code == 200 and response.headers["content-type"].startswith(media)
    for name in ("detail.blend", "log.jsonl", "detail/detail.blend", "detail/log.jsonl", "detail/spec.json",
                 "detail/screens/..%2Fdetail.blend", "detail/screens/x"):
        assert client.get(f"{base}/{name}" if name.startswith("detail/") else f"{base}/detail/{name}").status_code == 404


@pytest.mark.parametrize(
    "name",
    ["../v1/spec.json", "spec.JSON", "input.json", "frames/..%2Fspec.json", "frames/x", "spec.json/",
     "room/spec.json", "..%2Fspec.json", "%2e%2e/spec.json", ".status.json.tmp", "nope.txt"],
)
def test_anything_outside_the_closed_set_is_not_found(client: TestClient, name: str) -> None:
    create(client)
    assert client.get(f"/packages/hall-bench/versions/1/files/{name}").status_code == 404


def test_a_symlink_leading_outside_the_root_is_not_served(
    client: TestClient, render_root: Path, tmp_path: Path
) -> None:
    create(client)
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"secret")
    folder = render_root / "hall-bench" / "v1"
    (folder / "still.png").symlink_to(secret)
    assert client.get("/packages/hall-bench/versions/1/files/still.png").status_code == 404


# --- gate and availability ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/packages"), ("GET", "/packages/x"), ("POST", "/packages"),
     ("GET", "/packages/x/versions/1/files/spec.json"), ("PUT", "/packages/x/spec")],
)
def test_every_route_needs_the_owner_cookie(
    migrated_database: str, render_root: Path, fake_blender: Path, method: str, path: str
) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    response = c.request(method, path, json={"package_id": "x", "spec": {}})
    assert response.status_code == 401
    c.__exit__(None, None, None)


def test_a_missing_binary_refuses_builds_but_listing_and_files_still_work(
    migrated_database: str, render_root: Path, fake_blender: Path, tmp_path: Path
) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_success_launch())
    sign_in(c)
    create(c)
    c.app.state.settings = c.app.state.settings.model_copy(update={"blender_bin": tmp_path / "gone"})

    refused = create(c, "second")
    assert refused.status_code == 503
    detail = refused.json()["detail"]
    assert detail["failure_class"] == "blender_unavailable" and "Blender" in detail["reason"]
    assert not (render_root / "second").exists()
    assert c.put("/packages/hall-bench/spec", json={"spec": desk()}).status_code == 503

    assert c.get("/packages").status_code == 200
    assert c.get("/packages/hall-bench/versions/1/files/spec.json").status_code == 200
    c.__exit__(None, None, None)
    shutil.rmtree(render_root, ignore_errors=True)
