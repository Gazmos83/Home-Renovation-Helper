"""delete-piece: deleting a whole piece with every version, its records and its folder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.agent import house_file
from app.agent.house_file import HouseFileError, PieceMissing
from app.blender import storage
from app.db.models import (
    GeneratorExtensionRequest,
    Piece,
    PieceVersion,
    Thread,
    ThreadPiece,
)
from tests.test_delete_version import (  # noqa: F401 - fixture
    _counts,
    _piece,
    _records,
    session,
)


def test_a_piece_with_an_approved_and_priced_version_is_deleted(session, render_root: Path) -> None:  # noqa: F811
    _piece(session, render_root, versions=(1, 2))
    _records(session, 1)
    _records(session, 2)
    house_file.approve_version(session, "hall-bench", 2)
    thread = house_file.create_thread(session, "Bench", package_id="hall-bench")
    session.commit()
    house_file.delete_piece(session, render_root, "hall-bench", [thread.id])
    assert not (render_root / "hall-bench").exists()
    assert not any(name.startswith(".deleting") for name in (p.name for p in render_root.iterdir()))
    assert session.get(Piece, "hall-bench") is None
    assert session.scalars(select(PieceVersion).where(PieceVersion.package_id == "hall-bench")).all() == []
    assert session.scalars(select(ThreadPiece).where(ThreadPiece.package_id == "hall-bench")).all() == []
    assert session.get(Thread, thread.id) is None
    assert _counts(session) == (0, 0, 0, 0, 0, 0)


def test_what_would_go_is_listed_and_nothing_is_deleted(session, render_root: Path) -> None:  # noqa: F811
    _piece(session, render_root, versions=(1, 2, 3))
    _records(session, 3)
    house_file.approve_version(session, "hall-bench", 3)
    first = house_file.create_thread(session, "One", package_id="hall-bench")
    second = house_file.create_thread(session, "Two")
    house_file.add_build(session, second.id, "hall-bench")
    other = house_file.create_thread(session, "Other", package_id="desk")
    house_file.add_build(session, other.id, "hall-bench")
    session.commit()
    summary = house_file.piece_deletion(session, render_root, "hall-bench")
    assert summary["name"] == "Hall bench"
    assert summary["versions"] == [1, 2, 3]
    assert summary["approved"] == [{"version": 3, "priced": True}]
    assert summary["conversations"] == [str(first.id), str(second.id)]
    assert summary["refusal"] is None
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]


def test_a_piece_placed_in_a_composition_is_refused(session, render_root: Path) -> None:  # noqa: F811
    _piece(session, render_root)
    folder = storage.composition_version_dir(render_root, "living-room", 3)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps({
        "scope": {"room": "Living room"},
        "items": [{"id": "bench", "type": "piece", "package_id": "hall-bench", "version": 2}],
    }), encoding="utf-8")
    with pytest.raises(HouseFileError, match="Living room version 3"):
        house_file.delete_piece(session, render_root, "hall-bench", [])
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]
    assert session.get(Piece, "hall-bench") is not None


@pytest.mark.parametrize("status", ["queued", "running"])
def test_a_piece_still_building_is_refused(session, render_root: Path, status: str) -> None:  # noqa: F811
    _piece(session, render_root)
    storage.write_status(storage.version_dir(render_root, "hall-bench", 3), status=status)
    with pytest.raises(HouseFileError, match="still building"):
        house_file.delete_piece(session, render_root, "hall-bench", [])
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]


def test_the_id_is_free_again_after_the_delete(session, render_root: Path) -> None:  # noqa: F811
    _piece(session, render_root, versions=(1, 2))
    house_file.delete_version(session, render_root, "hall-bench", 2)
    assert storage.next_version(render_root, "hall-bench") == 3
    house_file.delete_piece(session, render_root, "hall-bench", [])
    assert storage.next_version(render_root, "hall-bench") == 1


def test_extension_requests_are_kept(session, render_root: Path) -> None:  # noqa: F811
    _piece(session, render_root, versions=(1,))
    house_file.record_extension_request(session, "modules.0.bevel_mm", "round the edges", package_id="hall-bench")
    session.commit()
    house_file.delete_piece(session, render_root, "hall-bench", [])
    assert len(session.scalars(select(GeneratorExtensionRequest)).all()) == 1


def test_an_unknown_piece_is_missing(session, render_root: Path) -> None:  # noqa: F811
    with pytest.raises(PieceMissing):
        house_file.piece_deletion(session, render_root, "no-such-piece")


def test_a_failed_commit_moves_the_package_back(session, render_root: Path, monkeypatch) -> None:  # noqa: F811
    _piece(session, render_root, versions=(1,))

    def broken() -> None:
        raise RuntimeError("database down")

    monkeypatch.setattr(session, "commit", broken)
    with pytest.raises(RuntimeError):
        house_file.delete_piece(session, render_root, "hall-bench", [])
    assert storage.versions(render_root, "hall-bench") == [1]
