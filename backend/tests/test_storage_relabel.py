"""two-tier-renders: render files recorded at the removed `preview` tier read `draft`."""

from __future__ import annotations

import json
from pathlib import Path

from app.blender import storage


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tree(root: Path) -> dict[str, Path]:
    piece = storage.version_dir(root, "hall-bench", 2)
    shell = storage.shell_version_dir(root, "flat", 1)
    room = storage.composition_version_dir(root, "wohnen", 1)
    files = {
        "status": piece / "status.json",
        "scene": piece / "scene.json",
        "room": piece / "room" / "scene.json",
        "detail": piece / "detail" / "scene.json",
        "variant": piece / "variants" / "walnut-preview" / "scene.json",
        "shell": shell / "scene.json",
        "composition": room / "status.json",
        "staging": piece / "variants" / ".oak-preview.staging" / "scene.json",
    }
    _write(files["status"], {"status": "succeeded", "renders": {
        "turntable": {"status": "succeeded", "tier": "preview"},
        "still": {"status": "succeeded", "tier": "final"},
    }})
    for name in ("scene", "room", "detail", "variant", "shell", "staging"):
        _write(files[name], {"tier": "preview", "resolution": 1000})
    _write(files["composition"], {"status": "succeeded", "renders": {"turntable": {"tier": "draft"}}})
    (piece / "variants" / "walnut-preview" / "still.png").write_bytes(b"png")
    return files


def test_preview_records_are_relabelled_draft_and_nothing_else_changes(tmp_path: Path) -> None:
    files = _tree(tmp_path)
    image = (files["variant"].parent / "still.png").read_bytes()

    assert storage.relabel_preview_files(tmp_path) == 6

    status = _read(files["status"])
    assert status["renders"]["turntable"]["tier"] == "draft"
    assert status["renders"]["still"]["tier"] == "final"
    for name in ("scene", "room", "detail", "variant", "shell"):
        assert _read(files[name]) == {"tier": "draft", "resolution": 1000}
    # The variant keeps its folder name and its picture.
    assert files["variant"].parent.name == "walnut-preview"
    assert (files["variant"].parent / "still.png").read_bytes() == image
    # A hidden staging folder is not a published render.
    assert _read(files["staging"])["tier"] == "preview"


def test_a_second_run_changes_nothing(tmp_path: Path) -> None:
    files = _tree(tmp_path)
    storage.relabel_preview_files(tmp_path)
    before = {name: path.read_bytes() for name, path in files.items()}
    assert storage.relabel_preview_files(tmp_path) == 0
    assert {name: path.read_bytes() for name, path in files.items()} == before


def test_an_unreadable_record_is_skipped(tmp_path: Path) -> None:
    piece = storage.version_dir(tmp_path, "hall-bench", 1)
    piece.mkdir(parents=True)
    (piece / "status.json").write_text("{not json", encoding="utf-8")
    _write(piece / "scene.json", {"tier": "preview"})
    assert storage.relabel_preview_files(tmp_path) == 1
    assert _read(piece / "scene.json")["tier"] == "draft"
