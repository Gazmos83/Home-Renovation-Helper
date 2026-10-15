"""render-offload: the developer panel's routes."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.blender.launch import LaunchResult
from app.db.models import RemoteRenderJob
from app.render import benchmark_store as store
from app.render.offload.runtime import OffloadRuntime
from tests.api_helpers import sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.offload_fakes import FakeServer
from tests.test_admin_models_api import _client as dev_client
from tests.test_offload_job import CONFIG


class AdminServer(FakeServer):
    """A fake server that also answers the GPU listing."""

    gpus = "NVIDIA RTX 4090;NVIDIA RTX 4090"

    async def _ssh(self, command: str, timeout: float) -> LaunchResult:
        if "GPUS:" in command:
            return LaunchResult(0, f"GPUS:{self.gpus}", False)
        return await super()._ssh(command, timeout)


def combined(server: FakeServer, local):
    async def launch(argv, cwd, timeout):
        if argv[0] in ("ssh", "scp"):
            return await server.launch(argv, cwd, timeout)
        return await local(argv, cwd, timeout)

    return launch


def clear(engine) -> None:
    with Session(engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'offload:%'"))
        session.execute(delete(RemoteRenderJob))
        session.commit()


@pytest.fixture
def server(tmp_path: Path) -> AdminServer:
    return AdminServer(tmp_path / "server")


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, server: AdminServer) -> Iterator[TestClient]:
    c = dev_client(migrated_database, render_root, fake_blender, dev=True)
    sign_in(c)
    clear(c.app.state.engine)
    c.app.state.blender_launch = combined(server, fake_pipeline_launch())
    yield c
    clear(c.app.state.engine)
    c.__exit__(None, None, None)


def configure(client: TestClient) -> None:
    client.app.state.offload = OffloadRuntime(CONFIG)


def test_the_panel_disabled_answers_404(migrated_database: str, render_root: Path, fake_blender: Path) -> None:
    c = dev_client(migrated_database, render_root, fake_blender, dev=False)
    sign_in(c)
    try:
        for method, path in (("GET", ""), ("POST", "/test"), ("POST", "/benchmark"), ("PUT", "/target"), ("PUT", "/rate")):
            assert c.request(method, f"/admin/offload{path}", json={}).status_code == 404, path
    finally:
        c.__exit__(None, None, None)


def test_every_route_needs_the_owner_session(migrated_database: str, render_root: Path, fake_blender: Path) -> None:
    c = dev_client(migrated_database, render_root, fake_blender, dev=True)
    try:
        assert c.get("/admin/offload").status_code == 401
        assert c.put("/admin/offload/target", json={"target": "local"}).status_code == 401
    finally:
        c.__exit__(None, None, None)


def test_the_summary_without_a_server(client: TestClient) -> None:
    body = client.get("/admin/offload").json()
    assert body["configured"] is False and body["host"] is None
    assert body["target"] == "local" and body["benchmark"] is None and body["jobs"] == []
    assert body["pinned_version"] == "5.2.1"


def test_the_summary_shows_the_connection_but_never_the_key_or_known_hosts(client: TestClient) -> None:
    configure(client)
    response = client.get("/admin/offload")
    body = response.json()
    assert (body["host"], body["port"], body["user"]) == ("gpu.example.org", 22, "render")
    assert (body["blender"], body["device"]) == ("/opt/blender-5.2.1/blender", "OPTIX")
    for secret in ("/keys", "id_ed25519", "known"):
        assert secret not in response.text


def test_the_target_is_refused_while_unconfigured_and_stays_local(client: TestClient) -> None:
    response = client.put("/admin/offload/target", json={"target": "remote"})
    assert response.status_code == 422 and response.json()["detail"]["field"] == "target"
    assert "not configured" in response.json()["detail"]["reason"]
    assert client.get("/admin/offload").json()["target"] == "local"


def test_the_target_can_be_switched_when_configured_and_applies_at_once(client: TestClient) -> None:
    configure(client)
    assert client.put("/admin/offload/target", json={"target": "remote"}).json()["target"] == "remote"
    assert store.read_final_target(client.app.state.engine) == "remote"
    assert client.put("/admin/offload/target", json={"target": "local"}).json()["target"] == "local"


@pytest.mark.parametrize("body", [{"target": "cloud"}, {"target": "remote", "x": 1}, {}])
def test_an_unknown_target_or_field_is_refused(client: TestClient, body: dict) -> None:
    configure(client)
    assert client.put("/admin/offload/target", json=body).status_code == 422


def test_the_hourly_rate_is_stored_and_a_negative_one_is_refused_naming_the_field(client: TestClient) -> None:
    assert client.put("/admin/offload/rate", json={"hourly_rate_eur": 1.8}).json()["hourly_rate_eur"] == 1.8
    response = client.put("/admin/offload/rate", json={"hourly_rate_eur": -1})
    assert response.status_code == 422 and response.json()["detail"]["field"] == "hourly_rate_eur"
    assert store.read_hourly_rate(client.app.state.engine) == 1.8


def test_a_connection_test_reports_version_and_gpus(client: TestClient) -> None:
    configure(client)
    body = client.post("/admin/offload/test").json()
    assert body == {
        "reachable": True, "blender_version": "5.2.1", "pinned_version": "5.2.1", "version_ok": True,
        "gpus": ["NVIDIA RTX 4090", "NVIDIA RTX 4090"],
    }


def test_a_connection_test_of_a_server_that_is_off(client: TestClient, tmp_path: Path) -> None:
    configure(client)
    client.app.state.blender_launch = combined(AdminServer(tmp_path / "off", reachable=False), fake_pipeline_launch())
    body = client.post("/admin/offload/test").json()
    assert body["reachable"] is False and body["blender_version"] is None and body["gpus"] == []


def test_a_connection_test_of_the_wrong_blender(client: TestClient, tmp_path: Path) -> None:
    configure(client)
    client.app.state.blender_launch = combined(
        AdminServer(tmp_path / "old", version="Blender 4.5.0 LTS"), fake_pipeline_launch()
    )
    body = client.post("/admin/offload/test").json()
    assert body["reachable"] is True and body["version_ok"] is False and body["blender_version"] == "4.5.0"
    assert body["gpus"] == []


def test_a_connection_test_without_a_server_is_409(client: TestClient) -> None:
    assert client.post("/admin/offload/test").status_code == 409


def test_the_remote_benchmark_is_measured_and_returned(client: TestClient) -> None:
    configure(client)
    body = client.post("/admin/offload/benchmark").json()
    assert body["benchmark"]["seconds_per_megapixel"] > 0 and body["benchmark"]["calibrated"] is False
    assert store.read_remote_benchmark(client.app.state.engine) is not None


def test_a_failed_remote_benchmark_is_502_and_stores_nothing(client: TestClient, tmp_path: Path) -> None:
    configure(client)
    client.app.state.blender_launch = combined(AdminServer(tmp_path / "off", reachable=False), fake_pipeline_launch())
    response = client.post("/admin/offload/benchmark")
    assert response.status_code == 502 and "unreachable" in response.json()["detail"]["reason"]
    assert store.read_remote_benchmark(client.app.state.engine) is None


def add_job(client: TestClient, *, age_minutes: int, actual: float | None, outcome="succeeded") -> None:
    with Session(client.app.state.engine) as session:
        session.add(
            RemoteRenderJob(
                package_id="bench", version=1, render_key="turntable", estimate_seconds=60.0,
                actual_seconds=actual, transfer_seconds=5.0, outcome=outcome,
                started_at=datetime.now(UTC) - timedelta(minutes=age_minutes),
            )
        )
        session.commit()


def test_recent_jobs_show_numbers_and_a_euro_estimate_only_with_a_rate(client: TestClient) -> None:
    add_job(client, age_minutes=10, actual=3600.0)
    add_job(client, age_minutes=1, actual=1800.0, outcome="failed")
    [newest, older] = client.get("/admin/offload").json()["jobs"]
    assert newest["outcome"] == "failed" and older["actual_seconds"] == 3600.0
    assert newest["cost_eur"] is None and older["transfer_seconds"] == 5.0
    client.put("/admin/offload/rate", json={"hourly_rate_eur": 1.8})
    [newest, older] = client.get("/admin/offload").json()["jobs"]
    assert older["cost_eur"] == 1.8 and newest["cost_eur"] == 0.9


def test_only_the_last_twenty_jobs_are_listed(client: TestClient) -> None:
    for minutes in range(25):
        add_job(client, age_minutes=minutes, actual=60.0)
    assert len(client.get("/admin/offload").json()["jobs"]) == 20


# --- pod mode (render-pod-lifecycle) ---------------------------------------------------------------


@pytest.fixture
def runpod(client: TestClient) -> Iterator:
    from dataclasses import replace

    from pydantic import SecretStr

    from app.render.offload.pod import PodManager, PodSettings
    from app.render.offload.runpod import RunPodClient
    from tests.offload_fakes import FakeRunPod

    fake = FakeRunPod()
    runtime = OffloadRuntime(replace(CONFIG, host="", host_key_alias="hra-render-pod"))
    runtime.pod = PodManager(
        client=RunPodClient(SecretStr("rpa_SECRETKEYVALUE"), transport=fake.transport),
        settings=PodSettings(("NVIDIA GeForce RTX 4090",), "runpod/base:0.6.2", "vol123"),
        template=runtime.config, semaphore=runtime.semaphore, engine=client.app.state.engine,
    )
    client.app.state.offload = runtime

    def clear_records() -> None:
        with Session(client.app.state.engine) as session:
            session.execute(text("DELETE FROM render_pod_sessions"))
            session.execute(text("DELETE FROM gpu_stock_samples"))
            session.commit()

    clear_records()
    yield fake
    clear_records()


def test_pod_mode_summary_shows_the_pod_but_never_the_key(client: TestClient, runpod) -> None:
    response = client.get("/admin/offload")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "pod" and body["host"] is None and body["port"] is None
    pod = body["pod"]
    assert pod["gpu_types"] == ["NVIDIA GeForce RTX 4090"] and pod["image"] == "runpod/base:0.6.2"
    assert pod["volume_id"] == "vol123" and pod["state"] == "none" and pod["idle_minutes"] == 10
    assert body["pod_sessions"] == []
    assert "rpa_" not in response.text and "id_ed25519" not in response.text


def test_pod_mode_connection_test_with_nothing_running_creates_no_pod(client: TestClient, runpod) -> None:
    response = client.post("/admin/offload/test")
    assert response.status_code == 200
    assert response.json() == {"runpod_ok": True, "volume_found": True, "data_center": "EU-RO-1", "reason": None}
    assert runpod.created == []


def test_pod_mode_connection_test_reports_a_missing_volume(client: TestClient, runpod) -> None:
    runpod.volume_id = "elsewhere"
    body = client.post("/admin/offload/test").json()
    assert body["runpod_ok"] is True and body["volume_found"] is False
    assert "network volume was not found" in body["reason"]


def test_delete_pod_now_deletes_it_and_shows_none(client: TestClient, runpod) -> None:
    pod = client.app.state.offload.pod
    pod.pod_id, pod.state = runpod.add_pod("hra-render"), "running"
    response = client.post("/admin/offload/pod/delete")
    assert response.status_code == 200
    assert response.json()["pod"]["state"] == "none" and runpod.deleted == ["pod1"]


def test_delete_pod_now_is_refused_during_a_render(client: TestClient, runpod) -> None:
    import asyncio

    runtime = client.app.state.offload
    runtime.pod.pod_id, runtime.pod.state = runpod.add_pod("hra-render"), "running"
    asyncio.run(runtime.semaphore.acquire())
    try:
        response = client.post("/admin/offload/pod/delete")
    finally:
        runtime.semaphore.release()
    assert response.status_code == 409 and "a render is running on the pod" in response.text
    assert runpod.deleted == []


def test_delete_pod_now_outside_pod_mode_is_409(client: TestClient) -> None:
    configure(client)
    assert client.post("/admin/offload/pod/delete").status_code == 409


@pytest.mark.parametrize("minutes", [0, 121, 2.5])
def test_idle_minutes_out_of_range_are_refused_and_unchanged(client: TestClient, runpod, minutes) -> None:
    response = client.put("/admin/offload/idle", json={"idle_minutes": minutes})
    assert response.status_code == 422
    assert store.read_idle_minutes(client.app.state.engine) == 10


def test_idle_minutes_are_stored(client: TestClient, runpod) -> None:
    response = client.put("/admin/offload/idle", json={"idle_minutes": 25})
    assert response.status_code == 200 and response.json()["pod"]["idle_minutes"] == 25


def test_pod_sessions_are_listed_with_their_cost(client: TestClient, runpod) -> None:
    from app.render.offload import sessions

    engine = client.app.state.engine
    session_id = sessions.open_session(engine, "pod7", "NVIDIA GeForce RTX 4090", 0.69)
    sessions.update_session(engine, session_id, jobs=1)
    sessions.close_session(engine, session_id, "deleted_idle")
    [listed] = client.get("/admin/offload").json()["pod_sessions"]
    assert listed["pod_id"] == "pod7" and listed["jobs"] == 1 and listed["outcome"] == "deleted_idle"
    assert listed["cost_usd"] is not None


# --- availability (render-gpu-availability) ---------------------------------------------------------------


def test_pod_mode_summary_carries_both_periods_and_the_sampling_switch(client: TestClient, runpod) -> None:
    body = client.get("/admin/offload").json()
    assert set(body["availability"]) == {"7", "30"}
    assert body["availability"]["7"]["samples"] == 0 and body["availability"]["7"]["any_in_stock_share"] is None
    assert body["stock_sampling"] is True


def test_the_sampling_switch_is_stored(client: TestClient, runpod) -> None:
    response = client.put("/admin/offload/sampling", json={"on": False})
    assert response.status_code == 200 and response.json()["stock_sampling"] is False
    assert client.get("/admin/offload").json()["stock_sampling"] is False
    assert client.put("/admin/offload/sampling", json={"on": "maybe"}).status_code == 422


def test_host_mode_has_no_availability(client: TestClient) -> None:
    configure(client)
    body = client.get("/admin/offload").json()
    assert body["availability"] is None and body["stock_sampling"] is None


def test_the_sampling_switch_needs_the_developer_gate(migrated_database: str, render_root: Path, fake_blender: Path) -> None:
    c = dev_client(migrated_database, render_root, fake_blender, dev=True)
    try:
        assert c.put("/admin/offload/sampling", json={"on": False}).status_code == 401
    finally:
        c.__exit__(None, None, None)
