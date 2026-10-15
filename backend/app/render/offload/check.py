"""Is the render server there, and is it the pinned Blender? (render-offload design decision 6)

Checked before a remote `final` is quoted, so the owner is never asked to approve a
render that cannot run. A failure is a refusal with a stated reason and there is no
fallback: the render is not run on the laptop instead.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Final

from app.blender.launch import Launch, LaunchResult
from app.render.guard import RenderRefused
from app.render.offload.runpod import UNREACHABLE as RUNPOD_UNREACHABLE
from app.render.offload.runpod import RunPodClient, RunPodError
from app.render.offload.transport import OffloadConfig, Transport, quoted

logger = logging.getLogger("app")

PINNED_VERSION: Final = "5.2.1"
CHECK_SECONDS: Final = 10.0
CACHE_SECONDS: Final = 60.0
SSH_ERROR: Final = 255  # what `ssh` itself exits with when it cannot connect or verify the host

# The remote shell prints Blender's first line on stderr, which is what the launcher keeps.
VERSION_COMMAND: Final = 'v=$({blender} 2>&1) && printf "%s\\n" "$v" | head -n 1 >&2'
_VERSION: Final = re.compile(r"Blender\s+(\d+\.\d+\.\d+)")

UNREACHABLE: Final = (
    "the render server is unreachable (check that it is running and that its host key is "
    "in the known-hosts file); start it, or switch final renders to the laptop in the "
    "developer panel"
)
SWITCH_TO_LAPTOP: Final = "switch final renders to the laptop in the developer panel"
NOT_CONFIGURED: Final = (
    "final renders are set to run on the render server, but it is not configured; "
    "set it up, or switch final renders to the laptop in the developer panel"
)


async def ask_version(config: OffloadConfig, launch: Launch) -> LaunchResult:
    """Run `blender --version` on the server (one ssh, ten seconds at most)."""
    command = VERSION_COMMAND.format(blender=quoted(config.blender, "--version"))
    return await Transport(config, launch).ssh(command, CHECK_SECONDS)


def reported_version(result: LaunchResult) -> str | None:
    found = _VERSION.search(result.stderr_tail)
    return found.group(1) if found else None


class OffloadChecker:
    """Runs the check and remembers a success for a minute."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._ok_until = 0.0

    async def check(self, config: OffloadConfig, launch: Launch) -> None:
        if self._clock() < self._ok_until:
            return
        result = await ask_version(config, launch)
        if result.timed_out or result.exit_code == SSH_ERROR:
            raise RenderRefused(UNREACHABLE, failure_class="offload_unreachable")
        if result.exit_code != 0:
            raise RenderRefused(
                "the render server answered but could not run Blender at the configured path; "
                "check the server's Blender, or switch final renders to the laptop in the "
                "developer panel",
                failure_class="offload_unreachable",
            )
        version = reported_version(result)
        if version is None:
            raise RenderRefused(
                "the render server's Blender did not report a version; check its installation, "
                "or switch final renders to the laptop in the developer panel",
                failure_class="offload_version",
            )
        if version != PINNED_VERSION:
            raise RenderRefused(
                f"the render server runs Blender {version}, not the pinned {PINNED_VERSION}; "
                "install the pinned version there, or switch final renders to the laptop in "
                "the developer panel",
                failure_class="offload_version",
            )
        self._ok_until = self._clock() + CACHE_SECONDS

    async def check_runpod(
        self, client: RunPodClient, volume_id: str, gpu_types: Sequence[str] = ()
    ) -> None:
        """Pod mode with no pod running (render-pod-lifecycle): RunPod accepts the key and
        knows the volume, and at least one render GPU is in stock in the volume's data centre
        (render-gpu-availability). Creates nothing, so nothing is billed before approval."""
        if self._clock() < self._ok_until:
            return
        started = self._clock()
        try:
            volume = await asyncio.wait_for(client.get_network_volume(volume_id), CHECK_SECONDS)
        except TimeoutError:
            raise RenderRefused(
                f"{RUNPOD_UNREACHABLE}; try again, or {SWITCH_TO_LAPTOP}", failure_class="offload_unreachable"
            ) from None
        except RunPodError as error:
            raise RenderRefused(
                f"{error.reason}; fix it, or {SWITCH_TO_LAPTOP}", failure_class="offload_unreachable"
            ) from None
        if gpu_types:
            await self._require_stock(client, gpu_types, volume.data_center_id, started)
        self._ok_until = self._clock() + CACHE_SECONDS

    async def _require_stock(
        self, client: RunPodClient, gpu_types: Sequence[str], data_center: str, started: float
    ) -> None:
        """Refuse when every render GPU reads `NONE` there. An unread stock never refuses:
        the create decides then, and it fails safely."""
        left = max(CHECK_SECONDS - (self._clock() - started), 1.0)
        try:
            levels = await asyncio.wait_for(client.gpu_stock(gpu_types, data_center), left)
        except (TimeoutError, RunPodError) as error:
            logger.warning("offload.stock_unread", extra={"context": {"error_type": type(error).__name__}})
            return
        if all(level == "NONE" for level in levels.values()):
            raise RenderRefused(
                f"none of {', '.join(gpu_types)} is in stock in {data_center} right now; "
                f"try again later, or {SWITCH_TO_LAPTOP}",
                failure_class="offload_no_stock",
            )

    def forget(self) -> None:
        self._ok_until = 0.0
