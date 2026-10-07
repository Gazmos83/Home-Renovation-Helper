"""Model uploads (model-assets): type from bytes, zip safety, reference checks, storage.

A model is a GLB (binary glTF 2), or a zip holding exactly one `.gltf` with its
buffers and images, or exactly one `.obj` with its `.mtl` and textures. Every
check runs before anything is unpacked: entry paths, links, counts and sizes,
extensions, and every file a glTF, OBJ or MTL names. Nothing in a model is
executed here; the headless check job imports it later (`check_model.py`).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Final
from urllib.parse import unquote
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelAsset

CHUNK_BYTES: Final = 1024 * 1024
ALLOWED_EXTENSIONS: Final = frozenset({"gltf", "bin", "obj", "mtl", "png", "jpg", "jpeg"})
MODEL_EXTENSIONS: Final = {"gltf": "gltf", "obj": "obj"}
# Texture statements in an MTL file; the file name is the statement's last token.
MTL_MAPS: Final = re.compile(r"^\s*(map_\w+|bump|disp|decal|norm|refl)\s+(.+?)\s*$", re.IGNORECASE)
MTLLIB: Final = re.compile(r"^\s*mtllib\s+(.+?)\s*$", re.IGNORECASE)
CONTENT_TYPES: Final = {
    "glb": "model/gltf-binary",
    "gltf": "model/gltf+json",
    "bin": "application/octet-stream",
    "obj": "text/plain",
    "mtl": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}
UNSUPPORTED: Final = (
    "only a GLB file, or a zip holding one glTF or one OBJ model with its files, is accepted"
)


class ModelRefused(Exception):
    """An upload or delete refused, with the HTTP status and a reason safe to show."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class Limits:
    max_bytes: int
    max_entries: int
    max_unpacked_bytes: int


def model_dir(root: Path, model_id: UUID) -> Path:
    return root / "models" / str(model_id)


# --- the upload stream ---------------------------------------------------------------


def _spool(stream: BinaryIO, limit: int, into: Path) -> int:
    """Copy `stream` to `into` under `limit`; on refusal nothing is left behind."""
    size = 0
    try:
        with into.open("wb") as handle:
            while chunk := stream.read(CHUNK_BYTES):
                size += len(chunk)
                if size > limit:
                    raise ModelRefused(413, f"the model is larger than {limit // (1024 * 1024)} MiB")
                handle.write(chunk)
    except BaseException:
        into.unlink(missing_ok=True)
        raise
    return size


def sniff(head: bytes) -> str | None:
    """`glb`, `zip` or `blend` from the first bytes, else `None`."""
    if head[:4] == b"glTF":
        return "glb"
    if head[:4] == b"PK\x03\x04":
        return "zip"
    if head[:7] == b"BLENDER":
        return "blend"
    return None


# --- references ------------------------------------------------------------------------


def _relative(reference: str, base: PurePosixPath, files: set[str], what: str) -> str:
    """The upload-relative path `reference` names from `base`, or a refusal naming it."""
    if not reference or "\\" in reference or ":" in reference or reference.startswith("/"):
        raise ModelRefused(415, f"{what} {reference!r} is not a relative file in the upload")
    target = base / reference
    parts: list[str] = []
    for part in target.parts:
        if part == "..":
            if not parts:
                raise ModelRefused(415, f"{what} {reference!r} points outside the upload")
            parts.pop()
        elif part not in (".", ""):
            parts.append(part)
    name = "/".join(parts)
    if name not in files:
        raise ModelRefused(415, f"{what} {reference!r} names a file the upload does not contain")
    return name


def _gltf_uris(document: dict) -> list[tuple[str, str]]:
    found = []
    for kind in ("buffers", "images"):
        for item in document.get(kind) or []:
            if isinstance(item, dict) and "uri" in item:
                found.append((kind[:-1], str(item["uri"])))
    return found


def check_gltf(document: object, base: PurePosixPath, files: set[str]) -> None:
    if not isinstance(document, dict):
        raise ModelRefused(415, "the glTF file is not a JSON object")
    for kind, uri in _gltf_uris(document):
        if uri.startswith("data:"):
            continue
        lowered = uri.lower()
        if lowered.startswith(("http:", "https:", "file:")) or uri.startswith("/"):
            raise ModelRefused(415, f"the glTF {kind} URI {uri!r} is not allowed; only files in the upload are")
        _relative(unquote(uri), base, files, f"the glTF {kind} URI")


def check_glb(path: Path) -> None:
    """A GLB is version 2 and names no file outside itself."""
    with path.open("rb") as handle:
        header = handle.read(20)
        if len(header) < 20:
            raise ModelRefused(415, "the GLB file is truncated")
        _magic, version, _length, chunk_length, chunk_type = struct.unpack("<4sIIII", header)
        if version != 2:
            raise ModelRefused(415, f"only GLB version 2 is accepted, not version {version}")
        if chunk_type != 0x4E4F534A:  # "JSON"
            raise ModelRefused(415, "the GLB file has no JSON chunk")
        try:
            document = json.loads(handle.read(chunk_length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise ModelRefused(415, "the GLB file's JSON chunk cannot be read") from None
    for kind, uri in _gltf_uris(document if isinstance(document, dict) else {}):
        if not uri.startswith("data:"):
            raise ModelRefused(415, f"the GLB {kind} URI {uri!r} names a file outside the GLB")


def check_obj(obj_text: str, base: PurePosixPath, files: set[str], read) -> None:
    for line in obj_text.splitlines():
        match = MTLLIB.match(line)
        if not match:
            continue
        for library in match.group(1).split():
            mtl = _relative(library, base, files, "the OBJ mtllib")
            mtl_base = PurePosixPath(mtl).parent
            for mtl_line in read(mtl).splitlines():
                mapped = MTL_MAPS.match(mtl_line)
                if mapped:
                    _relative(mapped.group(2).split()[-1], mtl_base, files, "the MTL texture")


# --- zips -------------------------------------------------------------------------------------


def _is_link(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def check_zip(path: Path, limits: Limits) -> tuple[zipfile.ZipFile, str, str]:
    """An open, checked zip, the model's kind (`gltf` or `obj`) and its entry name."""
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ModelRefused(415, "the zip file cannot be read") from None
    try:
        infos = archive.infolist()
        if len(infos) > limits.max_entries:
            raise ModelRefused(415, f"the zip holds {len(infos)} entries; at most {limits.max_entries} are allowed")
        files: set[str] = set()
        total = 0
        for info in infos:
            name = info.filename
            if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name) or "\\" in name:
                raise ModelRefused(415, f"the zip entry {name!r} has an absolute path")
            if ".." in PurePosixPath(name).parts:
                raise ModelRefused(415, f"the zip entry {name!r} points outside the upload")
            if _is_link(info):
                raise ModelRefused(415, f"the zip entry {name!r} is a link")
            if info.is_dir():
                continue
            extension = PurePosixPath(name).suffix.lower().lstrip(".")
            if extension not in ALLOWED_EXTENSIONS:
                raise ModelRefused(415, f"the zip entry {name!r} is not a model, material or texture file")
            total += info.file_size
            if total > limits.max_unpacked_bytes:
                raise ModelRefused(
                    415, f"the zip unpacks to more than {limits.max_unpacked_bytes // (1024 * 1024)} MiB"
                )
            files.add(name)
        models = [n for n in files if PurePosixPath(n).suffix.lower().lstrip(".") in MODEL_EXTENSIONS]
        if len(models) != 1:
            raise ModelRefused(
                415, "the zip must hold exactly one .gltf or .obj model" + (f"; it holds {len(models)}" if models else "")
            )
        entry = models[0]
        kind = MODEL_EXTENSIONS[PurePosixPath(entry).suffix.lower().lstrip(".")]

        def read(name: str) -> str:
            return archive.read(name).decode("utf-8", errors="replace")

        base = PurePosixPath(entry).parent
        if kind == "gltf":
            try:
                document = json.loads(archive.read(entry).decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise ModelRefused(415, f"the glTF file {entry!r} is not valid JSON") from None
            check_gltf(document, base, files)
        else:
            check_obj(read(entry), base, files, read)
        return archive, kind, entry
    except BaseException:
        archive.close()
        raise


def _extract(archive: zipfile.ZipFile, target: Path, limit: int) -> None:
    """Unpack every checked file, counting real bytes so a lying header cannot exceed `limit`."""
    written = 0
    for info in archive.infolist():
        if info.is_dir():
            continue
        destination = target.joinpath(*PurePosixPath(info.filename).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, destination.open("wb") as sink:
            while chunk := source.read(CHUNK_BYTES):
                written += len(chunk)
                if written > limit:
                    raise ModelRefused(415, f"the zip unpacks to more than {limit // (1024 * 1024)} MiB")
                sink.write(chunk)


# --- the library ---------------------------------------------------------------------------


def add_model(
    session: Session,
    root: Path,
    stream: BinaryIO,
    *,
    name: str,
    width_mm: int,
    depth_mm: int,
    height_mm: int,
    original_name: str,
    limits: Limits,
) -> ModelAsset:
    """Check and store one upload, recorded as `checking`; commits. Refusals leave nothing."""
    model_id = uuid4()
    (root / "models").mkdir(parents=True, exist_ok=True)
    folder = model_dir(root, model_id)
    with tempfile.TemporaryDirectory(dir=root / "models", prefix=".upload-") as scratch:
        spooled = Path(scratch) / "upload"
        size = _spool(stream, limits.max_bytes, spooled)
        with spooled.open("rb") as handle:
            found = sniff(handle.read(8))
        if found == "blend":
            raise ModelRefused(415, "a .blend file is not accepted; export the model as GLB, glTF or OBJ")
        if found is None:
            raise ModelRefused(415, UNSUPPORTED)
        staging = Path(scratch) / "files"
        staging.mkdir()
        if found == "glb":
            check_glb(spooled)
            kind, entry = "glb", "model.glb"
            shutil.copyfile(spooled, staging / entry)
        else:
            archive, kind, entry = check_zip(spooled, limits)
            with archive:
                _extract(archive, staging, limits.max_unpacked_bytes)
        os.replace(staging, folder)
    row = ModelAsset(
        id=model_id, name=name.strip()[:120], kind=kind, entry=entry, original_name=original_name[:512],
        size_bytes=size, width_mm=width_mm, depth_mm=depth_mm, height_mm=height_mm, state="checking",
    )
    session.add(row)
    try:
        session.commit()
    except BaseException:
        session.rollback()
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return row


def list_models(session: Session) -> list[ModelAsset]:
    return list(session.scalars(select(ModelAsset).order_by(ModelAsset.created_at)))


def get_model(session: Session, model_id: UUID) -> ModelAsset | None:
    return session.get(ModelAsset, model_id)


def stored_file(root: Path, model: ModelAsset, name: str) -> tuple[Path, str] | None:
    """A stored file of `model` by its exact relative name, with its content type."""
    folder = model_dir(root, model.id)
    if not name or name.startswith("/") or "\\" in name or ".." in PurePosixPath(name).parts:
        return None
    path = folder.joinpath(*PurePosixPath(name).parts)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        path.resolve().relative_to(folder.resolve())
    except ValueError:
        return None
    extension = "glb" if name == "model.glb" and model.kind == "glb" else path.suffix.lower().lstrip(".")
    content_type = CONTENT_TYPES.get(extension)
    return (path, content_type) if content_type else None


def record_check(session: Session, model: ModelAsset, report: dict | None, *, max_triangles: int, error: str | None) -> None:
    """Set `ready` or `refused` from the headless check's report. The caller commits."""
    if error or not report:
        model.state, model.reason = "refused", error or "the model could not be imported"
        return
    triangles = int(report.get("triangles") or 0)
    size = report.get("size_mm") or {}
    model.triangles = triangles
    model.measured_mm = {axis: round(float(size.get(axis, 0)), 1) for axis in ("x", "y", "z")}
    if triangles == 0:
        model.state, model.reason = "refused", "the model has no mesh"
    elif triangles > max_triangles:
        model.state, model.reason = "refused", f"the model has {triangles} triangles; at most {max_triangles} are allowed"
    else:
        model.state, model.reason = "ready", None


def delete_model(session: Session, root: Path, model: ModelAsset, used_by: list[str]) -> None:
    """Delete a model no composition places; commits. `used_by` names those that do."""
    if used_by:
        raise ModelRefused(409, f"{model.name!r} is placed in {', '.join(used_by)}; remove it there first")
    session.delete(model)
    session.commit()
    shutil.rmtree(model_dir(root, model.id), ignore_errors=True)
