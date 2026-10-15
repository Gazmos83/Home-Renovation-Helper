"""render-guard + scene-rendering: the render routes, with a fake launcher."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.blender import storage
from app.render import benchmark_store as store
from tests.api_helpers import create, desk, make_client, room_document, sign_in
from tests.blender_fakes import fake_failure_launch, fake_pipeline_launch, png_size

BASE = "/packages/hall-bench/versions/1"


def reset_render_settings(client: TestClient) -> None:
    """The database is shared across tests: a calibrated multiplier or a benchmark
    left by an earlier test must not leak into this one."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(client.app.state.engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'render:%'"))
        session.commit()


@pytest.fixture
def launched() -> list[list[str]]:
    return []


@pytest.fixture
def client(
    migrated_database: str, render_root: Path, fake_blender: Path, launched: list[list[str]]
) -> Iterator[TestClient]:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch(calls=launched))
    sign_in(c)
    reset_render_settings(c)
    store.write_benchmark(c.app.state.engine, 2.5, blender_version="5.2.1 LTS")
    assert create(c).status_code == 202
    launched.clear()
    yield c
    c.__exit__(None, None, None)


def render(client: TestClient, **body):
    return client.post(f"{BASE}/renders", json=body)


def renders_launched(launched: list[list[str]]) -> list[list[str]]:
    return [argv for argv in launched if not any(a.endswith("build_custom_build.py") for a in argv)]


# --- draft ------------------------------------------------------------------------------------


def test_a_draft_still_runs_with_its_estimate_and_is_served(client: TestClient, render_root: Path) -> None:
    response = render(client, kind="still", tier="draft")
    assert response.status_code == 202
    body = response.json()
    assert body["tier"] == "draft" and body["frames"] == 1 and body["status"] == "queued"
    assert body["estimate"] == "about 2 seconds"  # 1 frame × 0.64 MP × 2.5 s/MP = 1.6 s
    still = client.get(f"{BASE}/files/still.png")
    assert still.status_code == 200 and still.headers["content-type"] == "image/png"
    assert png_size(render_root / "hall-bench/v1/still.png") == (800, 800)
    job = client.get(BASE).json()["jobs"]["still"]
    assert job["status"] == "succeeded" and job["tier"] == "draft"


def test_a_draft_turntable_is_twelve_frames(client: TestClient, render_root: Path) -> None:
    response = render(client, kind="turntable", tier="draft")
    assert response.status_code == 202 and response.json()["frames"] == 12
    assert response.json()["estimate"] == "about 19 seconds"
    assert client.get(f"{BASE}/files/frames/11").status_code == 200
    assert client.get(f"{BASE}/files/frames/12").status_code == 404
    assert client.get(f"{BASE}/files/viewer.html").status_code == 200
    assert client.get(BASE).json()["renders"]["turntable_frames"] == 12


def test_a_room_draft_turntable_is_served_under_room(client: TestClient) -> None:
    response = render(client, kind="turntable", tier="draft", room=room_document("turntable"))
    assert response.status_code == 202 and response.json()["room"] is True
    assert client.get(f"{BASE}/files/room/frames/0").status_code == 200
    assert client.get(f"{BASE}/files/room/viewer.html").status_code == 200
    assert client.get(BASE).json()["renders"]["room_turntable_frames"] == 12


def test_a_room_with_the_wrong_output_kind_is_refused(client: TestClient, launched) -> None:
    response = render(client, kind="still", tier="draft", room=room_document("turntable"))
    assert response.status_code == 422 and "output.kind" in response.json()["detail"]["reason"]
    assert renders_launched(launched) == []


@pytest.mark.parametrize("field", ["frames", "resolution"])
def test_a_room_document_naming_a_tier_owned_field_is_refused(client: TestClient, field: str) -> None:
    room = room_document("turntable", **{field: 36 if field == "frames" else "draft"})
    response = render(client, kind="turntable", tier="draft", room=room)
    assert response.status_code == 422 and field in response.json()["detail"]["reason"]


def test_two_renders_back_to_back_are_both_accepted_and_never_overlap(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    tracker: list[int] = []
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch(delay=0.05, tracker=tracker))
    sign_in(c)
    reset_render_settings(c)
    store.write_benchmark(c.app.state.engine, 2.5)
    create(c)
    first = c.post(f"{BASE}/renders", json={"kind": "still", "tier": "draft"})
    second = c.post(f"{BASE}/renders", json={"kind": "turntable", "tier": "draft"})
    assert (first.status_code, second.status_code) == (202, 202)
    jobs = c.get(BASE).json()["jobs"]
    assert jobs["still"]["status"] == jobs["turntable"]["status"] == "succeeded"
    c.__exit__(None, None, None)


# --- the guard's refusals ---------------------------------------------------------------------


@pytest.mark.parametrize("field", ["frames", "resolution", "width", "height", "samples", "engine"])
def test_a_raw_knob_is_refused_by_name_and_starts_nothing(client: TestClient, launched, field: str) -> None:
    response = render(client, kind="turntable", tier="draft", **{field: 100})
    assert response.status_code == 422
    assert response.json()["detail"]["field"] == field
    assert renders_launched(launched) == []


def test_a_missing_tier_is_refused(client: TestClient, launched) -> None:
    response = render(client, kind="still")
    assert response.status_code == 422 and "tier is required" in response.json()["detail"]["reason"]
    assert renders_launched(launched) == []


@pytest.mark.parametrize("tier", ["ultra", "preview"])
def test_an_unknown_tier_is_refused_listing_the_two(client: TestClient, tier: str) -> None:
    reason = render(client, kind="still", tier=tier).json()["detail"]["reason"]
    assert tier in reason and "the tiers are draft, final" in reason


def test_no_benchmark_refuses_every_render(client: TestClient, launched) -> None:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    with Session(client.app.state.engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key = 'render:benchmark'"))
        session.commit()
    response = render(client, kind="still", tier="draft")
    assert response.status_code == 409 and response.json()["detail"]["failure_class"] == "benchmark_missing"
    assert renders_launched(launched) == []


def test_an_unbuilt_version_cannot_be_rendered(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_failure_launch)
    sign_in(c)
    reset_render_settings(c)
    store.write_benchmark(c.app.state.engine, 2.5)
    create(c)
    response = c.post(f"{BASE}/renders", json={"kind": "still", "tier": "draft"})
    assert response.status_code == 409 and response.json()["detail"]["failure_class"] == "not_built"
    c.__exit__(None, None, None)


def test_an_unknown_field_is_refused(client: TestClient) -> None:
    response = render(client, kind="still", tier="draft", seed=3)
    assert response.status_code == 422 and "seed" in response.json()["detail"]["reason"]


# --- final: two-step approval -----------------------------------------------------------------


def test_a_final_answers_with_the_estimate_and_a_token_and_starts_nothing(
    client: TestClient, launched
) -> None:
    response = render(client, kind="turntable", tier="final")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["failure_class"] == "approval_required" and detail["tier"] == "final"
    assert detail["estimate"] == "about 101 minutes" and detail["approval_token"]
    assert renders_launched(launched) == []


def test_approving_a_final_with_yes_runs_it_and_calibrates_the_multiplier(
    client: TestClient, render_root: Path
) -> None:
    token = render(client, kind="turntable", tier="final").json()["detail"]["approval_token"]
    response = client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
    assert response.status_code == 202 and response.json()["tier"] == "final"
    frames = sorted((render_root / "hall-bench/v1/frames").iterdir())
    assert len(frames) == 36 and png_size(frames[0]) == (1500, 1500)
    job = client.get(BASE).json()["jobs"]["turntable"]
    assert job["tier"] == "final" and job["status"] == "succeeded"
    multiplier = store.stored_cycles_multiplier(client.app.state.engine)
    assert multiplier is not None and multiplier != 30.0


def test_a_second_final_does_not_recalibrate(client: TestClient) -> None:
    for _ in range(2):
        token = render(client, kind="still", tier="final").json()["detail"]["approval_token"]
        client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
        if _ == 0:
            first = store.stored_cycles_multiplier(client.app.state.engine)
    assert store.stored_cycles_multiplier(client.app.state.engine) == first


def test_declining_a_final_refuses_it_and_discards_the_token(client: TestClient, launched) -> None:
    token = render(client, kind="turntable", tier="final").json()["detail"]["approval_token"]
    declined = client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "no"})
    assert declined.status_code == 409 and declined.json()["detail"]["failure_class"] == "declined"
    again = client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
    assert again.status_code == 409 and again.json()["detail"]["failure_class"] == "approval_invalid"
    assert renders_launched(launched) == []


def test_a_token_is_single_use(client: TestClient, launched) -> None:
    token = render(client, kind="still", tier="final").json()["detail"]["approval_token"]
    ok = client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
    reused = client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
    assert ok.status_code == 202 and reused.status_code == 409
    assert len(renders_launched(launched)) == 1


def test_a_token_for_another_version_is_refused_and_left_usable(client: TestClient) -> None:
    client.put("/packages/hall-bench/spec", json={"spec": desk()})
    token = render(client, kind="still", tier="final").json()["detail"]["approval_token"]
    wrong = client.post(
        "/packages/hall-bench/versions/2/renders/approve",
        json={"approval_token": token, "confirm": "yes"},
    )
    assert wrong.status_code == 409 and "different package" in wrong.json()["detail"]["reason"]
    right = client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
    assert right.status_code == 202


@pytest.mark.parametrize("body", [{}, {"confirm": "yes"}, {"approval_token": "nope", "confirm": "yes"}])
def test_a_missing_or_unknown_token_is_refused(client: TestClient, body: dict) -> None:
    response = client.post(f"{BASE}/renders/approve", json=body)
    assert response.status_code in (409, 422)


def test_an_expired_token_is_refused(client: TestClient) -> None:
    from app.render.approvals import ApprovalStore

    now = [0.0]
    client.app.state.render_approvals = ApprovalStore(clock=lambda: now[0], ttl=60)
    token = render(client, kind="still", tier="final").json()["detail"]["approval_token"]
    now[0] = 61.0
    response = client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
    assert response.status_code == 409 and "expired" in response.json()["detail"]["reason"]


# --- gate and availability --------------------------------------------------------------------


def test_the_routes_need_the_owner_cookie(
    migrated_database: str, render_root: Path, fake_blender: Path
) -> None:
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch())
    assert c.post(f"{BASE}/renders", json={"kind": "still", "tier": "draft"}).status_code == 401
    assert c.post(f"{BASE}/renders/approve", json={}).status_code == 401
    c.__exit__(None, None, None)


def test_an_unknown_version_is_not_found(client: TestClient) -> None:
    response = client.post("/packages/hall-bench/versions/9/renders", json={"kind": "still", "tier": "draft"})
    assert response.status_code == 404


def test_a_missing_binary_refuses_renders(client: TestClient, tmp_path: Path) -> None:
    client.app.state.settings = client.app.state.settings.model_copy(
        update={"blender_bin": tmp_path / "gone"}
    )
    response = render(client, kind="still", tier="draft")
    assert response.status_code == 503 and response.json()["detail"]["failure_class"] == "blender_unavailable"


def test_the_storage_status_carries_the_render_jobs(client: TestClient, render_root: Path) -> None:
    render(client, kind="still", tier="draft")
    status = storage.read_status(render_root / "hall-bench/v1")
    assert status["renders"]["still"]["tier"] == "draft"
