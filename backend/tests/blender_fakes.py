"""Fake launchers and file writers: the runner and routes without Blender.

A real generator is handed `--out <path that does not exist yet>`, creates it,
and fills it. These fakes do the same with the smallest files that pass the
runner's checks: a GLB header, a PNG of the exact requested size (zlib makes a
600 × 600 grey image about a kilobyte), parseable JSON and CSV.
"""

from __future__ import annotations

import asyncio
import csv
import functools
import json
import struct
import zlib
from collections.abc import Callable
from pathlib import Path

from app.blender.launch import Launch, LaunchResult

BUILD_FILES = (
    "model.glb",
    "model.blend",
    "spec.json",
    "cutlist.csv",
    "hardware.csv",
    "screenshot.png",
)


def out_dir_from_argv(argv: list[str]) -> Path:
    return Path(argv[argv.index("--out") + 1])


def arg_value(argv: list[str], flag: str) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv else None


@functools.lru_cache(maxsize=16)
def png_bytes(width: int, height: int) -> bytes:
    """A valid 8-bit greyscale PNG of exactly `width` × `height`."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", data[16:24])


def write_build_files(out: Path, *, spec: dict | None = None) -> None:
    out.mkdir()
    (out / "model.glb").write_bytes(b"glTF" + struct.pack("<II", 2, 20) + b"\x00" * 8)
    (out / "model.blend").write_bytes(b"BLENDER-fake")
    emitted = spec or {
        "name": "fake",
        "kind": "custom_build",
        "units": "mm",
        "overall": {"w": 1000, "h": 750, "d": 500},
        "modules": {},
        "parts": [],
        "hardware": [],
        "assembly": [],
        "layers": {"carcass": ["A"]},
        "blender_version": "5.2.1 LTS",
    }
    (out / "spec.json").write_text(json.dumps(emitted), encoding="utf-8")
    for name, fields in (("cutlist.csv", ["id", "qty"]), ("hardware.csv", ["id", "item"])):
        with (out / name).open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(fields)
    (out / "screenshot.png").write_bytes(png_bytes(800, 500))


def write_shell_files(out: Path) -> None:
    out.mkdir()
    (out / "model.glb").write_bytes(b"glTF" + struct.pack("<II", 2, 20) + b"\x00" * 8)
    (out / "model.blend").write_bytes(b"BLENDER-fake")
    (out / "shell.json").write_text(json.dumps({"kind": "apartment_shell", "walls": []}), encoding="utf-8")
    (out / "screenshot.png").write_bytes(png_bytes(800, 500))


def write_frames(out: Path, *, frames: int, size: int, skip_empty: int | None = None) -> None:
    out.mkdir()
    folder = out / "frames"
    folder.mkdir()
    for index in range(frames):
        (folder / f"frame_{index:03d}.png").write_bytes(
            b"" if index == skip_empty else png_bytes(size, size)
        )
    (out / "scene.json").write_text(json.dumps({"frames": frames}), encoding="utf-8")
    (out / "viewer.html").write_text(f"<html>{frames} frames</html>", encoding="utf-8")


def write_still(out: Path, *, size: int) -> None:
    out.mkdir()
    (out / "still.png").write_bytes(png_bytes(size, size))
    (out / "scene.json").write_text(json.dumps({"kind": "still"}), encoding="utf-8")


def fake_success_launch(
    writer: Callable[[Path, list[str]], None] | None = None,
    *,
    delay: float = 0.0,
    tracker: list[int] | None = None,
    calls: list[list[str]] | None = None,
) -> Launch:
    """Exits zero after `writer` fills the `--out` path. `tracker` records
    concurrency so a test can prove two launches never overlap."""

    async def _launch(argv: list[str], cwd: Path, timeout: float) -> LaunchResult:
        if calls is not None:
            calls.append(argv)
        if tracker is not None:
            tracker.append(1)
            assert sum(tracker) <= 1, "two launches overlapped"
        try:
            if delay:
                await asyncio.sleep(delay)
            (writer or (lambda out, _argv: write_build_files(out)))(
                out_dir_from_argv(argv), argv
            )
        finally:
            if tracker is not None:
                tracker.pop()
        return LaunchResult(exit_code=0, stderr_tail="", timed_out=False)

    return _launch


async def fake_failure_launch(argv: list[str], cwd: Path, timeout: float) -> LaunchResult:
    return LaunchResult(exit_code=1, stderr_tail="build: RuntimeError: boom", timed_out=False)


async def fake_hanging_launch(argv: list[str], cwd: Path, timeout: float) -> LaunchResult:
    return LaunchResult(
        exit_code=-1, stderr_tail=f"timed out after {timeout:.0f} seconds", timed_out=True
    )


async def fake_missing_binary_launch(
    argv: list[str], cwd: Path, timeout: float
) -> LaunchResult:
    return LaunchResult(
        exit_code=-1, stderr_tail="Blender could not be started: no such file", timed_out=False
    )


def fake_pipeline_launch(
    *, delay: float = 0.0, tracker: list[int] | None = None, calls: list[list[str]] | None = None
) -> Launch:
    """One fake for every script: a build writes the six files; a still, a
    turntable and a room render write what the real generator would, at the
    size and frame count the argv names (so only the tier can change them)."""

    def writer(out: Path, argv: list[str]) -> None:
        script = next((Path(a).name for a in argv if a.endswith(".py")), "")
        if script == "build_custom_build.py":
            write_build_files(out)
            return
        if script == "build_shell.py":
            write_shell_files(out)
            return
        size = int(arg_value(argv, "--tier-resolution"))
        frames = int(arg_value(argv, "--tier-frames"))
        if script == "render_still.py":
            write_still(out, size=size)
        elif script == "render_turntable.py":
            write_frames(out, frames=frames, size=size)
        else:  # build_room_scene.py: the scene document names the kind
            scene = json.loads(Path(arg_value(argv, "--scene")).read_text(encoding="utf-8"))
            if scene["output"]["kind"] == "still":
                write_still(out, size=size)
            else:
                write_frames(out, frames=frames, size=size)

    return fake_success_launch(writer, delay=delay, tracker=tracker, calls=calls)
