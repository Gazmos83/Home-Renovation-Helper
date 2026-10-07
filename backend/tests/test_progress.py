"""studio-conversation: how far a piece has come, from the house file and the version folder."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.agent import house_file, progress
from app.blender import storage

ITEM = {
    "aspect": "brief",
    "expected": "two drawers",
    "expected_source": "brief",
    "observed": "one drawer",
    "image": 1,
    "severity": "major",
}


def _piece(session: Session, root: Path, status: str = "succeeded") -> Path:
    house_file.record_piece(session, "hall-bench", "Hall bench", brief={"room": "Hall"})
    house_file.record_version(session, "hall-bench", 1)
    folder = storage.version_dir(root, "hall-bench", 1)
    storage.write_status(folder, status=status)
    return folder


def _read(session: Session, root: Path, brief: bool = True) -> dict:
    return progress.piece_progress(session, root, "hall-bench", brief_confirmed=brief)


def _done(result: dict) -> list[str]:
    return [s["step"] for s in result["steps"] if s["done"]]


def test_a_thread_with_no_piece_reports_only_the_brief(db_session: Session, render_root: Path) -> None:
    fresh = progress.piece_progress(db_session, render_root, None, brief_confirmed=False)
    assert fresh["package_id"] is None
    assert _done(fresh) == []
    assert fresh["next_step"] == "Describe the piece you want"

    confirmed = progress.piece_progress(db_session, render_root, None, brief_confirmed=True)
    assert _done(confirmed) == ["brief"]
    assert confirmed["next_step"] == "Ask for the piece to be designed"


def test_a_queued_build_is_waited_for(db_session: Session, render_root: Path) -> None:
    _piece(db_session, render_root, status="queued")
    result = _read(db_session, render_root)
    assert _done(result) == ["brief", "piece"]
    assert result["latest_version"] == 1
    assert result["build_status"] == "queued"
    assert result["next_step"] == "Wait for the build to finish"


def test_a_failed_build_says_so(db_session: Session, render_root: Path) -> None:
    _piece(db_session, render_root, status="failed")
    assert "failed" in _read(db_session, render_root)["next_step"]


def test_a_built_version_names_its_screenshot_by_route(db_session: Session, render_root: Path) -> None:
    folder = _piece(db_session, render_root)
    (folder / "screenshot.png").write_bytes(b"png")
    result = _read(db_session, render_root)
    assert _done(result) == ["brief", "piece", "built"]
    assert result["screenshot"] == "/packages/hall-bench/versions/1/files/screenshot.png"
    assert result["still"] is None
    assert result["viewer"] is None
    assert result["next_step"] == "Ask for a draft render"
    assert str(render_root) not in repr(result)


def test_a_draft_turntable_reads_its_tier_from_the_status(db_session: Session, render_root: Path) -> None:
    folder = _piece(db_session, render_root)
    storage.write_render_status(folder, "turntable", status="succeeded", tier="draft")
    result = _read(db_session, render_root)
    assert "rendered" in _done(result)
    assert next(s for s in result["steps"] if s["step"] == "rendered")["detail"] == "draft"
    assert result["next_step"] == "Ask for a review of the piece"


def test_the_viewer_is_named_only_once_the_turntable_is_published(db_session: Session, render_root: Path) -> None:
    folder = _piece(db_session, render_root)
    storage.write_render_status(folder, "turntable", status="running", tier="draft")
    (folder / "viewer.html").write_text("<html></html>")
    assert _read(db_session, render_root)["viewer"] is None  # no frame yet

    (folder / "frames").mkdir()
    (folder / "frames" / "frame_000.png").write_bytes(b"png")
    assert _read(db_session, render_root)["viewer"] == "/packages/hall-bench/versions/1/files/viewer.html"


def test_a_running_render_is_not_yet_rendered(db_session: Session, render_root: Path) -> None:
    folder = _piece(db_session, render_root)
    storage.write_render_status(folder, "turntable", status="running", tier="draft")
    assert "rendered" not in _done(_read(db_session, render_root))


def test_a_review_counts_only_its_open_items(db_session: Session, render_root: Path) -> None:
    _piece(db_session, render_root)
    review = house_file.record_review(
        db_session, "hall-bench", 1, ["screenshot.png"], [ITEM, {**ITEM, "aspect": "material"}]
    )
    result = _read(db_session, render_root)
    assert "reviewed" in _done(result)
    assert result["open_review_items"] == 2

    for item in house_file.items_of(db_session, review.id):
        house_file.set_item_status(db_session, item.id, "resolved")
    closed = _read(db_session, render_root)
    assert "reviewed" in _done(closed)
    assert closed["open_review_items"] == 0


def test_a_review_of_an_older_version_does_not_count(db_session: Session, render_root: Path) -> None:
    _piece(db_session, render_root)
    house_file.record_review(db_session, "hall-bench", 1, ["screenshot.png"], [ITEM])
    house_file.record_version(db_session, "hall-bench", 2, revised_from=1, changes=["more shelves"])
    storage.write_status(storage.version_dir(render_root, "hall-bench", 2), status="succeeded")
    result = _read(db_session, render_root)
    assert result["latest_version"] == 2
    assert "reviewed" not in _done(result)


def test_a_detail_still_and_a_final_job_complete_the_ladder(db_session: Session, render_root: Path) -> None:
    folder = _piece(db_session, render_root)
    storage.write_render_status(folder, "turntable", status="succeeded", tier="draft")
    house_file.record_review(db_session, "hall-bench", 1, ["screenshot.png"], [])
    storage.write_render_status(folder, "detail-still", status="succeeded", tier="final")
    detailed = _read(db_session, render_root)
    assert "detail" in _done(detailed)
    assert detailed["next_step"] == "Ask for a final render"

    storage.write_render_status(folder, "still", status="succeeded", tier="final")
    result = _read(db_session, render_root)
    assert _done(result) == ["brief", "piece", "built", "rendered", "reviewed", "detail", "final"]
    assert result["next_step"].startswith("Every step is done")


def test_a_package_made_without_a_brief_does_not_ask_for_one(db_session: Session, render_root: Path) -> None:
    house_file.record_piece(db_session, "hall-bench", "Hall bench")
    house_file.record_version(db_session, "hall-bench", 1)
    storage.write_status(storage.version_dir(render_root, "hall-bench", 1), status="succeeded")
    result = _read(db_session, render_root, brief=False)
    assert "brief" not in _done(result)
    assert result["next_step"] == "Ask for a draft render"


def test_open_extension_requests_of_the_piece_are_listed(db_session: Session, render_root: Path) -> None:
    _piece(db_session, render_root)
    house_file.record_extension_request(db_session, "bevel_mm", "a bevelled edge", package_id="hall-bench")
    house_file.record_extension_request(db_session, "inlay", "an inlay", package_id="other")
    assert _read(db_session, render_root)["open_requests"] == [
        {"field": "bevel_mm", "request": "a bevelled edge"}
    ]


def test_the_readiness_helpers_match_what_the_foreman_used(db_session: Session, render_root: Path) -> None:
    folder = _piece(db_session, render_root)
    assert not progress.review_ready(render_root, "hall-bench", 1)
    (folder / "screenshot.png").write_bytes(b"png")
    assert progress.review_ready(render_root, "hall-bench", 1)
    assert not progress.detail_ready(render_root, "hall-bench", 1)
    (folder / "model.blend").write_bytes(b"blend")
    assert progress.detail_ready(render_root, "hall-bench", 1)
    assert not progress.detail_ready(render_root, None, 1)
