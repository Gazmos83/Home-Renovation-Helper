"""Filesystem package records under the render root (furniture-packages).

`<root>/<package-id>/v<N>/` is the record: no table. A version holds its input
document, `status.json`, the six build files and any renders. This module is the
one place that turns an id and version into a directory, and the one place a
relative path is turned back into a filesystem path — `resolve()` refuses
anything outside the root.

Reserved: `benchmark` (the first-launch benchmark's folder) is not a package id.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

PACKAGE_ID_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
RESERVED_IDS: Final = frozenset({"benchmark", "shells"})
BENCHMARK_DIRNAME: Final = "benchmark"
SHELLS_DIRNAME: Final = "shells"

INPUT_FILE: Final = "input.json"
STATUS_FILE: Final = "status.json"

# What a successful build publishes, by name and media type.
BUILD_FILES: Final[dict[str, str]] = {
    "model.glb": "model/gltf-binary",
    "model.blend": "application/octet-stream",
    "spec.json": "application/json",
    "cutlist.csv": "text/csv",
    "hardware.csv": "text/csv",
    "screenshot.png": "image/png",
}

# What a successful shell build publishes (an apartment, not a piece).
SHELL_FILES: Final[dict[str, str]] = {
    "model.glb": "model/gltf-binary",
    "model.blend": "application/octet-stream",
    "shell.json": "application/json",
    "screenshot.png": "image/png",
}

# Every file the API serves by name (closed set; `frames/<n>` is handled apart).
SERVED_FILES: Final[dict[str, str]] = {
    **BUILD_FILES,
    "still.png": "image/png",
    "viewer.html": "text/html",
    "scene.json": "application/json",
    STATUS_FILE: "application/json",
}

STATUSES: Final = ("queued", "running", "succeeded", "failed")


class PathEscapesRoot(ValueError):
    """A relative path would resolve outside the configured root."""


class InvalidPackageId(ValueError):
    """A package id that is not a plain slug."""


def validate_package_id(package_id: str) -> str:
    if not isinstance(package_id, str) or not PACKAGE_ID_PATTERN.match(package_id):
        raise InvalidPackageId(
            "package id must be lower-case letters, digits and hyphens, start with a "
            "letter or digit, and be at most 64 characters"
        )
    if package_id in RESERVED_IDS:
        raise InvalidPackageId(f"{package_id!r} is reserved and cannot be a package id")
    return package_id


def resolve(root: Path, relative: Path | str) -> Path:
    """Join `relative` onto `root`, refusing any result outside it.

    Pathlib silently discards the left side when the right side is absolute
    (``Path("/root") / "/etc/passwd" == Path("/etc/passwd")``), so an absolute
    `relative` is refused before joining rather than relied on to fail the
    containment check below. A resolved symlink that lands outside the root is
    caught by the same containment check.
    """
    candidate = Path(relative)
    if candidate.is_absolute():
        raise PathEscapesRoot(f"{relative!r} is an absolute path, not a relative one")

    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise PathEscapesRoot(f"{relative!r} resolves outside the root") from None
    return resolved


def package_dir(root: Path, package_id: str) -> Path:
    return resolve(root, validate_package_id(package_id))


def version_dir(root: Path, package_id: str, version: int) -> Path:
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("version must be a positive integer")
    return resolve(root, Path(validate_package_id(package_id)) / f"v{version}")


def _version_numbers(folder: Path) -> list[int]:
    if not folder.is_dir():
        return []
    found = [
        int(entry.name[1:])
        for entry in folder.iterdir()
        if entry.is_dir() and re.fullmatch(r"v[1-9][0-9]*", entry.name)
    ]
    return sorted(found)


def versions(root: Path, package_id: str) -> list[int]:
    """The version numbers a package has, ascending."""
    return _version_numbers(package_dir(root, package_id))


def next_version(root: Path, package_id: str) -> int:
    existing = versions(root, package_id)
    return (existing[-1] + 1) if existing else 1


# --- apartment shells: `<root>/shells/<apartment-slug>/v<N>/` -----------------------------


def apartment_slug(name: str) -> str:
    """A package-id-shaped slug for an apartment name ("Example one-bed" → "example-one-bed")."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:64].strip("-")
    if not slug:
        raise InvalidPackageId(f"an apartment name needs letters or digits to make an id: {name!r}")
    return validate_package_id(slug)


def shell_dir(root: Path, slug: str) -> Path:
    return resolve(root, Path(SHELLS_DIRNAME) / validate_package_id(slug))


def shell_version_dir(root: Path, slug: str, version: int) -> Path:
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("version must be a positive integer")
    return resolve(root, Path(SHELLS_DIRNAME) / validate_package_id(slug) / f"v{version}")


def shell_versions(root: Path, slug: str) -> list[int]:
    return _version_numbers(shell_dir(root, slug))


def next_shell_version(root: Path, slug: str) -> int:
    existing = shell_versions(root, slug)
    return (existing[-1] + 1) if existing else 1


def list_shells(root: Path) -> list[tuple[str, list[int]]]:
    """Every apartment slug with its shell versions (ascending), ordered by slug."""
    base = root / SHELLS_DIRNAME
    if not base.is_dir():
        return []
    shells = []
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and PACKAGE_ID_PATTERN.match(entry.name):
            found = _version_numbers(entry)
            if found:
                shells.append((entry.name, found))
    return shells


def record_version_dir(root: Path, record: str, record_id: str, version: int) -> Path:
    """The version folder of a `piece` or a `shell`."""
    if record == "shell":
        return shell_version_dir(root, record_id, version)
    return version_dir(root, record_id, version)


def list_packages(root: Path) -> list[tuple[str, list[int]]]:
    """Every package id with its versions (ascending), ordered by id."""
    if not root.is_dir():
        return []
    packages = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name in RESERVED_IDS or entry.name.startswith("."):
            continue
        if not PACKAGE_ID_PATTERN.match(entry.name):
            continue
        found = versions(root, entry.name)
        if found:
            packages.append((entry.name, found))
    return packages


def staging_dir(target: Path) -> Path:
    """A fresh sibling of `target` matching the staging convention, so
    `sweep_stale_siblings` removes it if the process dies before publishing."""
    return target.parent / f".{target.name}.tmp-{uuid4().hex}"


def publish_directory(stage: Path, target: Path) -> None:
    """Atomically rename a fully written staging directory onto `target`."""
    os.replace(stage, target)


def sweep_stale_siblings(target: Path) -> list[Path]:
    """Remove any `.{target.name}.tmp-*` staging directory beside `target`.

    A killed run can leave exactly one such sibling next to the target it never
    got to publish. A run that regenerates over an existing directory stages
    beside *that* one, which is the `..{target.name}.tmp-*` form. Removes only
    directories matching those patterns — never `target` itself and never an
    unrelated sibling.
    """
    removed: list[Path] = []
    if not target.parent.is_dir():
        return removed
    stale_dirs = set(target.parent.glob(f".{target.name}.tmp-*"))
    stale_dirs |= set(target.parent.glob(f"..{target.name}.tmp-*"))
    for stale in sorted(stale_dirs):
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)
            removed.append(stale)
    return removed


def read_status(version_folder: Path) -> dict[str, Any] | None:
    path = version_folder / STATUS_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_status(version_folder: Path, **fields: Any) -> dict[str, Any]:
    """Merge `fields` into the version's status, writing atomically.

    Written beside the target then renamed, so a reader (or a crash) never sees
    half a file. Returns the status as written.
    """
    version_folder.mkdir(parents=True, exist_ok=True)
    current = read_status(version_folder) or {}
    current.update(fields)
    if current.get("status") not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    temp = version_folder / f".{STATUS_FILE}.{uuid4().hex}.tmp"
    temp.write_text(json.dumps(current, indent=2), encoding="utf-8")
    os.replace(temp, version_folder / STATUS_FILE)
    return current


RENDER_KEYS: Final = ("still", "turntable", "room-still", "room-turntable")


def render_key(kind: str, room: bool) -> str:
    return f"room-{kind}" if room else kind


def write_render_status(version_folder: Path, key: str, **fields: Any) -> dict[str, Any]:
    """Merge `fields` into one render's entry under `renders` in the version's
    status, writing atomically. Each entry is `queued → running →
    succeeded|failed` with its tier and estimate, so two renders requested back
    to back show the second as `queued` until the first finishes."""
    if key not in RENDER_KEYS:
        raise ValueError(f"unknown render key {key!r}")
    current = read_status(version_folder) or {}
    renders = dict(current.get("renders") or {})
    entry = dict(renders.get(key) or {})
    entry.update(fields)
    if entry.get("status") not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    renders[key] = entry
    return write_status(version_folder, status=current.get("status", "queued"), renders=renders)


def merge_scene_record(target: Path, key: str, record: dict[str, Any]) -> None:
    """Record one render's description in `target/scene.json` under `key`
    ("still" / "turntable"), keeping the other kind's record. Atomic."""
    path = target / "scene.json"
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {}
    existing[key] = record
    temp = target / f".scene.json.{uuid4().hex}.tmp"
    temp.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def sweep_orphaned_statuses(root: Path, *, reason: str = "the service restarted") -> int:
    """Mark every `queued`/`running` build or render under `root` as `failed`.

    No job queue survives a restart, so a status still `queued` or `running`
    from a previous process is not actually running. Returns how many entries
    were changed. Never raises for one unreadable folder.
    """
    changed = 0
    folders = [
        version_dir(root, package_id, number)
        for package_id, found in list_packages(root)
        for number in found
    ] + [
        shell_version_dir(root, slug, number)
        for slug, found in list_shells(root)
        for number in found
    ]
    for folder in folders:
        status = read_status(folder)
        if status is None:
            continue
        now = datetime.now(UTC).isoformat()
        if status.get("status") in ("queued", "running"):
            write_status(folder, status="failed", finished_at=now, error=reason)
            changed += 1
        for key, entry in list((status.get("renders") or {}).items()):
            if entry.get("status") in ("queued", "running"):
                write_render_status(folder, key, status="failed", finished_at=now, error=reason)
                changed += 1
    return changed
