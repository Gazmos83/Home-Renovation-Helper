"""furniture-packages: the filesystem records, ids, resolve and staging."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.blender import storage


def test_the_build_files_are_exactly_the_six() -> None:
    assert set(storage.BUILD_FILES) == {
        "model.glb", "model.blend", "spec.json", "cutlist.csv", "hardware.csv", "screenshot.png",
    }
    assert storage.BUILD_FILES["model.glb"] == "model/gltf-binary"


def test_the_served_set_adds_renders_and_status() -> None:
    assert {"still.png", "viewer.html", "scene.json", "status.json"} <= set(storage.SERVED_FILES)
    assert "input.json" not in storage.SERVED_FILES


@pytest.mark.parametrize("good", ["a", "hall-bench", "a" * 64, "9lives"])
def test_a_plain_slug_is_a_package_id(good: str) -> None:
    assert storage.validate_package_id(good) == good


@pytest.mark.parametrize(
    "bad", ["", "-x", "Hall", "a/b", "..", "a..b", "a b", "a" * 65, "x.y", "/abs", "benchmark"]
)
def test_anything_else_is_refused(bad: str) -> None:
    with pytest.raises(storage.InvalidPackageId):
        storage.validate_package_id(bad)


def test_next_version_follows_the_existing_folders(tmp_path: Path) -> None:
    assert storage.next_version(tmp_path, "desk") == 1
    storage.version_dir(tmp_path, "desk", 1).mkdir(parents=True)
    storage.version_dir(tmp_path, "desk", 2).mkdir()
    (tmp_path / "desk" / "notes").mkdir()
    assert storage.versions(tmp_path, "desk") == [1, 2]
    assert storage.next_version(tmp_path, "desk") == 3


def test_a_version_must_be_a_positive_integer(tmp_path: Path) -> None:
    for bad in (0, -1, True, "1"):
        with pytest.raises(ValueError):
            storage.version_dir(tmp_path, "desk", bad)  # type: ignore[arg-type]


def test_list_packages_skips_benchmark_hidden_and_empty(tmp_path: Path) -> None:
    storage.version_dir(tmp_path, "b-desk", 1).mkdir(parents=True)
    storage.version_dir(tmp_path, "a-bench", 1).mkdir(parents=True)
    storage.version_dir(tmp_path, "a-bench", 2).mkdir()
    (tmp_path / "benchmark" / "v1").mkdir(parents=True)
    (tmp_path / ".hidden" / "v1").mkdir(parents=True)
    (tmp_path / "empty").mkdir()
    assert storage.list_packages(tmp_path) == [("a-bench", [1, 2]), ("b-desk", [1])]


def test_list_packages_of_a_missing_root_is_empty(tmp_path: Path) -> None:
    assert storage.list_packages(tmp_path / "nope") == []


def test_resolve_joins_a_relative_path_onto_the_root(tmp_path: Path) -> None:
    assert storage.resolve(tmp_path, "a/b.txt") == (tmp_path / "a" / "b.txt").resolve()


def test_resolve_refuses_dot_dot_escape(tmp_path: Path) -> None:
    with pytest.raises(storage.PathEscapesRoot):
        storage.resolve(tmp_path, "../outside")


def test_resolve_refuses_an_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(storage.PathEscapesRoot):
        storage.resolve(tmp_path, "/etc/passwd")


def test_resolve_refuses_a_symlink_escaping_the_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside)
    with pytest.raises(storage.PathEscapesRoot):
        storage.resolve(root, "link/secret.txt")


def test_sweep_removes_only_matching_staging_directories(tmp_path: Path) -> None:
    target = tmp_path / "v1"
    target.mkdir()
    stale = tmp_path / ".v1.tmp-abc"
    regen = tmp_path / "..v1.tmp-def"
    keep_other = tmp_path / ".v2.tmp-abc"
    unrelated = tmp_path / "v1-copy"
    for folder in (stale, regen, keep_other, unrelated):
        folder.mkdir()
    removed = storage.sweep_stale_siblings(target)
    assert sorted(removed) == sorted([stale, regen])
    assert target.is_dir() and keep_other.is_dir() and unrelated.is_dir()


def test_sweep_is_a_no_op_without_a_parent_or_stale_siblings(tmp_path: Path) -> None:
    assert storage.sweep_stale_siblings(tmp_path / "missing" / "v1") == []
    (tmp_path / "v1").mkdir()
    assert storage.sweep_stale_siblings(tmp_path / "v1") == []


def test_staging_dir_matches_the_sweep_convention(tmp_path: Path) -> None:
    target = tmp_path / "v1"
    stage = storage.staging_dir(target)
    stage.mkdir()
    assert storage.sweep_stale_siblings(target) == [stage]


def test_publish_directory_renames_atomically(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "f.txt").write_text("x")
    storage.publish_directory(stage, tmp_path / "out")
    assert (tmp_path / "out" / "f.txt").read_text() == "x"
    assert not stage.exists()


def test_status_round_trips_and_merges(tmp_path: Path) -> None:
    folder = tmp_path / "v1"
    assert storage.read_status(folder) is None
    storage.write_status(folder, status="queued", kind="build")
    storage.write_status(folder, status="running", started_at="t0")
    assert storage.read_status(folder) == {"status": "running", "kind": "build", "started_at": "t0"}
    assert not list(folder.glob(".*.tmp")), "no temp file is left behind"


def test_an_unknown_status_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        storage.write_status(tmp_path / "v1", status="done")
