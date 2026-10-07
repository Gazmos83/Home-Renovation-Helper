"""model-assets: type from bytes, size cap, zip safety and reference checks, storage."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from sqlalchemy import text

from app.assets.models import Limits, ModelRefused, add_model, model_dir
from tests import model_fixtures as fx

LIMITS = Limits(max_bytes=2_000_000, max_entries=20, max_unpacked_bytes=1_000_000)


@pytest.fixture
def session(db_session):
    db_session.execute(text("DELETE FROM model_assets"))
    db_session.commit()
    yield db_session
    db_session.rollback()
    db_session.execute(text("DELETE FROM model_assets"))
    db_session.commit()


def upload(session, root: Path, content: bytes, name: str = "armchair.glb", limits: Limits = LIMITS):
    return add_model(
        session, root, io.BytesIO(content), name="armchair", width_mm=800, depth_mm=700, height_mm=900,
        original_name=name, limits=limits,
    )


def stored(root: Path) -> list[str]:
    folder = root / "models"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def refused(session, root: Path, content: bytes, status: int, *phrases: str, **kw) -> None:
    with pytest.raises(ModelRefused) as caught:
        upload(session, root, content, **kw)
    assert caught.value.status == status
    for phrase in phrases:
        assert phrase in caught.value.reason, caught.value.reason
    assert stored(root) == [], "nothing is kept after a refusal"


def test_a_glb_is_accepted_and_stored_as_checking(session, tmp_path: Path) -> None:
    row = upload(session, tmp_path, fx.glb())
    assert (row.kind, row.state, row.entry) == ("glb", "checking", "model.glb")
    assert (row.width_mm, row.depth_mm, row.height_mm) == (800, 700, 900)
    assert (model_dir(tmp_path, row.id) / "model.glb").read_bytes() == fx.glb()


def test_a_gltf_zip_and_an_obj_zip_are_accepted_and_unpacked(session, tmp_path: Path) -> None:
    gltf = upload(session, tmp_path, fx.gltf_zip(), "chair.zip")
    obj = upload(session, tmp_path, fx.obj_zip(), "box.zip")
    assert (gltf.kind, gltf.entry) == ("gltf", "box.gltf")
    assert (obj.kind, obj.entry) == ("obj", "box.obj")
    assert sorted(p.name for p in model_dir(tmp_path, obj.id).iterdir()) == ["box.mtl", "box.obj", "wood.png"]


def test_a_blend_file_is_refused_with_415(session, tmp_path: Path) -> None:
    refused(session, tmp_path, b"BLENDER-v405" + b"\x00" * 100, 415, ".blend file is not accepted", name="chair.glb")


@pytest.mark.parametrize("content", [b"%PDF-1.7", b"Kaydara FBX Binary  \x00", b"solid box\n"], ids=["pdf", "fbx", "stl"])
def test_other_types_are_refused_with_415(session, tmp_path: Path, content: bytes) -> None:
    refused(session, tmp_path, content + b"\x00" * 64, 415, "only a GLB file")


def test_an_oversized_file_is_refused_with_413_leaving_no_partial_file(session, tmp_path: Path) -> None:
    small = Limits(max_bytes=500, max_entries=20, max_unpacked_bytes=1_000_000)
    refused(session, tmp_path, fx.glb(), 413, "larger than", limits=small)


def test_a_glb_of_another_version_or_naming_an_outside_file_is_refused(session, tmp_path: Path) -> None:
    refused(session, tmp_path, fx.glb(version=1), 415, "version 2")
    refused(session, tmp_path, fx.glb({"images": [{"uri": "wood.png"}]}), 415, "'wood.png'", "outside the GLB")


@pytest.mark.parametrize("entry", ["../../app/main.py", "/etc/passwd", "C:/evil.png", "a\\..\\b.png"])
def test_an_unsafe_zip_entry_is_refused_naming_it(session, tmp_path: Path, entry: str) -> None:
    content = fx.zipped({"box.obj": fx.obj_text(), "box.mtl": "newmtl Wood\n", entry: b"x"})
    refused(session, tmp_path, content, 415, repr(entry))


def test_a_symbolic_link_in_a_zip_is_refused(session, tmp_path: Path) -> None:
    import zipfile

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("box.obj", fx.obj_text())
        archive.writestr("box.mtl", "newmtl Wood\n")
        link = zipfile.ZipInfo("wood.png")
        link.external_attr = (0o120777 << 16)
        archive.writestr(link, "/etc/passwd")
    refused(session, tmp_path, out.getvalue(), 415, "'wood.png'", "is a link")


def test_a_remote_gltf_texture_is_refused_naming_it(session, tmp_path: Path) -> None:
    refused(session, tmp_path, fx.gltf_zip("https://example.com/wood.png"), 415, "'https://example.com/wood.png'")


def test_a_gltf_naming_a_missing_file_is_refused(session, tmp_path: Path) -> None:
    refused(session, tmp_path, fx.gltf_zip("missing.png"), 415, "'missing.png'", "does not contain")


def test_a_missing_material_file_is_refused_naming_it(session, tmp_path: Path) -> None:
    refused(session, tmp_path, fx.obj_zip(mtl=False), 415, "'box.mtl'", "does not contain")


def test_a_missing_or_escaping_texture_is_refused(session, tmp_path: Path) -> None:
    refused(session, tmp_path, fx.obj_zip(texture="oak.png"), 415, "'oak.png'")
    refused(session, tmp_path, fx.obj_zip(texture="../../secret.png"), 415, "outside the upload")


def test_two_model_files_or_none_are_refused(session, tmp_path: Path) -> None:
    two = fx.zipped({"a.obj": fx.obj_text(), "b.obj": fx.obj_text(), "box.mtl": "newmtl Wood\n"})
    refused(session, tmp_path, two, 415, "exactly one", "holds 2")
    refused(session, tmp_path, fx.zipped({"wood.png": b"x"}), 415, "exactly one")


def test_an_unexpected_extension_is_refused(session, tmp_path: Path) -> None:
    refused(session, tmp_path, fx.zipped({"box.obj": fx.obj_text(), "box.mtl": "", "run.py": "x"}), 415, "'run.py'")


def test_the_entry_count_and_unpacked_size_caps_hold(session, tmp_path: Path) -> None:
    many = {f"t{i}.png": b"x" for i in range(25)}
    refused(session, tmp_path, fx.zipped({"box.obj": fx.obj_text(), "box.mtl": "", **many}), 415, "entries", "at most 20")
    big = fx.zipped({"box.obj": fx.obj_text(), "box.mtl": "", "huge.png": b"\x00" * 1_200_000})
    refused(session, tmp_path, big, 415, "unpacks to more than")
