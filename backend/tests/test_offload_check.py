"""render-offload: the check before a remote final is quoted, with a fake server."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.blender.launch import LaunchResult
from app.render.guard import RenderRefused
from app.render.offload.check import OffloadChecker
from app.render.offload.runtime import OffloadRuntime, ensure_server
from app.render.offload.transport import OffloadConfig
from tests.offload_fakes import FakeServer

CONFIG = OffloadConfig(
    host="gpu.example.org", port=22, user="render", key_path=Path("/k/id"),
    known_hosts_path=Path("/k/known"), blender="/opt/blender-5.2.1/blender", device="OPTIX",
)


def check(server: FakeServer, checker: OffloadChecker | None = None) -> None:
    asyncio.run((checker or OffloadChecker()).check(CONFIG, server.launch))


def test_a_reachable_server_with_the_pinned_blender_passes(tmp_path: Path) -> None:
    server = FakeServer(tmp_path)
    check(server)
    [argv] = server.calls
    assert argv[0] == "ssh" and "StrictHostKeyChecking=yes" in argv
    assert "/opt/blender-5.2.1/blender --version" in argv[-1]


def test_a_success_is_remembered_for_a_minute(tmp_path: Path) -> None:
    now = [100.0]
    checker = OffloadChecker(clock=lambda: now[0])
    server = FakeServer(tmp_path)
    check(server, checker)
    now[0] += 59
    check(server, checker)
    assert len(server.calls) == 1
    now[0] += 2
    check(server, checker)
    assert len(server.calls) == 2


@pytest.mark.parametrize(
    ("server", "fragment"),
    [
        ({"reachable": False}, "unreachable"),
        ({"version": "Blender 4.5.0 LTS"}, "runs Blender 4.5.0, not the pinned 5.2.1"),
        ({"version": "something else"}, "did not report a version"),
    ],
)
def test_a_server_that_fails_the_check_is_refused_with_a_reason_and_not_remembered(
    tmp_path: Path, server: dict, fragment: str
) -> None:
    fake = FakeServer(tmp_path, **server)
    checker = OffloadChecker()
    with pytest.raises(RenderRefused, match=fragment) as caught:
        check(fake, checker)
    assert "switch final renders to the laptop" in caught.value.reason
    with pytest.raises(RenderRefused):
        check(fake, checker)
    assert len(fake.calls) == 2


def test_a_host_key_that_is_not_in_the_known_hosts_file_is_unreachable(tmp_path: Path) -> None:
    async def refused(argv, cwd, timeout):
        return LaunchResult(255, "Host key verification failed.", False)

    with pytest.raises(RenderRefused, match="unreachable"):
        asyncio.run(OffloadChecker().check(CONFIG, refused))


def test_a_timeout_is_unreachable(tmp_path: Path) -> None:
    async def slow(argv, cwd, timeout):
        assert timeout <= 10
        return LaunchResult(-1, "timed out after 10 seconds", True)

    with pytest.raises(RenderRefused, match="unreachable"):
        asyncio.run(OffloadChecker().check(CONFIG, slow))


def test_blender_missing_at_the_configured_path_is_refused_with_its_own_reason(tmp_path: Path) -> None:
    async def missing(argv, cwd, timeout):
        return LaunchResult(127, "sh: 1: /opt/blender: not found", False)

    with pytest.raises(RenderRefused, match="could not run Blender"):
        asyncio.run(OffloadChecker().check(CONFIG, missing))


def test_an_unconfigured_server_is_refused_never_replaced_by_the_laptop(tmp_path: Path) -> None:
    server = FakeServer(tmp_path)
    with pytest.raises(RenderRefused, match="not configured") as caught:
        asyncio.run(ensure_server(None, server.launch))
    assert caught.value.failure_class == "offload_not_configured"
    assert server.calls == []


def test_ensure_server_uses_the_runtimes_checker(tmp_path: Path) -> None:
    server = FakeServer(tmp_path, version="Blender 4.5.0")
    with pytest.raises(RenderRefused, match="4.5.0"):
        asyncio.run(ensure_server(OffloadRuntime(CONFIG), server.launch))


# --- pod mode (render-pod-lifecycle) ---------------------------------------------------------------


def pod_runtime(fake_runpod, key: str = "rpa_SECRETKEYVALUE") -> OffloadRuntime:
    from dataclasses import replace

    from pydantic import SecretStr

    from app.render.offload.pod import PodManager, PodSettings
    from app.render.offload.runpod import RunPodClient

    runtime = OffloadRuntime(replace(CONFIG, host="", host_key_alias="hra-render-pod"))
    runtime.pod = PodManager(
        client=RunPodClient(SecretStr(key), transport=fake_runpod.transport),
        settings=PodSettings(("NVIDIA GeForce RTX 4090",), "runpod/base:0.6.2", "vol123"),
        template=runtime.config, semaphore=runtime.semaphore,
    )
    return runtime


def test_pod_mode_with_nothing_running_checks_runpod_and_creates_nothing(tmp_path: Path) -> None:
    from tests.offload_fakes import FakeRunPod

    fake, server = FakeRunPod(), FakeServer(tmp_path)
    asyncio.run(ensure_server(pod_runtime(fake), server.launch))
    assert [request.url.path for request in fake.requests] == ["/v1/networkvolumes/vol123"]
    assert fake.created == [] and server.calls == []


def test_a_rejected_runpod_key_refuses_before_approval_without_the_key(tmp_path: Path) -> None:
    from tests.offload_fakes import FakeRunPod

    fake = FakeRunPod()
    with pytest.raises(RenderRefused) as caught:
        asyncio.run(ensure_server(pod_runtime(fake, key="rpa_WRONGKEYVALUE"), FakeServer(tmp_path).launch))
    assert caught.value.reason.startswith("RunPod rejected the API key")
    assert "laptop" in caught.value.reason and "rpa_" not in caught.value.reason
    assert fake.created == []


def test_a_missing_volume_refuses_before_approval(tmp_path: Path) -> None:
    from tests.offload_fakes import FakeRunPod

    with pytest.raises(RenderRefused, match="network volume was not found"):
        asyncio.run(ensure_server(pod_runtime(FakeRunPod(volume_id="other")), FakeServer(tmp_path).launch))


def test_a_running_pod_is_checked_over_ssh(tmp_path: Path) -> None:
    from tests.offload_fakes import FakeRunPod

    fake, server = FakeRunPod(), FakeServer(tmp_path)
    runtime = pod_runtime(fake)
    runtime.pod.state = "running"
    runtime.pod.connection = runtime.config.for_pod("203.0.113.7", 10341)
    asyncio.run(ensure_server(runtime, server.launch))
    [argv] = server.calls
    assert "HostKeyAlias=hra-render-pod" in argv and "render@203.0.113.7" in argv
    assert argv[argv.index("-p") + 1] == "10341" and fake.requests == []

