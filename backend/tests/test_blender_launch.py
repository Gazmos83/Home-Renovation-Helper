"""render-guard: a cancelled launch never leaves its child process running."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from app.blender.launch import subprocess_launch


def test_a_cancelled_launch_kills_the_child(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"

    async def cancel_while_running() -> None:
        task = asyncio.create_task(
            subprocess_launch(["sh", "-c", f"echo $$ > {pid_file}; exec sleep 30"], tmp_path, timeout=60)
        )
        while not pid_file.exists() or not pid_file.read_text().strip():
            await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_while_running())
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)
