"""The RunPod pod's life: created after approval, deleted when idle (render-pod-lifecycle design decision 5).

At most one pod exists. `ensure_pod` runs inside the server's one-job lock, before
render time starts: it reuses a running pod or creates one from the network volume,
waits for an address, then retries the Blender version check over SSH until it
passes or the start-up limit is reached. A pod that fails to start is deleted and
the job fails with the reason; nothing ever falls back to the laptop.

`job_finished` starts the idle time. One task on the app's loop deletes the pod when
it runs out and no job holds the lock; a job in between cancels it. A failed delete
is retried every minute and shown to the developer until it succeeds.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID

from sqlalchemy import Engine

from app.blender.launch import Launch
from app.render import benchmark_store
from app.render.offload import sessions
from app.render.offload.check import (
    PINNED_VERSION,
    SSH_ERROR,
    ask_version,
    reported_version,
)
from app.render.offload.job import RemoteFailed
from app.render.offload.runpod import PodInfo, RunPodClient, RunPodError, pod_body
from app.render.offload.transport import OffloadConfig

logger = logging.getLogger("app")

STARTUP_LIMIT_SECONDS: Final = 600.0
# A pod RunPod has not given an address by now was never started (design decision 12).
ADDRESS_LIMIT_SECONDS: Final = 180.0
ADDRESS_POLL_SECONDS: Final = 5.0
SSH_POLL_SECONDS: Final = 10.0
DELETE_RETRY_SECONDS: Final = 60.0
BUSY_RECHECK_SECONDS: Final = 30.0
SHUTDOWN_SECONDS: Final = 30.0
# What `ssh` prints when the pod's key is not the pinned one: no retry can fix that.
_HOST_KEY_FAILED: Final = re.compile(r"Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED")

HOST_KEY_MISMATCH: Final = (
    "the render pod's host key does not match the known-hosts file; re-run the volume setup "
    "or fix the known-hosts entry for hra-render-pod"
)
POD_BUSY: Final = "a render is running on the pod; it can be deleted when the render ends"


class PodBusy(Exception):
    """The pod cannot be deleted now: a remote job holds it."""


@dataclass(frozen=True, slots=True)
class PodSettings:
    gpu_types: tuple[str, ...]  # first choice first
    image: str
    volume_id: str


def _now() -> datetime:
    return datetime.now(UTC)


class PodManager:
    def __init__(
        self,
        *,
        client: RunPodClient,
        settings: PodSettings,
        template: OffloadConfig,
        semaphore: asyncio.Semaphore,
        engine: Engine | None = None,
        now: Callable[[], datetime] = _now,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self.client = client
        self.settings = settings
        self.template = template
        self.semaphore = semaphore
        self.engine = engine
        self._now = now
        self._sleep = sleep
        self.state = "none"  # none, starting, running or delete_failed
        self.pod_id: str | None = None
        self.connection: OffloadConfig | None = None
        self.delete_at: datetime | None = None
        self.error: str | None = None
        self._session: UUID | None = None
        self._task: asyncio.Task | None = None
        # How the session is closed once a failed delete finally succeeds.
        self._retry_outcome = "deleted_idle"

    # -- read by the check, the estimate and the developer panel --------------------

    @property
    def running(self) -> bool:
        return self.state == "running" and self.connection is not None

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "pod_id": self.pod_id,
            "delete_at": self.delete_at.isoformat() if self.delete_at else None,
            "error": self.error,
        }

    # -- start ----------------------------------------------------------------------

    async def ensure_pod(self, launch: Launch) -> OffloadConfig:
        """The running pod's connection, creating the pod when there is none. Raises `RemoteFailed`."""
        self._cancel_timer()
        if self.running:
            self.delete_at = None
            return self.connection  # type: ignore[return-value]
        if self.state == "delete_failed":
            await self._delete(self._retry_outcome)
            if self.state == "delete_failed":
                raise RemoteFailed(f"the previous render pod could not be deleted: {self.error}")
        return await self._start(launch)

    async def _start(self, launch: Launch) -> OffloadConfig:
        self.state, self.error, self.delete_at = "starting", None, None
        began = self._now()
        try:
            volume = await self.client.get_network_volume(self.settings.volume_id)
            pod = await self.client.create_pod(
                pod_body(
                    gpu_types=self.settings.gpu_types,
                    image=self.settings.image,
                    volume_id=self.settings.volume_id,
                    data_center_id=volume.data_center_id,
                ),
                gpu_types=self.settings.gpu_types,
            )
        except RunPodError as error:
            self.state = "none"
            raise RemoteFailed(error.reason) from None
        self.pod_id = pod.id
        self._session = self._record(sessions.open_session, pod.id, self._placed(pod), pod.cost_per_hr)
        try:
            connection, cost, placed = await self._wait_until_ready(launch, began)
        except RemoteFailed as failure:
            await self._delete("start_failed", error=failure.reason)
            raise
        boot_seconds = (self._now() - began).total_seconds()
        self.state, self.connection = "running", connection
        if self.engine is not None and boot_seconds > 0:
            try:
                benchmark_store.write_boot_seconds(self.engine, boot_seconds)
            except Exception as error:  # noqa: BLE001 - the render goes ahead without the record
                logger.warning("offload.boot_not_recorded", extra={"context": {"error_type": type(error).__name__}})
        changes: dict[str, Any] = {"ready_at": self._now()}
        if cost is not None:
            changes["cost_per_hr"] = cost
        if placed is not None:
            changes["gpu_type"] = placed
        self._update(**changes)
        return connection

    async def _wait_until_ready(
        self, launch: Launch, began: datetime
    ) -> tuple[OffloadConfig, float | None, str | None]:
        def left() -> float:
            return STARTUP_LIMIT_SECONDS - (self._now() - began).total_seconds()

        while True:
            if left() <= 0:
                raise RemoteFailed(
                    f"the render pod did not answer within {int(STARTUP_LIMIT_SECONDS // 60)} minutes "
                    "of starting and was deleted"
                )
            try:
                pod = await self.client.get_pod(self.pod_id or "")
            except RunPodError as error:
                raise RemoteFailed(error.reason) from None
            if pod is None or pod.status == "TERMINATED":
                raise RemoteFailed("the render pod stopped while starting")
            if not pod.reachable:
                if (self._now() - began).total_seconds() >= ADDRESS_LIMIT_SECONDS:
                    raise RemoteFailed(
                        f"RunPod did not start the render pod within {int(ADDRESS_LIMIT_SECONDS // 60)} "
                        "minutes, so it was deleted; try again, RunPod will likely use another machine"
                    )
                await self._sleep(ADDRESS_POLL_SECONDS)
                continue
            connection = self.template.for_pod(pod.public_ip or "", pod.ssh_port or 22)
            answer = await ask_version(connection, launch)
            if _HOST_KEY_FAILED.search(answer.stderr_tail):
                raise RemoteFailed(HOST_KEY_MISMATCH)
            if answer.exit_code == 0 and not answer.timed_out:
                version = reported_version(answer)
                if version != PINNED_VERSION:
                    raise RemoteFailed(
                        f"the render pod runs Blender {version or 'of an unknown version'}, not the pinned "
                        f"{PINNED_VERSION}; re-run the volume setup"
                    )
                return connection, pod.cost_per_hr, pod.gpu_type
            if answer.exit_code not in (SSH_ERROR, -1) and not answer.timed_out:
                raise RemoteFailed(
                    "the render pod answered but could not run Blender at the configured path; "
                    "check RENDER_OFFLOAD_BLENDER and the volume setup"
                )
            await self._sleep(SSH_POLL_SECONDS)

    # -- idle and delete ---------------------------------------------------------------

    def job_finished(self, idle_minutes: int | None = None) -> None:
        """A remote job ended on the running pod: count it and start the idle time."""
        if not self.running:
            return
        self._update(jobs=1)
        if idle_minutes is None:
            idle_minutes = (
                benchmark_store.read_idle_minutes(self.engine)
                if self.engine is not None
                else benchmark_store.DEFAULT_IDLE_MINUTES
            )
        self.delete_at = self._now() + timedelta(minutes=idle_minutes)
        self._start_timer()

    def _start_timer(self) -> None:
        self._cancel_timer()
        self._task = asyncio.get_running_loop().create_task(self._wait_and_delete())

    def _cancel_timer(self) -> None:
        if self._task is not None and not self._task.done() and self._task is not asyncio.current_task():
            self._task.cancel()
        self._task = None

    async def _wait_and_delete(self) -> None:
        while self.delete_at is not None and self.pod_id is not None:
            remaining = (self.delete_at - self._now()).total_seconds()
            if remaining > 0:
                await self._sleep(remaining)
                continue
            if self.semaphore.locked():  # a job is running on the pod: never delete under it
                await self._sleep(BUSY_RECHECK_SECONDS)
                continue
            await self._delete("deleted_idle" if self.state == "running" else self._retry_outcome)
            if self.state != "delete_failed":
                return
            self.delete_at = self._now() + timedelta(seconds=DELETE_RETRY_SECONDS)

    async def delete_now(self) -> None:
        """The developer's "Delete pod now". Raises `PodBusy` while a job holds the pod."""
        if self.semaphore.locked():
            raise PodBusy(POD_BUSY)
        if self.pod_id is None:
            return
        self._cancel_timer()
        await self._delete("deleted_manual")
        if self.state == "delete_failed":
            self._retry_later("deleted_manual")

    async def _delete(self, outcome: str, *, error: str | None = None) -> None:
        """Delete the pod and confirm it is gone; on failure keep it as `delete_failed`."""
        pod_id = self.pod_id
        if pod_id is None:
            self.state = "none"
            return
        try:
            await self.client.delete_pod(pod_id)
            left = await self.client.get_pod(pod_id)
            if left is not None and left.status != "TERMINATED":
                raise RunPodError("RunPod still lists the render pod after deleting it")
        except RunPodError as failure:
            self.state, self.error, self.connection = "delete_failed", failure.reason, None
            self._update(outcome="delete_failed", error=failure.reason)
            logger.warning("offload.pod_delete_failed", extra={"context": {"pod_id": pod_id}})
            return
        self._record(sessions.close_session, self._session, outcome, error)
        self.state, self.pod_id, self.connection, self.delete_at, self._session = "none", None, None, None, None
        self.error = None

    def _retry_later(self, outcome: str) -> None:
        self._retry_outcome = outcome
        self.delete_at = self._now() + timedelta(seconds=DELETE_RETRY_SECONDS)
        self._start_timer()

    # -- app start and stop --------------------------------------------------------------

    async def startup_cleanup(self) -> None:
        """Delete every app-named pod left from an earlier run, and record each as orphaned."""
        try:
            pods = await self.client.list_pods()
        except RunPodError as error:
            self.error = error.reason
            logger.warning("offload.pod_cleanup_failed", extra={"context": {"reason": error.reason}})
            return
        for pod in pods:
            try:
                await self.client.delete_pod(pod.id)
            except RunPodError as error:
                self.state, self.pod_id, self.error = "delete_failed", pod.id, error.reason
                self._session = self._record(sessions.open_session, pod.id, self._placed(pod), pod.cost_per_hr)
                self._update(outcome="delete_failed", error=error.reason)
                self._retry_later("orphaned")
                continue
            self._record(sessions.record_orphan, pod.id, self._placed(pod), pod.cost_per_hr)

    async def shutdown(self) -> None:
        """Delete the pod before the app exits, waiting at most 30 seconds."""
        self._cancel_timer()
        if self.pod_id is None:
            return
        try:
            await asyncio.wait_for(self._delete("deleted_shutdown"), SHUTDOWN_SECONDS)
        except TimeoutError:
            logger.warning("offload.pod_delete_timed_out", extra={"context": {"pod_id": self.pod_id}})

    # -- records ---------------------------------------------------------------------------

    def _placed(self, pod: PodInfo) -> str:
        """The GPU type RunPod gave the pod, or the first choice until it says."""
        return pod.gpu_type or self.settings.gpu_types[0]

    def _record(self, write: Callable[..., Any], *args: Any) -> Any:
        return write(self.engine, *args) if self.engine is not None else None

    def _update(self, **changes: Any) -> None:
        if self.engine is not None:
            sessions.update_session(self.engine, self._session, **changes)
