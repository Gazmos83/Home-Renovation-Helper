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
from tests.conftest import clean_house_file


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


def test_a_sixteenth_version_is_refused_and_writes_no_folder(client: TestClient, render_root: Path) -> None:
    create(client)
    for number in range(2, 16):
        storage.version_dir(render_root, "hall-bench", number).mkdir()
    response = client.put("/packages/hall-bench/spec", json={"spec": desk()})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["failure_class"] == "version_limit"
    assert "15 versions" in detail["reason"] and "Pieces page" in detail["reason"]
    assert not (render_root / "hall-bench" / "v16").exists()


def test_editing_an_unknown_package_is_not_found(client: TestClient) -> None:
    assert client.put("/packages/nope/spec", json={"spec": desk()}).status_code == 404


# --- listing and reading ----------------------------------------------------------------------


def test_listing_names_each_package_with_versions_newest_first(client: TestClient) -> None:
    create(client, "a-bench")
    client.put("/packages/a-bench/spec", json={"spec": desk()})
    create(client, "b-desk")
    assert client.get("/packages").json() == [
        {"package_id": "a-bench", "versions": [2, 1], "room": None},
        {"package_id": "b-desk", "versions": [1], "room": None},
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


def test_a_version_built_before_the_views_answers_not_found_for_them(
    client: TestClient, render_root: Path
) -> None:
    create(client)
    folder = render_root / "hall-bench" / "v1"
    for name in ("front.png", "side.png", "top.png"):
        (folder / name).unlink()
    base = "/packages/hall-bench/versions/1/files"
    assert client.get(f"{base}/screenshot.png").status_code == 200
    for name in ("front.png", "side.png", "top.png"):
        assert client.get(f"{base}/{name}").status_code == 404


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


def test_frames_are_also_served_by_the_file_names_the_viewer_loads(client: TestClient, render_root: Path) -> None:
    create(client)
    folder = render_root / "hall-bench" / "v1"
    (folder / "frames").mkdir()
    (folder / "frames" / "frame_003.png").write_bytes(b"png")
    (folder / "room" / "frames").mkdir(parents=True)
    (folder / "room" / "frames" / "frame_000.png").write_bytes(b"png")
    (folder / "detail" / "frames").mkdir(parents=True)
    (folder / "detail" / "frames" / "frame_001.png").write_bytes(b"png")
    base = "/packages/hall-bench/versions/1/files"
    assert client.get(f"{base}/frames/frame_003.png").status_code == 200
    assert client.get(f"{base}/room/frames/frame_000.png").status_code == 200
    assert client.get(f"{base}/detail/frames/frame_001.png").status_code == 200
    for name in ("frames/frame_004.png", "frames/frame_3.png", "frames/frame_003.jpg", "frames/frame_../x.png"):
        assert client.get(f"{base}/{name}").status_code == 404


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
     ("GET", "/packages/x/versions/1/files/spec.json"), ("PUT", "/packages/x/spec"),
     ("PUT", "/packages/x/versions/1/approval"), ("DELETE", "/packages/x/versions/1/approval"),
     ("DELETE", "/packages/x/versions/1"),
     ("GET", "/packages/x/versions/1/design"), ("GET", "/packages/x/versions/1/bundle"),
     ("PUT", "/packages/x/room"), ("GET", "/rooms"), ("DELETE", "/rooms/x")],
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


# --- approval -------------------------------------------------------------------------------


@pytest.fixture
def record(client: TestClient) -> Iterator:
    """Record a piece and its versions in the house file; the rows are removed afterwards."""
    from sqlalchemy.orm import Session

    from app.agent import house_file
    from app.db.models import Piece

    made: list[str] = []
    clean_house_file(client.app.state.engine)

    def _record(package_id: str = "hall-bench", versions: tuple[int, ...] = (1,)) -> None:
        with Session(client.app.state.engine) as session:
            house_file.record_piece(session, package_id, "Hall bench")
            for number in versions:
                house_file.record_version(session, package_id, number)
            session.commit()
        made.append(package_id)

    yield _record
    with Session(client.app.state.engine) as session:
        for package_id in made:
            piece = session.get(Piece, package_id)
            if piece is not None:
                session.delete(piece)
        session.commit()


def test_a_built_version_is_approved_and_read_back_approved(client: TestClient, record) -> None:
    create(client)
    record()
    response = client.put("/packages/hall-bench/versions/1/approval")
    assert response.status_code == 200
    approved_at = response.json()["approved_at"]
    assert approved_at
    assert client.get("/packages/hall-bench/versions/1").json()["approved_at"] == approved_at
    listed = client.get("/packages/hall-bench").json()["versions"]
    assert [v["approved_at"] is not None for v in listed] == [True]


def test_approving_another_version_moves_the_approval(client: TestClient, record) -> None:
    create(client)
    wider = desk()
    wider["modules"][0]["width"] = 1100
    assert client.put("/packages/hall-bench/spec", json={"spec": wider}).status_code == 202
    record(versions=(1, 2))
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    assert client.put("/packages/hall-bench/versions/2/approval").status_code == 200
    assert client.get("/packages/hall-bench/versions/1").json()["approved_at"] is None
    assert client.get("/packages/hall-bench/versions/2").json()["approved_at"] is not None


def test_unapproving_clears_the_approval_and_repeats_quietly(client: TestClient, record) -> None:
    create(client)
    record()
    client.put("/packages/hall-bench/versions/1/approval")
    for _ in range(2):
        response = client.delete("/packages/hall-bench/versions/1/approval")
        assert response.status_code == 200 and response.json()["approved_at"] is None
    assert client.get("/packages/hall-bench/versions/1").json()["approved_at"] is None


def test_a_version_still_building_cannot_be_approved(
    client: TestClient, render_root: Path, record
) -> None:
    create(client)
    record()
    storage.write_status(render_root / "hall-bench" / "v1", status="running")
    response = client.put("/packages/hall-bench/versions/1/approval")
    assert response.status_code == 409
    assert response.json()["detail"]["failure_class"] == "not_built"
    assert client.get("/packages/hall-bench/versions/1").json()["approved_at"] is None


def test_a_folder_only_package_cannot_be_approved(client: TestClient) -> None:
    create(client)
    response = client.put("/packages/hall-bench/versions/1/approval")
    assert response.status_code == 409
    assert response.json()["detail"]["failure_class"] == "not_recorded"
    assert client.delete("/packages/hall-bench/versions/1/approval").status_code == 200


def test_approving_an_unknown_version_is_not_found(client: TestClient) -> None:
    create(client)
    assert client.put("/packages/hall-bench/versions/9/approval").status_code == 404
    assert client.put("/packages/nothing/versions/1/approval").status_code == 404
    assert client.delete("/packages/hall-bench/versions/9/approval").status_code == 404


def _place_in_wohnen(client: TestClient, render_root: Path, *, approve_room: bool) -> None:
    from sqlalchemy.orm import Session

    from app.agent import house_file

    with Session(client.app.state.engine) as session:
        composition = house_file.record_composition(session, "room", "Wohnen")
        house_file.record_composition_version(session, composition, 1, None, [])
        session.commit()
    folder = storage.composition_version_dir(render_root, "wohnen", 1)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(
        json.dumps({
            "kind": "room_composition",
            "scope": {"room": "Wohnen"},
            "items": [{"id": "bench", "type": "piece", "package_id": "hall-bench", "version": 1}],
        }),
        encoding="utf-8",
    )
    storage.write_status(folder, status="succeeded")
    if approve_room:
        assert client.put("/compositions/wohnen/versions/1/approval").status_code == 200


def test_unapproving_a_piece_placed_in_an_approved_room_is_refused(
    client: TestClient, record, render_root: Path
) -> None:
    create(client)
    record()
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    _place_in_wohnen(client, render_root, approve_room=True)
    response = client.delete("/packages/hall-bench/versions/1/approval")
    assert response.status_code == 409
    assert response.json()["detail"]["failure_class"] == "placed_in_approved_room"
    assert "Wohnen version 1" in response.json()["detail"]["reason"]
    assert client.get("/packages/hall-bench/versions/1").json()["approved_at"] is not None


def test_unapproving_a_piece_in_an_unapproved_room_clears(
    client: TestClient, record, render_root: Path
) -> None:
    create(client)
    record()
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    _place_in_wohnen(client, render_root, approve_room=False)
    response = client.delete("/packages/hall-bench/versions/1/approval")
    assert response.status_code == 200 and response.json()["approved_at"] is None


# --- deleting a version (version-cleanup-and-inspection) ---------------------------------------


def test_a_deleted_version_is_gone_and_the_next_edit_gets_a_new_number(client: TestClient, render_root: Path) -> None:
    create(client)
    assert client.put("/packages/hall-bench/spec", json={"spec": desk()}).json()["version"] == 2
    response = client.delete("/packages/hall-bench/versions/2")
    assert response.status_code == 204
    assert not (render_root / "hall-bench" / "v2").exists()
    assert [v["version"] for v in client.get("/packages/hall-bench").json()["versions"]] == [1]
    assert client.put("/packages/hall-bench/spec", json={"spec": desk()}).json()["version"] == 3


def test_deleting_an_approved_version_is_refused_with_the_reason(client: TestClient, record) -> None:
    create(client)
    record("hall-bench", (1,))
    client.put("/packages/hall-bench/versions/1/approval")
    response = client.delete("/packages/hall-bench/versions/1")
    assert response.status_code == 409
    assert "unapprove version 1 first" in response.json()["detail"]["reason"]
    assert client.get("/packages/hall-bench/versions/1").status_code == 200


def test_deleting_the_only_version_removes_the_package(client: TestClient, render_root: Path) -> None:
    create(client)
    assert client.delete("/packages/hall-bench/versions/1").status_code == 204
    assert not (render_root / "hall-bench").exists()
    assert client.get("/packages").json() == []


@pytest.mark.parametrize("path", ["/packages/hall-bench/versions/9", "/packages/Bad/versions/1", "/packages/hall-bench/versions/0"])
def test_deleting_an_unknown_version_is_not_found(client: TestClient, path: str) -> None:
    create(client)
    assert client.delete(path).status_code == 404


# --- export (design-import) -----------------------------------------------------------------


def test_the_design_downloads_as_an_import_document_that_re_imports_unchanged(
    client: TestClient, render_root: Path
) -> None:
    from app.design_import import parse_import

    create(client)
    response = client.get("/packages/hall-bench/versions/1/design")
    assert response.status_code == 200
    assert 'filename="hall-bench-v1.json"' in response.headers["content-disposition"]
    document = response.json()
    assert document["kind"] == "package_import" and "guide" not in document
    stored = json.loads((render_root / "hall-bench" / "v1" / storage.INPUT_FILE).read_text())
    assert parse_import(document) == (stored, "")


def _members(response) -> set[str]:
    import io
    import zipfile

    return set(zipfile.ZipFile(io.BytesIO(response.content)).namelist())


def test_the_bundle_holds_exactly_the_design_shop_files_model_and_pictures(
    client: TestClient, render_root: Path
) -> None:
    create(client)
    response = client.get("/packages/hall-bench/versions/1/bundle")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="hall-bench-v1.zip"' in response.headers["content-disposition"]
    expected = {"hall-bench-v1.json", "cutlist.csv", "hardware.csv", "model.glb", "screenshot.png"}
    assert _members(response) == expected

    (render_root / "hall-bench" / "v1" / "still.png").write_bytes(b"png")
    assert _members(client.get("/packages/hall-bench/versions/1/bundle")) == expected | {"still.png"}


def test_the_bundle_of_a_version_still_building_is_refused(client: TestClient, render_root: Path) -> None:
    create(client)
    storage.write_status(render_root / "hall-bench" / "v1", status="running")
    response = client.get("/packages/hall-bench/versions/1/bundle")
    assert response.status_code == 409
    assert response.json()["detail"]["failure_class"] == "not_built"
    assert client.get("/packages/hall-bench/versions/1/design").status_code == 200


def test_exports_of_an_unknown_version_are_not_found(client: TestClient) -> None:
    create(client)
    for kind in ("design", "bundle"):
        assert client.get(f"/packages/hall-bench/versions/9/{kind}").status_code == 404
        assert client.get(f"/packages/nothing/versions/1/{kind}").status_code == 404


# --- a piece's room (conversation-projects) -------------------------------------------------


@pytest.fixture
def rooms(client: TestClient) -> Iterator[None]:
    from sqlalchemy.orm import Session

    from app.agent import house_file

    clean_house_file(client.app.state.engine)
    with Session(client.app.state.engine) as session:
        square = [[0, 0], [3000, 0], [3000, 2000], [0, 2000]]
        house_file.upsert_room(session, "Schlafzimmer", square, 2500)
        house_file.upsert_room(session, "Hall", square, 2500)
        session.commit()
    yield
    clean_house_file(client.app.state.engine)


def test_the_room_names_are_listed(client: TestClient, rooms) -> None:
    assert [room["name"] for room in client.get("/rooms").json()] == ["Hall", "Schlafzimmer"]


def test_an_unassigned_piece_is_attached_to_a_room_and_the_list_names_it(client: TestClient, rooms) -> None:
    create(client, "murphy-bed")
    assert client.get("/packages").json()[0]["room"] is None

    response = client.put("/packages/murphy-bed/room", json={"room": "Schlafzimmer"})
    assert response.status_code == 200
    assert response.json() == {"package_id": "murphy-bed", "room": "Schlafzimmer"}
    assert client.get("/packages").json()[0]["room"] == "Schlafzimmer"

    assert client.put("/packages/murphy-bed/room", json={"room": None}).json()["room"] is None
    assert client.get("/packages").json()[0]["room"] is None


def test_an_unknown_room_is_refused_naming_it_and_the_piece_is_unchanged(client: TestClient, rooms) -> None:
    create(client, "murphy-bed")
    client.put("/packages/murphy-bed/room", json={"room": "Hall"})
    response = client.put("/packages/murphy-bed/room", json={"room": "Attic"})
    assert response.status_code == 422
    assert "Attic" in response.json()["detail"]["reason"]
    assert client.get("/packages").json()[0]["room"] == "Hall"


def test_an_unknown_piece_is_not_found(client: TestClient, rooms) -> None:
    assert client.put("/packages/nope/room", json={"room": "Hall"}).status_code == 404


def test_setting_a_piece_room_leaves_every_conversations_room_alone(client: TestClient, rooms) -> None:
    from sqlalchemy.orm import Session

    from app.agent import house_file

    create(client, "murphy-bed")
    with Session(client.app.state.engine) as session:
        thread = house_file.create_thread(session, "Bedroom")
        house_file.set_thread_room(session, thread.id, house_file.room_by_name(session, "Hall"))
        session.commit()
        thread_id = thread.id
    client.put("/packages/murphy-bed/room", json={"room": "Schlafzimmer"})
    with Session(client.app.state.engine) as session:
        room, _ = house_file.thread_scope(session, thread_id)
        assert room.name == "Hall"


# --- drop-superseded-version-rows ---------------------------------------------------------


def _note_for(client: TestClient, thread, package_id: str = "hall-bench") -> str | None:
    from sqlalchemy.orm import Session

    from app.agent import house_file

    with Session(client.app.state.engine) as session:
        return house_file.read_summary(session, thread, package_id)[0]


def _bound_thread(client: TestClient, note: str, owner_edited: bool = False):
    from sqlalchemy.orm import Session

    from app.agent import house_file

    with Session(client.app.state.engine) as session:
        thread = house_file.create_thread(session, "test", package_id="hall-bench")
        house_file.add_build(session, thread.id, "hall-bench")
        house_file.write_summary(session, thread.id, note, "m1", "hall-bench", owner_edited=owner_edited)
        session.commit()
        return thread.id


def test_approving_a_newer_version_drops_the_older_saved_rows_and_keeps_every_version(
    client: TestClient, record, render_root: Path
) -> None:
    create(client)
    wider = desk()
    wider["modules"][0]["width"] = 1100
    assert client.put("/packages/hall-bench/spec", json={"spec": wider}).status_code == 202
    record(versions=(1, 2))
    note = "- **Version 1:** saved\n- Version 2 had doors on top; moved to the bottom\n- **Handles:** push-latch"
    first = _bound_thread(client, note, owner_edited=True)
    second = _bound_thread(client, "## Builds\n- v1 saved")
    assert client.put("/packages/hall-bench/versions/2/approval").status_code == 200
    kept = "- Version 2 had doors on top; moved to the bottom\n- **Handles:** push-latch"
    assert _note_for(client, first) == kept
    assert _note_for(client, second) == "## Builds\n- v1 saved"  # would leave no row: kept
    from sqlalchemy.orm import Session

    from app.db.models import ThreadPiece

    with Session(client.app.state.engine) as session:
        assert session.get(ThreadPiece, (first, "hall-bench")).summary_owner_edited is True
        assert session.get(ThreadPiece, (second, "hall-bench")).summary_owner_edited is False
    assert [v["version"] for v in client.get("/packages/hall-bench").json()["versions"]] == [2, 1]
    assert storage.version_dir(render_root, "hall-bench", 1).is_dir()


def test_approving_again_and_approving_the_older_version_change_no_note(client: TestClient, record) -> None:
    create(client)
    wider = desk()
    wider["modules"][0]["width"] = 1100
    assert client.put("/packages/hall-bench/spec", json={"spec": wider}).status_code == 202
    record(versions=(1, 2))
    thread = _bound_thread(client, "- Version 2 saved\n- **Handles:** push-latch")
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    assert _note_for(client, thread).startswith("- Version 2 saved")  # 2 is newer than 1
    assert client.put("/packages/hall-bench/versions/2/approval").status_code == 200
    after = _note_for(client, thread)
    assert "Version 2 saved" in after  # the approved version itself is kept
    assert client.put("/packages/hall-bench/versions/2/approval").status_code == 200
    assert _note_for(client, thread) == after


def test_a_failure_dropping_the_rows_still_approves(client: TestClient, record, monkeypatch) -> None:
    from app.agent import decisions_note

    create(client)
    record()
    monkeypatch.setattr(decisions_note, "drop_superseded_version_rows", lambda *a: 1 / 0)
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    assert client.get("/packages/hall-bench/versions/1").json()["approved_at"] is not None


def test_a_conversation_not_bound_to_the_piece_keeps_its_note(client: TestClient, record) -> None:
    from sqlalchemy.orm import Session

    from app.agent import house_file

    create(client)
    wider = desk()
    wider["modules"][0]["width"] = 1100
    assert client.put("/packages/hall-bench/spec", json={"spec": wider}).status_code == 202
    record(versions=(1, 2))
    with Session(client.app.state.engine) as session:
        loose = house_file.create_thread(session, "loose")
        house_file.write_summary(session, loose.id, "- Version 1 saved\n- **A:** b", "m1")
        session.commit()
        loose_id = loose.id
    assert client.put("/packages/hall-bench/versions/2/approval").status_code == 200
    with Session(client.app.state.engine) as session:
        assert house_file.read_summary(session, loose_id)[0] == "- Version 1 saved\n- **A:** b"


# --- brief-height-follows-approved-version -----------------------------------------------


def _brief_of(client: TestClient, package_id: str = "hall-bench") -> dict:
    from sqlalchemy.orm import Session

    from app.db.models import Piece

    with Session(client.app.state.engine) as session:
        return dict(session.get(Piece, package_id).brief)


def _set_brief(client: TestClient, brief: dict) -> None:
    from sqlalchemy.orm import Session

    from app.db.models import Piece

    with Session(client.app.state.engine) as session:
        session.get(Piece, "hall-bench").brief = brief
        session.commit()


def test_raised_height_limit_only_raises_a_stated_limit_and_names_the_version() -> None:
    from app.agent.house_file import raised_height_limit

    brief = {"room": "Wohnen", "purpose": "wall unit up to 2.2 m", "max_piece_height_mm": 2200, "style": "oak"}
    assert raised_height_limit(brief, 2238, 17) == brief | {"max_piece_height_mm": 2238, "max_piece_height_from_version": 17}
    assert raised_height_limit(brief, 2200, 3) is brief
    assert raised_height_limit(brief, 2100, 3) is brief
    assert raised_height_limit({"room": "Wohnen"}, 2238, 3) == {"room": "Wohnen"}
    assert raised_height_limit({"max_piece_height_mm": None}, 2238, 3) == {"max_piece_height_mm": None}


def test_approving_a_taller_version_raises_the_stored_height_limit(client: TestClient, record) -> None:
    from app.blender.custom_build.derive import overall

    create(client)
    record()
    height = overall(desk())["h"]
    _set_brief(client, {"room": "Wohnen", "max_piece_height_mm": height - 38, "style": "oak"})
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    assert _brief_of(client) == {
        "room": "Wohnen", "max_piece_height_mm": height, "max_piece_height_from_version": 1, "style": "oak",
    }
    # Unapproving keeps the limit; re-approving and an unrelated change leave it.
    assert client.delete("/packages/hall-bench/versions/1/approval").status_code == 200
    assert _brief_of(client)["max_piece_height_mm"] == height


def test_approving_a_lower_version_or_with_no_limit_leaves_the_brief(client: TestClient, record) -> None:
    from app.blender.custom_build.derive import overall

    create(client)
    record()
    brief = {"room": "Wohnen", "max_piece_height_mm": overall(desk())["h"] + 100}
    _set_brief(client, brief)
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    assert _brief_of(client) == brief
    client.delete("/packages/hall-bench/versions/1/approval")
    _set_brief(client, {"room": "Wohnen"})
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    assert _brief_of(client) == {"room": "Wohnen"}


def test_a_failure_raising_the_limit_still_approves(client: TestClient, record, monkeypatch) -> None:
    from app.agent import house_file

    create(client)
    record()
    monkeypatch.setattr(house_file, "raise_brief_height_limit", lambda *a: 1 / 0)
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    assert client.get("/packages/hall-bench/versions/1").json()["approved_at"] is not None


def _seed_height_items(client: TestClient) -> None:
    from sqlalchemy.orm import Session

    from app.agent import house_file

    base = {"expected_source": "brief", "image": 1, "severity": "major"}
    with Session(client.app.state.engine) as session:
        house_file.record_review(
            session, "hall-bench", 1, ["screenshot.png"],
            [
                {**base, "aspect": "brief", "expected": "max_piece_height_mm 2200.0 mm", "observed": "taller than 2200"},
                {**base, "aspect": "brief", "expected": "doors covering the bottom two shelves", "observed": "doors on top"},
                {**base, "aspect": "brief", "expected": "max_piece_height_mm 2400", "observed": "over"},
            ],
        )
        session.commit()


def _item_statuses(client: TestClient) -> dict[str, str]:
    from sqlalchemy.orm import Session

    from app.agent import house_file

    with Session(client.app.state.engine) as session:
        return {
            i.expected: i.status
            for r in house_file.reviews_for(session, "hall-bench", 1)
            for i in house_file.items_of(session, r.id)
        }


def test_a_second_approval_after_the_limit_was_raised_still_clears_earlier_items(client: TestClient, record) -> None:
    create(client)
    record()
    _set_brief(client, {"room": "Wohnen", "max_piece_height_mm": 2238, "max_piece_height_from_version": 1})
    _seed_height_items(client)
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    statuses = _item_statuses(client)
    assert statuses["max_piece_height_mm 2200.0 mm"] == "dismissed"
    assert statuses["max_piece_height_mm 2400"] == "open"  # a higher figure than the limit stays
    assert statuses["doors covering the bottom two shelves"] == "open"
    # The review text is as the Reviewer wrote it.
    assert "max_piece_height_mm 2200.0 mm" in statuses


def test_a_failure_dismissing_items_still_approves(client: TestClient, record, monkeypatch) -> None:
    from app.agent import house_file

    create(client)
    record()
    _set_brief(client, {"max_piece_height_mm": 2238})
    monkeypatch.setattr(house_file, "dismiss_outdated_height_items", lambda *a: 1 / 0)
    assert client.put("/packages/hall-bench/versions/1/approval").status_code == 200
    assert client.get("/packages/hall-bench/versions/1").json()["approved_at"] is not None
