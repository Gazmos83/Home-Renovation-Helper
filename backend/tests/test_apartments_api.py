"""apartment-shell: apartment and shell routes with a fake launcher (every render at `draft` or refused)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent import house_file
from app.render import benchmark_store as store
from tests.api_helpers import make_client, sign_in
from tests.blender_fakes import fake_failure_launch, fake_pipeline_launch, png_size
from tests.conftest import clean_house_file
from tests.test_record_plan import PLAN

BASE = "/apartments/flat/shell"


def seed(client: TestClient) -> None:
    with Session(client.app.state.engine) as session:
        house_file.upsert_apartment(
            session, "Flat", PLAN["ceiling_height_mm"], PLAN["wall_thickness_mm"],
            [
                {"name": r["name"], "corners_mm": r["corners_mm"], "openings": r.get("openings", [])}
                for r in PLAN["rooms"]
            ],
        )
        session.commit()


@pytest.fixture
def launched() -> list[list[str]]:
    return []


@pytest.fixture
def client(
    migrated_database: str, render_root: Path, fake_blender: Path, launched: list[list[str]]
) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch(calls=launched))
    clean_house_file(c.app.state.engine)
    sign_in(c)
    store.write_benchmark(c.app.state.engine, 2.5, blender_version="5.2.1 LTS")
    seed(c)
    yield c
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def test_apartments_are_listed_and_read(client: TestClient) -> None:
    listed = client.get("/apartments").json()
    assert [a["apartment"] for a in listed] == ["flat"]
    assert listed[0]["rooms"] == ["Bedroom", "Living room"] and listed[0]["shell_versions"] == []
    assert client.get("/apartments/flat").json()["name"] == "Flat"
    assert client.get("/apartments/ghost").status_code == 404


def test_a_build_publishes_the_shell_files_and_serves_them_by_exact_name(client: TestClient, render_root: Path) -> None:
    response = client.post(BASE)
    assert response.status_code == 202
    assert response.json() == {"apartment": "flat", "version": 1, "status": "queued"}
    described = client.get(f"{BASE}/versions/1").json()
    assert described["status"] == "succeeded"
    assert {"model.glb", "model.blend", "shell.json", "screenshot.png"} <= set(described["files"])
    shot = client.get(f"{BASE}/versions/1/files/screenshot.png")
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/png"
    assert png_size(render_root / "shells/flat/v1/screenshot.png") == (800, 500)
    assert client.get(f"{BASE}/versions/1/files/shell.json").status_code == 200
    for name in ("input.json", "../v1/status.json/x", "nope.txt", "frames/0"):
        assert client.get(f"{BASE}/versions/1/files/{name}").status_code == 404, name
    frames = render_root / "shells/flat/v1/frames"
    frames.mkdir()
    (frames / "frame_000.png").write_bytes(b"png")
    assert client.get(f"{BASE}/versions/1/files/frames/0").status_code == 200
    assert client.get(f"{BASE}/versions/1/files/frames/frame_000.png").status_code == 200


def test_each_build_is_a_new_version_and_the_first_is_untouched(client: TestClient, render_root: Path) -> None:
    client.post(BASE)
    before = (render_root / "shells/flat/v1/shell.json").read_text(encoding="utf-8")
    assert client.post(BASE).json()["version"] == 2
    assert (render_root / "shells/flat/v1/shell.json").read_text(encoding="utf-8") == before
    assert client.get("/apartments/flat").json()["shell_versions"] == [2, 1]


def test_an_apartment_with_no_rooms_cannot_be_built(client: TestClient) -> None:
    with Session(client.app.state.engine) as session:
        from app.db.models import Room

        session.query(Room).delete()
        session.commit()
    response = client.post(BASE)
    assert response.status_code == 409 and response.json()["detail"]["failure_class"] == "no_rooms"


def test_a_draft_shell_turntable_runs_with_its_estimate_and_is_served(
    client: TestClient, render_root: Path, launched
) -> None:
    client.post(BASE)
    launched.clear()
    response = client.post(f"{BASE}/versions/1/renders", json={"kind": "turntable", "tier": "draft"})
    assert response.status_code == 202
    body = response.json()
    assert body["tier"] == "draft" and body["frames"] == 12 and body["estimate"] == "about 19 seconds"
    assert client.get(f"{BASE}/versions/1/files/frames/11").status_code == 200
    assert client.get(f"{BASE}/versions/1/files/viewer.html").status_code == 200
    job = client.get(f"{BASE}/versions/1").json()["jobs"]["turntable"]
    assert job["status"] == "succeeded" and job["tier"] == "draft"
    assert any("render_turntable.py" in " ".join(argv) for argv in launched)


def test_raw_frames_are_refused_naming_the_field_and_nothing_launches(client: TestClient, launched) -> None:
    client.post(BASE)
    launched.clear()
    response = client.post(f"{BASE}/versions/1/renders", json={"kind": "turntable", "tier": "draft", "frames": 12})
    assert response.status_code == 422 and response.json()["detail"]["field"] == "frames"
    assert launched == []


def test_a_tier_is_required(client: TestClient) -> None:
    client.post(BASE)
    response = client.post(f"{BASE}/versions/1/renders", json={"kind": "turntable"})
    assert response.status_code == 422 and response.json()["detail"]["field"] == "tier"


def test_a_final_answers_409_with_the_estimate_then_runs_only_on_yes(client: TestClient, launched) -> None:
    client.post(BASE)
    launched.clear()
    first = client.post(f"{BASE}/versions/1/renders", json={"kind": "turntable", "tier": "final"})
    assert first.status_code == 409
    detail = first.json()["detail"]
    assert detail["failure_class"] == "approval_required" and detail["estimate"]
    assert launched == []

    declined = client.post(
        f"{BASE}/versions/1/renders/approve", json={"approval_token": detail["approval_token"], "confirm": "no"}
    )
    assert declined.status_code == 409 and launched == []

    again = client.post(f"{BASE}/versions/1/renders", json={"kind": "turntable", "tier": "final"}).json()["detail"]
    approved = client.post(
        f"{BASE}/versions/1/renders/approve", json={"approval_token": again["approval_token"], "confirm": "yes"}
    )
    assert approved.status_code == 202 and approved.json()["tier"] == "final"
    assert any("render_turntable.py" in " ".join(argv) for argv in launched)


def test_an_unbuilt_shell_cannot_be_rendered(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_failure_launch)
    clean_house_file(c.app.state.engine)
    sign_in(c)
    store.write_benchmark(c.app.state.engine, 2.5)
    seed(c)
    c.post(BASE)
    response = c.post(f"{BASE}/versions/1/renders", json={"kind": "turntable", "tier": "draft"})
    assert response.status_code == 409 and response.json()["detail"]["failure_class"] == "not_built"
    clean_house_file(c.app.state.engine)
    c.__exit__(None, None, None)


def test_every_route_needs_the_session(client: TestClient) -> None:
    anonymous = TestClient(client.app)
    assert anonymous.get("/apartments").status_code == 401
    assert anonymous.post(BASE).status_code == 401
    assert anonymous.post(f"{BASE}/versions/1/renders", json={"tier": "draft"}).status_code == 401
