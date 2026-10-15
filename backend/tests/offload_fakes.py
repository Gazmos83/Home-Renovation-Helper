"""A fake render server: ssh and scp answered from a temporary folder, no network.

`FakeServer.launch` has the signature of the launcher the transport uses. It reads
the argv the transport built, so a test sees the real commands, and it performs them
the way a Linux box would: make the job folder, take the archive, unpack it, "render"
by writing what the generator would, hand the output back, remove the folder.
"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
import shutil
import tarfile
from pathlib import Path

import httpx

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


class FakeRunPod:
    """RunPod's REST API, answered in memory (render-pod-lifecycle).

    `transport` is an `httpx.MockTransport` for `RunPodClient`. A created pod gets an
    address after `ready_after` reads of it, the way a booting pod does.
    """

    def __init__(
        self,
        *,
        key: str = "rpa_SECRETKEYVALUE",
        volume_id: str = "vol123",
        data_center: str = "EU-RO-1",
        ready_after: int = 1,
        no_capacity: bool = False,
        no_capacity_text: str = "There are no longer any instances available with the requested specifications.",
        delete_fails: int = 0,
        down: bool = False,
        stock: set[str] | None = None,
    ) -> None:
        self.key = key
        self.volume_id = volume_id
        self.data_center = data_center
        self.ready_after = ready_after
        self.no_capacity = no_capacity
        self.no_capacity_text = no_capacity_text
        self.delete_fails = delete_fails
        self.down = down
        self.stock = stock  # GPU types that can be placed; `None` means any
        self.pods: dict[str, dict] = {}
        self.reads: dict[str, int] = {}
        self.requests: list[httpx.Request] = []
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self._next = 0
        self.transport = httpx.MockTransport(self._handle)

    def add_pod(self, name: str, *, ready: bool = True, gpu: str = "NVIDIA GeForce RTX 4090") -> str:
        self._next += 1
        pod_id = f"pod{self._next}"
        self.pods[pod_id] = {
            "id": pod_id, "name": name, "desiredStatus": "RUNNING", "costPerHr": 0.69,
            "gpu": {"id": gpu, "count": 1},
        }
        self.reads[pod_id] = self.ready_after if ready else 0
        if ready:
            self._make_ready(pod_id)
        return pod_id

    def _make_ready(self, pod_id: str) -> None:
        self.pods[pod_id].update(publicIp="203.0.113.7", portMappings={"22": 10341})

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("down", request=request)
        if request.headers.get("Authorization") != f"Bearer {self.key}":
            return httpx.Response(401, json={"error": "unauthorized"})
        path = request.url.path.removeprefix("/v1")
        if request.method == "GET" and path.startswith("/networkvolumes/"):
            if path.rsplit("/", 1)[-1] != self.volume_id:
                return httpx.Response(404, json={"error": "not found"})
            return httpx.Response(
                200, json={"id": self.volume_id, "name": "hra", "size": 5, "dataCenterId": self.data_center}
            )
        if request.method == "POST" and path == "/pods":
            body = json.loads(request.content)
            self.created.append(body)
            placeable = [g for g in body["gpuTypeIds"] if self.stock is None or g in self.stock]
            if self.no_capacity or not placeable:
                return httpx.Response(500, json={"error": self.no_capacity_text, "status": 500})
            pod_id = self.add_pod(body["name"], ready=False, gpu=placeable[0])
            return httpx.Response(201, json=self.pods[pod_id])
        if path == "/pods" and request.method == "GET":
            name = request.url.params.get("name")
            return httpx.Response(200, json=[pod for pod in self.pods.values() if name in (None, pod["name"])])
        pod_id = path.rsplit("/", 1)[-1]
        if request.method == "GET":
            if pod_id not in self.pods:
                return httpx.Response(404, json={"error": "not found"})
            self.reads[pod_id] += 1
            if self.reads[pod_id] >= self.ready_after:
                self._make_ready(pod_id)
            return httpx.Response(200, json=self.pods[pod_id])
        if request.method == "DELETE":
            if self.delete_fails:
                self.delete_fails -= 1
                return httpx.Response(500, json={"error": "try later"})
            self.pods.pop(pod_id, None)
            self.deleted.append(pod_id)
            return httpx.Response(204)
        return httpx.Response(405)



__all__ = ["OK", "FakeRunPod", "FakeServer", "png_bytes"]
