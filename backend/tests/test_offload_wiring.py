"""render-offload: finals go to the render server when chosen; refused, never moved, when it cannot be used."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.agent.tools.photoreal_detail import render_detail
from app.agent.tools.render_turntable import preview as render_preview
from app.agent.tools.render_turntable import run as render_run
from app.blender import storage
from app.db.models import RemoteRenderJob
from app.render import benchmark_store as store
from app.render.offload.runtime import OffloadRuntime
from tests.api_helpers import create, make_client, sign_in
from tests.blender_fakes import fake_pipeline_launch
from tests.offload_fakes import FakeServer
from tests.test_builder_tools import folder_of, made, wait_job
from tests.test_offload_job import CONFIG

HOST = "gpu.example.org"


def combined(server: FakeServer, local):
    """The launcher the app uses: ssh and scp go to the fake server, Blender to the fake pipeline."""

    async def launch(argv, cwd, timeout):
        if argv[0] in ("ssh", "scp"):
            return await server.launch(argv, cwd, timeout)
        return await local(argv, cwd, timeout)

    return launch


def clear_offload(engine) -> None:
    with Session(engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'offload:%'"))
        session.execute(delete(RemoteRenderJob))
        session.commit()


def choose_remote(engine, *, benchmark: bool = True) -> None:
    store.write_final_target(engine, "remote")
    if benchmark:
        store.write_remote_benchmark(engine, 0.2, 40.0)


def local_renders(calls: list[list[str]]) -> list[list[str]]:
    return [c for c in calls if any(p.endswith(("render_turntable.py", "render_still.py")) for p in c)]


@pytest.fixture
def server(tmp_path: Path) -> FakeServer:
    return FakeServer(tmp_path / "server")


@pytest.fixture
def remote_state(tool_state, server: FakeServer) -> Iterator:
    clear_offload(tool_state.engine)
    tool_state.offload = OffloadRuntime(CONFIG)
    tool_state.blender_launch = combined(server, fake_pipeline_launch(calls=tool_state.launched))
    yield tool_state
    clear_offload(tool_state.engine)


def final_args(**fields):
    return {"package_id": "bench", "tier": "final", "kind": "turntable", **fields}


# --- the agent's render tools ----------------------------------------------------------------------------


def test_the_builder_sends_no_piece_final_to_the_server(make_ctx, remote_state, server: FakeServer) -> None:
    """rooms-only-renders: the Builder renders rooms; a piece final is refused before the server is asked."""
    from plugins.render_turntable.tool import PIECE_REFUSED

    made(make_ctx, remote_state)
    choose_remote(remote_state.engine)
    server.calls.clear()
    assert render_preview(final_args(), make_ctx()) == PIECE_REFUSED
    assert render_run(final_args(), replace(make_ctx(), approved=True)) == PIECE_REFUSED
    assert server.calls == [] and local_renders(remote_state.launched) == []


def test_a_detail_final_goes_to_the_server_too(make_ctx, remote_state, server: FakeServer) -> None:
    from app.agent.tools.photoreal_detail import start_detail_pass
    from tests.live_helpers import FakeBlender

    made(make_ctx, remote_state)
    remote_state.live_blender = FakeBlender()
    start_detail_pass.run({}, replace(make_ctx(package_id="bench"), approved=True))
    choose_remote(remote_state.engine)
    result = render_detail.run(
        {"tier": "final", "kind": "still"}, replace(make_ctx(package_id="bench"), approved=True)
    )
    assert result.startswith("Started a final still of the detailed bench")
    wait_job(folder_of(remote_state), "detail-still")
    assert (storage.detail_dir(folder_of(remote_state)) / "still.png").is_file()
    assert local_renders(remote_state.launched) == []


# --- the render route ----------------------------------------------------------------------------------------


@pytest.fixture
def client(migrated_database: str, render_root: Path, fake_blender: Path, server: FakeServer) -> Iterator[TestClient]:
    calls: list[list[str]] = []
    c = make_client(migrated_database, render_root, fake_blender, fake_pipeline_launch(calls=calls))
    sign_in(c)
    clear_offload(c.app.state.engine)
    store.write_benchmark(c.app.state.engine, 2.5, blender_version="5.2.1 LTS")
    c.app.state.offload = OffloadRuntime(CONFIG)
    c.app.state.blender_launch = combined(server, fake_pipeline_launch(calls=calls))
    c.app.state.local_calls = calls
    assert create(c).status_code == 202
    calls.clear()
    yield c
    clear_offload(c.app.state.engine)
    c.__exit__(None, None, None)


BASE = "/packages/hall-bench/versions/1"


def test_a_remote_final_over_http_quotes_asks_then_runs_on_the_server(
    client: TestClient, server: FakeServer, render_root: Path
) -> None:
    choose_remote(client.app.state.engine)
    asked = client.post(f"{BASE}/renders", json={"kind": "turntable", "tier": "final"})
    assert asked.status_code == 409 and asked.json()["detail"]["failure_class"] == "approval_required"
    assert "on the render server" in asked.json()["detail"]["summary"]
    assert asked.json()["detail"]["estimate"] == "about 56 seconds"
    assert local_renders(client.app.state.local_calls) == []

    token = asked.json()["detail"]["approval_token"]
    ok = client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
    assert ok.status_code == 202
    folder = render_root / "hall-bench" / "v1"
    assert len(list((folder / "frames").iterdir())) == 36
    assert server.job_folders() == [] and local_renders(client.app.state.local_calls) == []
    with Session(client.app.state.engine) as session:
        [job] = session.scalars(select(RemoteRenderJob)).all()
    assert (job.package_id, job.render_key, job.outcome) == ("hall-bench", "turntable", "succeeded")
    assert job.transfer_seconds is not None and job.estimate_seconds == pytest.approx(36 * 2.25 * 0.2 + 40)
    assert store.read_remote_benchmark(client.app.state.engine).calibrated is True
    assert store.stored_cycles_multiplier(client.app.state.engine) is None


def test_a_remote_final_over_http_without_the_remote_benchmark_is_refused(client: TestClient) -> None:
    choose_remote(client.app.state.engine, benchmark=False)
    response = client.post(f"{BASE}/renders", json={"kind": "turntable", "tier": "final"})
    assert response.status_code == 409 and "remote benchmark must be run first" in response.json()["detail"]["reason"]


def test_the_target_local_keeps_a_final_over_http_on_the_laptop(client: TestClient, server: FakeServer) -> None:
    store.write_final_target(client.app.state.engine, "local")
    asked = client.post(f"{BASE}/renders", json={"kind": "turntable", "tier": "final"})
    assert "render server" not in asked.json()["detail"]["summary"]
    assert server.calls == []


def test_a_remote_final_over_http_is_refused_with_503_before_any_approval(
    client: TestClient, tmp_path: Path
) -> None:
    bad = FakeServer(tmp_path / "bad", reachable=False)
    client.app.state.blender_launch = combined(bad, fake_pipeline_launch())
    choose_remote(client.app.state.engine)
    response = client.post(f"{BASE}/renders", json={"kind": "turntable", "tier": "final"})
    assert response.status_code == 503
    assert response.json()["detail"]["failure_class"] == "offload_unreachable"
    assert "approval_token" not in response.text
    assert local_renders(client.app.state.local_calls) == []


def test_an_unconfigured_server_over_http_is_503_not_a_laptop_render(client: TestClient) -> None:
    client.app.state.offload = None
    choose_remote(client.app.state.engine)
    response = client.post(f"{BASE}/renders", json={"kind": "turntable", "tier": "final"})
    assert response.status_code == 503 and "not configured" in response.json()["detail"]["reason"]


def test_a_draft_over_http_stays_local(client: TestClient, server: FakeServer) -> None:
    choose_remote(client.app.state.engine)
    assert client.post(f"{BASE}/renders", json={"kind": "still", "tier": "draft"}).status_code == 202
    assert server.calls == [] and local_renders(client.app.state.local_calls)


def test_no_homeowner_response_names_the_server_or_the_target(client: TestClient) -> None:
    choose_remote(client.app.state.engine)
    asked = client.post(f"{BASE}/renders", json={"kind": "still", "tier": "final"})
    token = asked.json()["detail"]["approval_token"]
    client.post(f"{BASE}/renders/approve", json={"approval_token": token, "confirm": "yes"})
    store.write_hourly_rate(client.app.state.engine, 1.8)
    texts = [
        asked.text,
        client.get(BASE).text,
        client.get(f"{BASE}/files/status.json").text,
        client.get(f"{BASE}/renders").text,
        client.get("/packages").text,
    ]
    for text_ in texts:
        for secret in (HOST, "render@", "gpu.", "cost_eur", "hourly", "OPTIX", "id_ed25519"):
            assert secret not in text_, secret


# --- no render GPU in stock (render-gpu-availability) ---------------------------------------------------


def sold_out_runtime():
    """Pod mode with no pod running and nothing in stock in the volume's data centre."""
    from dataclasses import replace as replaced

    from pydantic import SecretStr

    from app.render.offload.pod import PodManager, PodSettings
    from app.render.offload.runpod import RunPodClient
    from tests.offload_fakes import FakeRunPod

    fake = FakeRunPod(catalog={"NVIDIA RTX A4500": {"EU-RO-1": "NONE"}})
    runtime = OffloadRuntime(replaced(CONFIG, host="", host_key_alias="hra-render-pod"))
    runtime.pod = PodManager(
        client=RunPodClient(SecretStr("rpa_SECRETKEYVALUE"), transport=fake.transport),
        settings=PodSettings(("NVIDIA RTX A4500", "NVIDIA GeForce RTX 4090"), "runpod/base:0.6.2", "vol123"),
        template=runtime.config, semaphore=runtime.semaphore,
    )
    return fake, runtime


def test_a_final_with_no_render_gpu_in_stock_is_503_over_http(client: TestClient) -> None:
    fake, client.app.state.offload = sold_out_runtime()
    choose_remote(client.app.state.engine)
    response = client.post(f"{BASE}/renders", json={"kind": "turntable", "tier": "final"})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["failure_class"] == "offload_no_stock" and "EU-RO-1" in detail["reason"]
    assert "approval_token" not in response.text and "rpa_" not in response.text
    assert fake.created == [] and local_renders(client.app.state.local_calls) == []
