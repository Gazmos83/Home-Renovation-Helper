"""A fake render server: ssh and scp answered from a temporary folder, no network.

`FakeServer.launch` has the signature of the launcher the transport uses. It reads
the argv the transport built, so a test sees the real commands, and it performs them
the way a Linux box would: make the job folder, take the archive, unpack it, "render"
by writing what the generator would, hand the output back, remove the folder.
"""

from __future__ import annotations

import asyncio
import re
import shlex
import shutil
import tarfile
from pathlib import Path

from app.blender.launch import LaunchResult
from tests.blender_fakes import png_bytes, write_frames, write_still

OK = LaunchResult(0, "", False)


class FakeServer:
    def __init__(
        self,
        root: Path,
        *,
        version: str = "Blender 5.2.1 LTS",
        reachable: bool = True,
        delay: float = 0.0,
        omit_frame: int | None = None,
        extra_file: str | None = None,
        symlink: bool = False,
        hang_render: bool = False,
        fail_upload: bool = False,
        fail_render: str | None = None,
    ) -> None:
        self.root = root
        self.version = version
        self.reachable = reachable
        self.delay = delay
        self.omit_frame = omit_frame
        self.extra_file = extra_file
        self.symlink = symlink
        self.hang_render = hang_render
        self.fail_upload = fail_upload
        self.fail_render = fail_render
        self.calls: list[list[str]] = []
        self.render_commands: list[str] = []
        self.uploaded: list[str] = []
        self.active = 0
        self.max_active = 0

    # -- helpers -----------------------------------------------------------------

    def _path(self, remote: str) -> Path:
        return self.root / remote.split(":", 1)[-1]

    def job_folders(self) -> list[str]:
        base = self.root / "hra-render"
        return sorted(entry.name for entry in base.iterdir()) if base.is_dir() else []

    # -- the launcher -------------------------------------------------------------

    async def launch(self, argv: list[str], cwd: Path, timeout: float) -> LaunchResult:
        self.calls.append(argv)
        if not self.reachable:
            return LaunchResult(255, "ssh: connect to host gpu port 22: Connection refused", False)
        if argv[0] == "scp":
            return self._scp(argv)
        return await self._ssh(argv[-1], timeout)

    def _scp(self, argv: list[str]) -> LaunchResult:
        source, destination = argv[-2], argv[-1]
        if "@" in destination:  # upload
            if self.fail_upload:
                return LaunchResult(1, "scp: write failed", False)
            target = self._path(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            self.uploaded.append(target.name)
            return OK
        origin = self._path(source)  # download of a folder
        if not origin.is_dir():
            return LaunchResult(1, "scp: no such file", False)
        shutil.copytree(origin, destination, symlinks=True)
        return OK

    async def _ssh(self, command: str, timeout: float) -> LaunchResult:
        if "--version" in command:
            return LaunchResult(0, self.version, False)
        if command.startswith("mkdir -p"):
            job = re.search(r"mkdir (hra-render/\S+)$", command).group(1)
            (self.root / job).mkdir(parents=True)
            return OK
        if "tar xzf" in command:
            job = re.match(r"cd (hra-render/\S+) &&", command).group(1)
            folder = self.root / job
            with tarfile.open(folder / "bundle.tar.gz") as archive:
                archive.extractall(folder, filter="data")
            (folder / "bundle.tar.gz").unlink()
            return OK
        if "--background" in command:
            return await self._render(command, timeout)
        if command.startswith("rm -rf"):
            shutil.rmtree(self.root / shlex.split(command)[-1], ignore_errors=True)
            return OK
        return LaunchResult(1, f"unknown command: {command}", False)

    async def _render(self, command: str, timeout: float) -> LaunchResult:
        self.render_commands.append(command)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.hang_render:
                return LaunchResult(-1, f"timed out after {timeout:.0f} seconds", True)
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.fail_render:
                return LaunchResult(1, self.fail_render, False)
            job = re.match(r"cd (hra-render/\S+) &&", command).group(1)
            words = shlex.split(command.split("&&", 1)[1])
            arg = lambda flag: words[words.index(flag) + 1]
            size, frames = int(arg("--tier-resolution")), int(arg("--tier-frames"))
            out = self.root / job / "out"
            if "render_still.py" in command:
                write_still(out, size=size)
            else:
                write_frames(out, frames=frames, size=size, skip_empty=self.omit_frame)
                (out / "viewer.html").write_text("<html>SERVER VIEWER</html>", encoding="utf-8")
                if self.omit_frame is not None:
                    (out / "frames" / f"frame_{self.omit_frame:03d}.png").unlink()
            if self.extra_file:
                (out / self.extra_file).write_text("surprise", encoding="utf-8")
            if self.symlink:
                (out / "frames" / "frame_000.png").unlink(missing_ok=True)
                (out / "frames" / "frame_000.png").symlink_to("/etc/hostname")
            return OK
        finally:
            self.active -= 1


__all__ = ["OK", "FakeServer", "png_bytes"]
