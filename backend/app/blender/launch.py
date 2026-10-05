"""The one seam between the runner and a real Blender process.

`Launch` is what the ordinary test suite replaces with fakes (success, non-zero
exit, hang past the timeout, missing binary), so no test needs Blender unless it
is marked `blender`. Production binds it to `subprocess_launch`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LaunchResult:
    exit_code: int
    stderr_tail: str
    timed_out: bool


# (argv, working directory, timeout in seconds) -> the process's outcome.
Launch = Callable[[list[str], Path, float], Awaitable[LaunchResult]]


def last_nonblank_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


async def subprocess_launch(argv: list[str], cwd: Path, timeout: float) -> LaunchResult:
    """The real launcher: `asyncio.create_subprocess_exec` with a timeout."""
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, PermissionError, OSError) as error:
        return LaunchResult(
            exit_code=-1,
            stderr_tail=f"Blender could not be started: {error}",
            timed_out=False,
        )

    try:
        _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        return LaunchResult(
            exit_code=-1,
            stderr_tail=f"timed out after {timeout:.0f} seconds",
            timed_out=True,
        )

    return LaunchResult(
        exit_code=process.returncode or 0,
        stderr_tail=last_nonblank_line(stderr.decode("utf-8", errors="replace")),
        timed_out=False,
    )
