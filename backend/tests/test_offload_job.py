"""render-offload: a remote final, end to end through `run_render`, with a fake server."""

from __future__ import annotations

import asyncio
import json
import tarfile
from pathlib import Path

import pytest

from app.blender import storage
from app.blender.runner import run_render
from app.render.benchmark_store import Benchmark, RemoteBenchmark
from app.render.guard import RenderNotAuthorised, authorise
from app.render.offload.runtime import OffloadRuntime
from app.render.offload.transport import OffloadConfig
from tests.blender_fakes import fake_success_launch
from tests.offload_fakes import FakeServer
from tests.test_runner import TIERS, new_version, render_writer

CONFIG = OffloadConfig(
    host="gpu.example.org", port=22, user="render", key_path=Path("/keys/id_ed25519"),
    known_hosts_path=Path("/keys/known"), blender="/opt/blender-5.2.1/blender", device="OPTIX",
)
BIN = Path("/fake/blender")


def final_ticket(kind="turntable", *, version=1, room=False, source="model", target="remote"):
    return authorise(
        package_id="desk", version=version, kind=kind, tier="final", tiers=TIERS,
        benchmark=Benchmark(2.5, "t"), room=room, approval="yes", source=source, target=target,
        remote_benchmark=RemoteBenchmark(0.2, 40.0, "t"),
    )


def go(root: Path, ticket, server: FakeServer, *, local=None, runtime=None, **kwargs):
    runtime = runtime or OffloadRuntime(CONFIG)
    return run_render(
        ticket, root=root, blender_bin=BIN, timeout=60, semaphore=asyncio.Semaphore(1),
        launch=server.launch if local is None else local, offload=runtime, **kwargs,
    )


def run(coro):
    return asyncio.run(coro)


def job_of(folder: Path) -> dict:
    return storage.read_status(folder)["renders"]["turntable"]


def test_a_final_turntable_on_the_server_publishes_36_frames_and_cleans_up(
    render_root: Path, tmp_path: Path
) -> None:
    folder = new_version(render_root, built=True)
    server = FakeServer(tmp_path / "server")
    finished: list[tuple[float, float]] = []
    jobs: list[dict] = []
    run(go(render_root, final_ticket(), server,
           on_finished=lambda quote, seconds: finished.append((quote.estimate_seconds, seconds)),
           on_remote_job=jobs.append))

    frames = sorted(p.name for p in (folder / "frames").iterdir())
    assert frames == [f"frame_{i:03d}.png" for i in range(36)]
    assert job_of(folder)["status"] == "succeeded" and job_of(folder)["tier"] == "final"
    assert server.job_folders() == []                     # the job folder is gone
    assert [p for p in folder.iterdir() if p.name.startswith(".")] == []
    # The generator ran with the tier's values and the server's GPU, and nothing else.
    [command] = server.render_commands
    for expected in ("--tier-frames 36", "--tier-resolution 1500", "--tier-engine CYCLES",
                     "--cycles-device OPTIX", "--blend input.blend", "--out out", "timeout -k 10"):
        assert expected in command
    # The viewer was written here, not copied from the server.
    viewer = (folder / "viewer.html").read_text(encoding="utf-8")
    assert "SERVER VIEWER" not in viewer and "36" in viewer
    # The records.
    [job] = jobs
    assert job["outcome"] == "succeeded" and job["transfer_seconds"] is not None
    assert job["actual_seconds"] >= job["transfer_seconds"] >= 0
    assert finished and finished[0][1] <= job["actual_seconds"]


def test_a_final_still_on_the_server(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    run(go(render_root, final_ticket("still"), FakeServer(tmp_path / "s")))
    assert (folder / "still.png").is_file()
    assert storage.read_status(folder)["renders"]["still"]["status"] == "succeeded"


def test_nothing_runs_on_the_laptop_for_a_remote_final(render_root: Path, tmp_path: Path) -> None:
    new_version(render_root, built=True)
    server = FakeServer(tmp_path / "s")
    run(go(render_root, final_ticket(), server))
    assert {argv[0] for argv in server.calls} == {"ssh", "scp"}
    assert all(str(BIN) not in argv for argv in server.calls)


def test_every_call_is_key_only_and_carries_no_key_material(render_root: Path, tmp_path: Path) -> None:
    new_version(render_root, built=True)
    server = FakeServer(tmp_path / "s")
    run(go(render_root, final_ticket(), server))
    for argv in server.calls:
        assert "BatchMode=yes" in argv and "StrictHostKeyChecking=yes" in argv
        assert "-i" in argv and "/keys/id_ed25519" in argv
        assert not any("PRIVATE" in part for part in argv)


def test_the_archive_holds_the_bundle_and_the_model_only(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    (folder / "model.blend").write_bytes(b"BLENDER-model")
    captured: list[list[str]] = []

    class Spy(FakeServer):
        async def launch(self, argv, cwd, timeout):
            if argv[0] == "scp" and argv[-1].endswith("bundle.tar.gz"):
                with tarfile.open(argv[-2]) as archive:
                    captured.append(archive.getnames())
            return await super().launch(argv, cwd, timeout)

    run(go(render_root, final_ticket(), Spy(tmp_path / "s")))
    [names] = captured
    assert "input.blend" in names
    assert "backend/app/blender/generators/render_turntable.py" in names
    assert "backend/app/render/viewer.html" in names
    assert not any(n.startswith(("backend/app/db", "backend/app/agent", "backend/app/api")) for n in names)
    assert not any(n.endswith(("spec.json", "cutlist.csv")) for n in names)


def test_a_detail_final_uploads_the_detail_copy(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    copy = storage.detail_blend_path(folder)
    copy.parent.mkdir()
    copy.write_bytes(b"BLENDER-detail")
    uploaded: list[bytes] = []

    class Spy(FakeServer):
        async def launch(self, argv, cwd, timeout):
            if argv[0] == "scp" and argv[-1].endswith("bundle.tar.gz"):
                with tarfile.open(argv[-2]) as archive:
                    uploaded.append(archive.extractfile("input.blend").read())
            return await super().launch(argv, cwd, timeout)

    run(go(render_root, final_ticket(source="detail"), Spy(tmp_path / "s")))
    assert uploaded == [b"BLENDER-detail"]
    assert (storage.detail_dir(folder) / "frames" / "frame_035.png").is_file()


def test_a_room_final_uploads_the_package_and_the_room_document(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    (folder / "model.glb").write_bytes(b"glTF....")
    (folder / "spec.json").write_text("{}", encoding="utf-8")
    seen: dict[str, object] = {}

    class Spy(FakeServer):
        async def launch(self, argv, cwd, timeout):
            if argv[0] == "scp" and argv[-1].endswith("bundle.tar.gz"):
                with tarfile.open(argv[-2]) as archive:
                    seen["names"] = archive.getnames()
                    seen["scene"] = json.loads(archive.extractfile("scene.json").read())
            return await super().launch(argv, cwd, timeout)

    run(go(render_root, final_ticket("still", room=True), Spy(tmp_path / "s"),
           scene_document={"marker": "room-doc", "output": {"kind": "still"}}))
    assert "package/model.glb" in seen["names"] and "package/spec.json" in seen["names"]
    assert seen["scene"]["marker"] == "room-doc"


# --- failures: nothing published, the server is cleaned, never a local fallback ----------------------


def test_a_missing_frame_after_transfer_fails_naming_it_and_publishes_nothing(
    render_root: Path, tmp_path: Path
) -> None:
    folder = new_version(render_root, built=True)
    server = FakeServer(tmp_path / "s", omit_frame=20)
    run(go(render_root, final_ticket(), server))
    entry = job_of(folder)
    assert entry["status"] == "failed" and "frame_020.png" in entry["error"]
    assert not (folder / "frames").exists() and not (folder / "viewer.html").exists()
    assert server.job_folders() == []
    assert [p for p in folder.iterdir() if p.name.startswith(".")] == []


def test_a_timeout_stops_the_job_reports_it_and_cleans_up(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    server = FakeServer(tmp_path / "s", hang_render=True)
    run(go(render_root, final_ticket(), server))
    assert job_of(folder)["status"] == "failed" and "exceeded" in job_of(folder)["error"]
    assert server.job_folders() == []


def test_a_render_failure_on_the_server_is_reported_and_cleaned(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    server = FakeServer(tmp_path / "s", fail_render="render: RuntimeError: out of memory")
    run(go(render_root, final_ticket(), server))
    assert "out of memory" in job_of(folder)["error"]
    assert server.job_folders() == []


def test_an_unreachable_server_fails_the_job_and_never_runs_it_locally(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    server = FakeServer(tmp_path / "s", reachable=False)
    run(go(render_root, final_ticket(), server))
    assert job_of(folder)["status"] == "failed"
    assert not (folder / "frames").exists()
    assert all(argv[0] in {"ssh", "scp"} for argv in server.calls)


def test_a_failed_upload_is_reported_and_cleaned(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    server = FakeServer(tmp_path / "s", fail_upload=True)
    run(go(render_root, final_ticket(), server))
    assert "could not be copied to the render server" in job_of(folder)["error"]
    assert server.job_folders() == []


def test_an_unexpected_file_from_the_server_is_refused(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    run(go(render_root, final_ticket(), FakeServer(tmp_path / "s", extra_file="run.sh")))
    assert "unexpected file: run.sh" in job_of(folder)["error"]
    assert not (folder / "frames").exists()


def test_a_link_from_the_server_is_refused(render_root: Path, tmp_path: Path) -> None:
    folder = new_version(render_root, built=True)
    run(go(render_root, final_ticket(), FakeServer(tmp_path / "s", symlink=True)))
    assert "link" in job_of(folder)["error"]
    assert not (folder / "frames").exists()


def test_a_remote_ticket_with_no_server_configured_fails_and_does_not_run_locally(
    render_root: Path,
) -> None:
    folder = new_version(render_root, built=True)
    calls: list[list[str]] = []
    run(run_render(
        final_ticket(), root=render_root, blender_bin=BIN, timeout=60, semaphore=asyncio.Semaphore(1),
        launch=fake_success_launch(render_writer, calls=calls), offload=None,
    ))
    assert "not configured" in job_of(folder)["error"]
    assert calls == []


def test_a_used_remote_ticket_is_refused(render_root: Path, tmp_path: Path) -> None:
    new_version(render_root, built=True)
    server = FakeServer(tmp_path / "s")
    ticket = final_ticket()
    run(go(render_root, ticket, server))
    with pytest.raises(RenderNotAuthorised):
        run(go(render_root, ticket, server))


# --- one job per machine ------------------------------------------------------------------------------


def test_two_remote_finals_never_overlap_and_the_second_reads_queued(render_root: Path, tmp_path: Path) -> None:
    first = new_version(render_root, built=True)
    second = new_version(render_root, version=2, built=True)
    server = FakeServer(tmp_path / "s", delay=0.3)
    runtime = OffloadRuntime(CONFIG)
    seen: list[str] = []

    async def both():
        a = asyncio.create_task(go(render_root, final_ticket(version=1), server, runtime=runtime))
        b = asyncio.create_task(go(render_root, final_ticket(version=2), server, runtime=runtime))
        await asyncio.sleep(0.1)
        seen.append(job_of(second)["status"] if "renders" in (storage.read_status(second) or {}) else "none")
        await asyncio.gather(a, b)

    from app.blender.runner import mark_render_queued

    mark_render_queued(first, final_ticket(version=1))
    mark_render_queued(second, final_ticket(version=2))
    run(both())
    assert server.max_active == 1
    assert seen == ["queued"]
    assert job_of(first)["status"] == job_of(second)["status"] == "succeeded"


def test_a_local_draft_runs_while_a_remote_final_renders(render_root: Path, tmp_path: Path) -> None:
    remote_folder = new_version(render_root, built=True)
    local_folder = new_version(render_root, package_id="other", built=True)
    server = FakeServer(tmp_path / "s", delay=0.6)
    order: list[str] = []

    async def local_launch(argv, cwd, timeout):
        order.append("local draft")
        return await fake_success_launch(render_writer)(argv, cwd, timeout)

    draft = authorise(
        package_id="other", version=1, kind="still", tier="draft", tiers=TIERS,
        benchmark=Benchmark(2.5, "t"), approval="yes",
    )

    async def both():
        remote = asyncio.create_task(go(render_root, final_ticket(), server))
        await asyncio.sleep(0.1)
        await run_render(
            draft, root=render_root, blender_bin=BIN, timeout=60, semaphore=asyncio.Semaphore(1),
            launch=local_launch,
        )
        order.append("draft done")
        assert not remote.done(), "the draft waited for the remote final"
        await remote
        order.append("final done")

    run(both())
    assert order == ["local draft", "draft done", "final done"]
    assert (local_folder / "still.png").is_file() and (remote_folder / "frames").is_dir()
