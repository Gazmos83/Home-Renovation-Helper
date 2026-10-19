"""Format checks for published files, shared by the generators and the runner.

Standard library only: it runs inside Blender's Python as well as the backend.
"""

from __future__ import annotations

import csv
import json
import struct
from pathlib import Path

from app.blender.storage import BUILD_FILES, COMPOSITION_FILES, SHELL_FILES


class VerificationError(RuntimeError):
    """A published file is missing, empty or malformed. The message names it."""


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise VerificationError(f"{path.name} is not a PNG file")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def verify_png(path: Path, expected: tuple[int, int] | None = None) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise VerificationError(f"{path.name} is missing or empty")
    size = png_size(path)
    if expected is not None and size != expected:
        raise VerificationError(
            f"{path.name} is {size[0]}×{size[1]}, expected {expected[0]}×{expected[1]}"
        )


def verify_glb(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise VerificationError("model.glb is not a GLB 2.0 file")


def glb_mesh_nodes(path: Path) -> list[str]:
    """The names of a GLB's nodes that carry a mesh, read from its JSON chunk."""
    verify_glb(path)
    data = path.read_bytes()
    try:
        length, kind = struct.unpack_from("<II", data, 12)
        if kind != 0x4E4F534A:  # "JSON"
            raise ValueError("the first chunk is not JSON")
        document = json.loads(data[20:20 + length])
    except (struct.error, ValueError) as error:
        raise VerificationError(f"model.glb has no readable JSON chunk: {error}") from None
    return [str(node.get("name", "")) for node in document.get("nodes", []) if "mesh" in node]


def verify_build(directory: Path) -> None:
    """The nine build files exist (exactly), are non-empty and parse."""
    names = {entry.name for entry in directory.iterdir()}
    if names != set(BUILD_FILES):
        raise VerificationError(
            f"expected the build files only, got {sorted(names)} (missing "
            f"{sorted(set(BUILD_FILES) - names)}, extra {sorted(names - set(BUILD_FILES))})"
        )
    for entry in directory.iterdir():
        if entry.stat().st_size == 0:
            raise VerificationError(f"{entry.name} is empty")
    json.loads((directory / "spec.json").read_text(encoding="utf-8"))
    for name in ("cutlist.csv", "hardware.csv"):
        with (directory / name).open(newline="", encoding="utf-8") as handle:
            list(csv.DictReader(handle))
    verify_glb(directory / "model.glb")
    for name in ("screenshot.png", "front.png", "side.png", "top.png"):
        png_size(directory / name)


def verify_frames(directory: Path, count: int, size: int) -> None:
    """`frames/frame_000.png` … exactly `count` of them, each `size` × `size`."""
    frames = directory / "frames"
    expected = [f"frame_{index:03d}.png" for index in range(count)]
    present = sorted(entry.name for entry in frames.iterdir()) if frames.is_dir() else []
    if present != expected:
        missing = sorted(set(expected) - set(present))
        raise VerificationError(
            f"expected {count} turntable frames; missing {missing[:3]}"
            if missing
            else f"unexpected frame files: {sorted(set(present) - set(expected))[:3]}"
        )
    for name in expected:
        verify_png(frames / name, (size, size))


def verify_shell(directory: Path) -> None:
    """The four shell build files exist (exactly), are non-empty and parse."""
    names = {entry.name for entry in directory.iterdir()}
    if names != set(SHELL_FILES):
        raise VerificationError(
            f"expected the shell files only, got {sorted(names)} (missing "
            f"{sorted(set(SHELL_FILES) - names)}, extra {sorted(names - set(SHELL_FILES))})"
        )
    for entry in directory.iterdir():
        if entry.stat().st_size == 0:
            raise VerificationError(f"{entry.name} is empty")
    json.loads((directory / "shell.json").read_text(encoding="utf-8"))
    verify_glb(directory / "model.glb")
    png_size(directory / "screenshot.png")


def verify_composition(directory: Path) -> None:
    """The four composition build files exist (exactly), are non-empty and parse."""
    names = {entry.name for entry in directory.iterdir()}
    if names != set(COMPOSITION_FILES):
        raise VerificationError(
            f"expected the composition files only, got {sorted(names)} (missing "
            f"{sorted(set(COMPOSITION_FILES) - names)}, extra {sorted(names - set(COMPOSITION_FILES))})"
        )
    for entry in directory.iterdir():
        if entry.stat().st_size == 0:
            raise VerificationError(f"{entry.name} is empty")
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    verify_png(directory / "screenshot.png")
    # Every mesh in the model belongs to exactly one surface of the report's map (app-check-2026-10-09).
    surfaces = report.get("surfaces") if isinstance(report, dict) else None
    if not isinstance(surfaces, dict):
        raise VerificationError("report.json has no surface map")
    listed = [name for names in surfaces.values() for name in names]
    twice = sorted({name for name in listed if listed.count(name) > 1})
    if twice:
        raise VerificationError(f"the surface map lists {twice[0]!r} more than once")
    # Each placed item's meshes are items in the surface map, each listed for one item (hidden-room-items).
    item_lists = [entry.get("meshes") or [] for entry in report.get("items") or [] if isinstance(entry, dict)]
    owned = [name for names in item_lists for name in names]
    shared = sorted({name for name in owned if owned.count(name) > 1})
    if shared:
        raise VerificationError(f"the report lists the mesh {shared[0]!r} for two items")
    stray = sorted(set(owned) - set(surfaces.get("items") or []))
    if stray:
        raise VerificationError(f"the report's item mesh {stray[0]!r} is not under the surface map's items")
    meshes = set(glb_mesh_nodes(directory / "model.glb"))
    if meshes != set(listed):
        raise VerificationError(
            "the surface map does not match the model's meshes "
            f"(unmapped {sorted(meshes - set(listed))[:3]}, absent {sorted(set(listed) - meshes)[:3]})"
        )
