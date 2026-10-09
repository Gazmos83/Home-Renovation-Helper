"""version-cleanup-and-inspection: deleting a piece version, its folder and its records."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.house_file import HouseFileError, VersionMissing
from app.blender import storage
from app.db.models import (
    CutListPricing,
    CutListPricingEntry,
    Piece,
    RenderFeedback,
    RenderRun,
    Review,
    ReviewItem,
    Thread,
    ThreadPiece,
)
from app.db.session import make_engine
from app.pricing import price_list
from tests.conftest import clean_house_file
from tests.pricing_helpers import clean_pricing

STORE = "delete-version-store"
ITEM = {
    "aspect": "proportion", "expected": "600 mm", "expected_source": "spec", "observed": "600 mm",
    "image": 1, "severity": "minor",
}


@pytest.fixture
def session(migrated_database: str) -> Iterator[Session]:
    engine = make_engine(migrated_database)
    clean_house_file(engine)
    clean_pricing(engine)
    with Session(engine) as s:
        s.execute(text(
            "INSERT INTO stores (store_key, source_site, name, url) "
            f"VALUES ('{STORE}', 'toom', 'S', 'https://toom.de') ON CONFLICT DO NOTHING"
        ))
        s.commit()
        yield s
        s.rollback()
    clean_house_file(engine)
    clean_pricing(engine)
    with Session(engine) as s:
        s.execute(text(f"DELETE FROM stores WHERE store_key = '{STORE}'"))
        s.commit()
    engine.dispose()


def _piece(session: Session, root: Path, versions=(1, 2, 3), package_id="hall-bench") -> None:
    house_file.record_piece(session, package_id, "Hall bench")
    for number in versions:
        house_file.record_version(session, package_id, number)
        folder = storage.version_dir(root, package_id, number)
        folder.mkdir(parents=True)
        storage.write_status(folder, status="succeeded")
    session.commit()


def _records(session: Session, version: int, package_id="hall-bench") -> None:
    """A review with two items, a rated draft render and a pricing with one entry."""
    house_file.record_review(session, package_id, version, ["still.png"], [ITEM, ITEM])
    run = RenderRun(
        id=uuid4(), package_id=package_id, version=version, render_key="still", tier="draft",
        outcome="succeeded", slot="builder", model="m", trace_id="b" * 32, started_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()
    session.add(RenderFeedback(run_id=run.id, rating="up"))
    entry = price_list.create_entry(
        session, key=f"panel:{package_id}-{version}", label="Birch 18", category="panel", unit="per_piece",
        base_cents=5990, sheet_length_mm=2500, sheet_width_mm=1250, thickness_mm=18,
    )
    pricing = CutListPricing(
        package_id=package_id, version=version, store_key=STORE, materials_cents=0, cut_service_cents=0,
        total_cents=0, complete=True, result={},
    )
    session.add(pricing)
    session.flush()
    session.add(CutListPricingEntry(pricing_id=pricing.id, entry_id=entry.id, cents_used=5990))
    session.commit()


def _count(session: Session, model, version: int | None = None) -> int:
    query = select(func.count()).select_from(model)
    if version is not None:
        query = query.where(model.version == version)
    return int(session.scalar(query))


def _counts(session: Session) -> tuple[int, ...]:
    return (
        _count(session, Review), _count(session, ReviewItem), _count(session, RenderRun),
        _count(session, RenderFeedback), _count(session, CutListPricing), _count(session, CutListPricingEntry),
    )


# --- refusals -----------------------------------------------------------------------------


def test_an_approved_version_is_refused_and_nothing_changes(session, render_root: Path) -> None:
    _piece(session, render_root)
    house_file.approve_version(session, "hall-bench", 3)
    session.commit()
    with pytest.raises(HouseFileError, match="unapprove version 3 first"):
        house_file.delete_version(session, render_root, "hall-bench", 3)
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]
    assert house_file.version_row(session, "hall-bench", 3) is not None


def test_a_version_placed_in_a_composition_is_refused_naming_it(session, render_root: Path) -> None:
    _piece(session, render_root)
    folder = storage.composition_version_dir(render_root, "living-room", 3)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(json.dumps({
        "scope": {"room": "Living room"},
        "items": [{"id": "bench", "type": "piece", "package_id": "hall-bench", "version": 2}],
    }), encoding="utf-8")
    with pytest.raises(HouseFileError, match="Living room version 3"):
        house_file.delete_version(session, render_root, "hall-bench", 2)
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]
    assert house_file.version_row(session, "hall-bench", 2) is not None


@pytest.mark.parametrize("status", ["queued", "running"])
def test_a_version_still_building_is_refused(session, render_root: Path, status: str) -> None:
    _piece(session, render_root)
    storage.write_status(storage.version_dir(render_root, "hall-bench", 2), status=status)
    with pytest.raises(HouseFileError, match="still building"):
        house_file.delete_version(session, render_root, "hall-bench", 2)
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]


def test_a_version_still_rendering_is_refused(session, render_root: Path) -> None:
    _piece(session, render_root)
    _records(session, 2)
    session.execute(text("UPDATE render_runs SET outcome = 'running'"))
    session.commit()
    before = _counts(session)
    with pytest.raises(HouseFileError, match="still rendering"):
        house_file.delete_version(session, render_root, "hall-bench", 2)
    assert _counts(session) == before
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]


def test_a_render_queued_in_the_status_file_is_refused(session, render_root: Path) -> None:
    _piece(session, render_root)
    storage.write_render_status(storage.version_dir(render_root, "hall-bench", 2), "still", status="queued")
    with pytest.raises(HouseFileError, match="still rendering"):
        house_file.delete_version(session, render_root, "hall-bench", 2)


def test_a_missing_version_is_refused(session, render_root: Path) -> None:
    _piece(session, render_root)
    with pytest.raises(VersionMissing):
        house_file.delete_version(session, render_root, "hall-bench", 9)
    with pytest.raises(VersionMissing):
        house_file.delete_version(session, render_root, "nothing-here", 1)
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]


# --- what goes -----------------------------------------------------------------------------


def test_the_records_of_the_deleted_version_go_and_the_others_stay(session, render_root: Path) -> None:
    _piece(session, render_root, versions=(1, 2, 3, 4))
    house_file.approve_version(session, "hall-bench", 4)
    _records(session, 2)
    _records(session, 3)
    assert house_file.delete_version(session, render_root, "hall-bench", 2) is False
    session.expire_all()
    for model in (Review, RenderRun, CutListPricing):
        assert _count(session, model, 2) == 0
        assert _count(session, model, 3) == 1
    assert _count(session, ReviewItem) == 2
    assert _count(session, RenderFeedback) == 1
    assert _count(session, CutListPricingEntry) == 1
    assert house_file.version_row(session, "hall-bench", 2) is None
    assert storage.versions(render_root, "hall-bench") == [1, 3, 4]
    assert house_file.approved_version_of(session, "hall-bench") == 4
    assert not list((render_root / "hall-bench").glob(".deleting-*"))


def test_a_notice_naming_the_version_keeps_its_text_and_loses_the_piece(session, render_root: Path) -> None:
    _piece(session, render_root)
    thread = house_file.create_thread(session, "Hall bench", package_id="hall-bench")
    text_ = "The draft turntable of hall-bench version 2 is ready."
    for version in (2, 3):
        house_file.add_notice(
            session, thread.id, after_messages=1, outcome="succeeded", tier="draft", text=text_,
            package_id="hall-bench", version=version,
        )
    session.commit()
    house_file.delete_version(session, render_root, "hall-bench", 2)
    session.expire_all()
    notices = house_file.notices_for(session, thread.id)
    assert [n.text for n in notices] == [text_, text_]
    assert sorted((n.package_id, n.version) for n in notices if n.version is not None) == [("hall-bench", 3)]
    assert sum(1 for n in notices if n.package_id is None and n.version is None) == 1


def test_the_last_version_deletes_the_piece_and_unbinds_its_conversations(session, render_root: Path) -> None:
    _piece(session, render_root, versions=(1,))
    thread = house_file.create_thread(session, "Hall bench", package_id="hall-bench")
    house_file.add_build(session, thread.id, "hall-bench")
    house_file.record_extension_request(session, "bevel_mm", "round the edges", package_id="hall-bench")
    session.commit()
    assert house_file.delete_version(session, render_root, "hall-bench", 1) is True
    session.expire_all()
    assert session.get(Piece, "hall-bench") is None
    assert not (render_root / "hall-bench").exists()
    assert storage.list_packages(render_root) == []
    kept = session.get(Thread, thread.id)
    assert kept is not None and kept.package_id is None
    assert _count(session, ThreadPiece) == 0
    assert [r.field for r in house_file.open_extension_requests(session)] == ["bevel_mm"]


def test_a_folder_that_cannot_be_moved_leaves_everything(session, render_root: Path, monkeypatch) -> None:
    _piece(session, render_root)
    _records(session, 2)
    before = _counts(session)

    def broken(*_args, **_kwargs):
        raise OSError("disk went away")

    monkeypatch.setattr(storage, "move_version_aside", broken)
    with pytest.raises(OSError):
        house_file.delete_version(session, render_root, "hall-bench", 2)
    monkeypatch.undo()
    session.expire_all()
    assert _counts(session) == before
    assert house_file.version_row(session, "hall-bench", 2) is not None
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]


def test_a_failed_commit_moves_the_folder_back(session, render_root: Path, monkeypatch) -> None:
    _piece(session, render_root)

    def broken() -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(session, "commit", broken)
    with pytest.raises(RuntimeError):
        house_file.delete_version(session, render_root, "hall-bench", 2)
    monkeypatch.undo()
    session.expire_all()
    assert house_file.version_row(session, "hall-bench", 2) is not None
    assert storage.versions(render_root, "hall-bench") == [1, 2, 3]
    assert not list((render_root / "hall-bench").glob(".deleting-*"))


def test_a_folder_only_version_is_deleted_and_its_number_not_reused(session, render_root: Path) -> None:
    for number in (1, 2):
        storage.version_dir(render_root, "desk", number).mkdir(parents=True)
    assert house_file.delete_version(session, render_root, "desk", 2) is False
    assert storage.versions(render_root, "desk") == [1]
    assert storage.next_version(render_root, "desk") == 3
