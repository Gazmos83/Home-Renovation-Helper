"""render-pod-lifecycle: the pod is created after approval and deleted when idle.

RunPod is answered in memory (`FakeRunPod`), SSH by a fake launcher, and time by a
clock the test moves, so no test waits and none touches the network.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.blender.launch import LaunchResult
from app.db.session import make_engine
from app.render import benchmark_store
from app.render.offload import sessions
from app.render.offload.job import RemoteFailed
from app.render.offload.pod import HOST_KEY_MISMATCH, PodBusy, PodManager, PodSettings
from app.render.offload.runpod import RunPodClient
from app.render.offload.transport import OffloadConfig
from tests.offload_fakes import FakeRunPod

START = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
TEMPLATE = OffloadConfig(
    host="", port=22, user="root", key_path=Path("/k/id"), known_hosts_path=Path("/k/known"),
    blender="/workspace/blender-5.2.1-linux-x64/blender", device="OPTIX", host_key_alias="hra-render-pod",
)
SETTINGS = PodSettings(gpu_types=("NVIDIA GeForce RTX 4090",), image="runpod/base:0.6.2", volume_id="vol123")


class Clock:
    """`now` and `sleep` for the manager. Sleeps wait until the test moves the clock,
    except while `auto` is on, when they move it themselves (a pod starting)."""

    def __init__(self) -> None:
        self.t = START
        self.auto = True
        self._waiting: list[tuple[datetime, asyncio.Future]] = []

    def now(self) -> datetime:
        return self.t

    async def sleep(self, seconds: float) -> None:
        if self.auto:
            self.t += timedelta(seconds=seconds)
            await asyncio.sleep(0)
            return
        future = asyncio.get_running_loop().create_future()
        self._waiting.append((self.t + timedelta(seconds=seconds), future))
        await future

    async def to(self, when: datetime) -> None:
        self.t = when
        for _ in range(20):
            due = [(at, f) for at, f in self._waiting if at <= self.t and not f.done()]
            if not due:
                await asyncio.sleep(0)
                continue
            for at, future in due:
                self._waiting.remove((at, future))
                future.set_result(None)
            await asyncio.sleep(0)


def at(minutes: float) -> datetime:
    return START + timedelta(minutes=minutes)


def ssh(version: str = "Blender 5.2.1 LTS", *, refuse: int = 0, stderr: str | None = None):
    """A launcher answering `blender --version`; the first `refuse` calls cannot connect."""
    calls: list[list[str]] = []

    async def launch(argv, cwd, timeout):
        calls.append(argv)
        if stderr is not None:
            return LaunchResult(255, stderr, False)
        if len(calls) <= refuse:
            return LaunchResult(255, "ssh: connect to host port 10341: Connection refused", False)
        return LaunchResult(0, version, False)

    launch.calls = calls  # type: ignore[attr-defined]
    return launch


def manager(fake: FakeRunPod, clock: Clock, *, engine=None, semaphore=None) -> PodManager:
    return PodManager(
        client=RunPodClient(SecretStr("rpa_SECRETKEYVALUE"), transport=fake.transport),
        settings=SETTINGS, template=TEMPLATE, semaphore=semaphore or asyncio.Semaphore(1),
        engine=engine, now=clock.now, sleep=clock.sleep,
    )


def test_the_first_final_creates_one_pod_and_connects_to_it() -> None:
    async def scenario():
        fake, clock = FakeRunPod(ready_after=3), Clock()
        pods = manager(fake, clock)
        connection = await pods.ensure_pod(ssh(refuse=1))
        return fake, pods, connection

    fake, pods, connection = asyncio.run(scenario())
    [body] = fake.created
    assert body["networkVolumeId"] == "vol123" and body["dataCenterIds"] == ["EU-RO-1"]
    assert connection.host == "203.0.113.7" and connection.port == 10341
    assert connection.host_key_alias == "hra-render-pod"
    assert pods.state == "running" and pods.status()["pod_id"] == "pod1"


def test_a_running_pod_is_reused() -> None:
    async def scenario():
        fake, clock = FakeRunPod(), Clock()
        pods = manager(fake, clock)
        first = await pods.ensure_pod(ssh())
        pods.job_finished(idle_minutes=10)
        second = await pods.ensure_pod(ssh())
        return fake, pods, first, second

    fake, pods, first, second = asyncio.run(scenario())
    assert len(fake.created) == 1 and first == second
    assert pods.delete_at is None  # the idle time stops while the pod is in use again


def test_no_free_gpu_fails_the_job_and_leaves_no_pod() -> None:
    fake = FakeRunPod(no_capacity=True)
    pods = manager(fake, Clock())
    with pytest.raises(RemoteFailed) as caught:
        asyncio.run(pods.ensure_pod(ssh()))
    assert caught.value.reason == "no NVIDIA GeForce RTX 4090 is free on RunPod right now"
    assert pods.state == "none" and fake.pods == {}


def test_a_pod_that_never_answers_is_deleted_after_ten_minutes() -> None:
    fake, clock = FakeRunPod(), Clock()
    pods = manager(fake, clock)
    with pytest.raises(RemoteFailed, match="did not answer within 10 minutes"):
        asyncio.run(pods.ensure_pod(ssh(refuse=10_000)))
    assert fake.deleted == ["pod1"] and fake.pods == {} and pods.state == "none"
    assert clock.t - START >= timedelta(minutes=10)


def test_a_pod_runpod_never_starts_is_deleted_after_three_minutes() -> None:
    fake, clock = FakeRunPod(ready_after=10_000), Clock()
    pods = manager(fake, clock)
    with pytest.raises(RemoteFailed, match="RunPod did not start the render pod within 3 minutes"):
        asyncio.run(pods.ensure_pod(ssh()))
    assert fake.deleted == ["pod1"] and fake.pods == {} and pods.state == "none"
    assert timedelta(minutes=3) <= clock.t - START < timedelta(minutes=4)


def test_a_pod_with_an_address_keeps_the_full_ten_minutes_for_ssh() -> None:
    fake, clock = FakeRunPod(ready_after=1), Clock()
    pods = manager(fake, clock)
    with pytest.raises(RemoteFailed, match="did not answer within 10 minutes"):
        asyncio.run(pods.ensure_pod(ssh(refuse=10_000)))
    assert clock.t - START >= timedelta(minutes=10)


def test_a_changed_host_key_fails_at_once_and_deletes_the_pod() -> None:
    fake, clock = FakeRunPod(), Clock()
    pods = manager(fake, clock)
    with pytest.raises(RemoteFailed) as caught:
        asyncio.run(pods.ensure_pod(ssh(stderr="Host key verification failed.")))
    assert caught.value.reason == HOST_KEY_MISMATCH
    assert fake.deleted == ["pod1"] and clock.t - START < timedelta(minutes=1)


def test_the_wrong_blender_fails_and_deletes_the_pod() -> None:
    fake = FakeRunPod()
    pods = manager(fake, Clock())
    with pytest.raises(RemoteFailed, match="Blender 4.5.0"):
        asyncio.run(pods.ensure_pod(ssh("Blender 4.5.0")))
    assert fake.deleted == ["pod1"]


def test_an_idle_pod_is_deleted_when_the_idle_time_ends() -> None:
    async def scenario():
        fake, clock = FakeRunPod(), Clock()
        pods = manager(fake, clock)
        await pods.ensure_pod(ssh())
        clock.t, clock.auto = START, False
        pods.job_finished(idle_minutes=10)
        await clock.to(at(9))
        alive_at_nine = dict(fake.pods)
        await clock.to(at(10))
        return fake, pods, alive_at_nine

    fake, pods, alive_at_nine = asyncio.run(scenario())
    assert "pod1" in alive_at_nine
    assert fake.deleted == ["pod1"] and pods.state == "none"


def test_a_job_during_the_idle_time_postpones_the_delete() -> None:
    async def scenario():
        fake, clock = FakeRunPod(), Clock()
        pods = manager(fake, clock)
        await pods.ensure_pod(ssh())
        clock.t, clock.auto = START, False
        pods.job_finished(idle_minutes=10)  # a final ends at 14:00
        await clock.to(at(6))
        await pods.ensure_pod(ssh())  # another starts at 14:06
        await clock.to(at(12))
        pods.job_finished(idle_minutes=10)  # and ends at 14:12
        await clock.to(at(10.5))
        kept = list(fake.deleted)
        await clock.to(at(22))
        return fake, kept

    fake, kept = asyncio.run(scenario())
    assert kept == [] and fake.deleted == ["pod1"]


def test_the_pod_is_never_deleted_under_a_running_job() -> None:
    async def scenario():
        fake, clock = FakeRunPod(), Clock()
        lock = asyncio.Semaphore(1)
        pods = manager(fake, clock, semaphore=lock)
        await pods.ensure_pod(ssh())
        clock.t, clock.auto = START, False
        pods.job_finished(idle_minutes=10)
        await lock.acquire()  # something holds the server's lock past the idle time
        await clock.to(at(10))
        held = list(fake.deleted)
        lock.release()
        await clock.to(at(11))
        return fake, held

    fake, held = asyncio.run(scenario())
    assert held == [] and fake.deleted == ["pod1"]


def test_a_failed_delete_is_retried_a_minute_later_and_shown() -> None:
    async def scenario():
        fake, clock = FakeRunPod(delete_fails=1), Clock()
        pods = manager(fake, clock)
        await pods.ensure_pod(ssh())
        clock.t, clock.auto = START, False
        pods.job_finished(idle_minutes=10)
        await clock.to(at(10))
        shown = pods.status()
        await clock.to(at(11))
        return fake, pods, shown

    fake, pods, shown = asyncio.run(scenario())
    assert shown["state"] == "delete_failed" and "did not delete" in shown["error"]
    assert fake.deleted == ["pod1"] and pods.state == "none"


def test_delete_now_is_refused_while_a_job_runs() -> None:
    async def scenario():
        fake, clock = FakeRunPod(), Clock()
        lock = asyncio.Semaphore(1)
        pods = manager(fake, clock, semaphore=lock)
        await pods.ensure_pod(ssh())
        async with lock:
            with pytest.raises(PodBusy):
                await pods.delete_now()
        await pods.delete_now()
        return fake, pods

    fake, pods = asyncio.run(scenario())
    assert fake.deleted == ["pod1"] and pods.state == "none"


def test_startup_deletes_only_app_named_pods() -> None:
    fake = FakeRunPod()
    mine = fake.add_pod("hra-render")
    other = fake.add_pod("someone-else")
    asyncio.run(manager(fake, Clock()).startup_cleanup())
    assert fake.deleted == [mine] and other in fake.pods


def test_shutdown_deletes_the_idle_pod() -> None:
    async def scenario():
        fake, clock = FakeRunPod(), Clock()
        pods = manager(fake, clock)
        await pods.ensure_pod(ssh())
        pods.job_finished(idle_minutes=10)
        await pods.shutdown()
        return fake

    assert asyncio.run(scenario()).deleted == ["pod1"]


# --- records -----------------------------------------------------------------------------------------


@pytest.fixture
def engine(migrated_database: str) -> Iterator:
    engine = make_engine(migrated_database)

    def clear() -> None:
        with Session(engine) as session:
            session.execute(text("DELETE FROM render_pod_sessions"))
            session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'offload:%'"))
            session.commit()

    clear()
    yield engine
    clear()
    engine.dispose()


def test_a_session_records_start_up_jobs_and_idle_deletion(engine) -> None:
    async def scenario():
        fake, clock = FakeRunPod(ready_after=4), Clock()
        pods = manager(fake, clock, engine=engine)
        await pods.ensure_pod(ssh())
        pods.job_finished(idle_minutes=10)
        await pods.ensure_pod(ssh())
        pods.job_finished(idle_minutes=10)
        await pods.delete_now()

    asyncio.run(scenario())
    assert benchmark_store.read_boot_seconds(engine) == 15.0  # three address polls of five seconds
    with Session(engine) as db:
        [row] = sessions.recent_sessions(db)
    assert row["jobs"] == 2 and row["outcome"] == "deleted_manual" and row["ready_at"] is not None
    assert row["cost_per_hr"] == 0.69


def test_a_failed_start_is_recorded(engine) -> None:
    fake = FakeRunPod()
    with pytest.raises(RemoteFailed):
        asyncio.run(manager(fake, Clock(), engine=engine).ensure_pod(ssh("Blender 4.5.0")))
    with Session(engine) as db:
        [row] = sessions.recent_sessions(db)
    assert row["outcome"] == "start_failed" and "4.5.0" in row["error"]


def test_an_orphan_found_at_startup_is_recorded(engine) -> None:
    fake = FakeRunPod()
    fake.add_pod("hra-render")
    asyncio.run(manager(fake, Clock(), engine=engine).startup_cleanup())
    with Session(engine) as db:
        [row] = sessions.recent_sessions(db)
    assert row["outcome"] == "orphaned"


def test_when_the_first_choice_is_sold_out_the_next_is_used_and_recorded(engine) -> None:
    from dataclasses import replace

    async def scenario():
        fake = FakeRunPod(stock={"NVIDIA GeForce RTX 5090"})
        pods = manager(fake, Clock(), engine=engine)
        pods.settings = replace(SETTINGS, gpu_types=("NVIDIA RTX A4500", "NVIDIA GeForce RTX 5090"))
        await pods.ensure_pod(ssh())
        return fake

    fake = asyncio.run(scenario())
    assert fake.created[0]["gpuTypeIds"] == ["NVIDIA RTX A4500", "NVIDIA GeForce RTX 5090"]
    with Session(engine) as db:
        [row] = sessions.recent_sessions(db)
    assert row["gpu_type"] == "NVIDIA GeForce RTX 5090"
