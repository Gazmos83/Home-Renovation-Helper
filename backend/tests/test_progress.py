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


def test_a_render_is_running_only_while_one_is_queued_or_running(db_session: Session, render_root: Path) -> None:
    folder = _piece(db_session, render_root)
    assert _read(db_session, render_root)["rendering"] is False
    for state, expected in (("queued", True), ("running", True), ("succeeded", False), ("failed", False)):
        storage.write_render_status(folder, "turntable", status=state, tier="draft")
        assert _read(db_session, render_root)["rendering"] is expected, state
    storage.write_render_status(folder, "turntable", status="succeeded", tier="draft")
    storage.write_render_status(folder, "still", status="running", tier="draft")
    assert _read(db_session, render_root)["rendering"] is True


def test_the_version_count_and_limit_are_reported(db_session: Session, render_root: Path) -> None:
    """version-cleanup-and-inspection: the Project panel's "N of 15 versions"."""
    assert progress.piece_progress(db_session, render_root, None, brief_confirmed=False)["version_count"] == 0
    _piece(db_session, render_root)
    for number in (2, 3):
        storage.version_dir(render_root, "hall-bench", number).mkdir()
    result = _read(db_session, render_root)
    assert (result["version_count"], result["max_versions"]) == (3, 15)


# --- the conversation's room (project-room-inspection) ---------------------------------

SQUARE = [[0, 0], [3000, 0], [3000, 2000], [0, 2000]]


def _thread_in(session: Session, room: str | None = None):
    thread = house_file.create_thread(session, "Bench")
    if room:
        house_file.set_thread_room(session, thread.id, house_file.upsert_room(session, room, SQUARE, 2500))
    return thread.id


def _compose(session: Session, root: Path, scope: str, name: str, *, model: bool) -> Path:
    composition = house_file.record_composition(session, scope, name)
    house_file.record_composition_version(session, composition, 1, None, [])
    folder = storage.composition_version_dir(root, composition.slug, 1)
    folder.mkdir(parents=True)
    if model:
        (folder / "model.glb").write_bytes(b"glb")
        (folder / "report.json").write_text("{}", encoding="utf-8")
    return folder


def test_a_thread_without_a_room_reports_none(db_session: Session, render_root: Path) -> None:
    assert progress.room_progress(db_session, render_root, _thread_in(db_session)) is None


def test_a_room_without_a_composition_has_no_3d_view(db_session: Session, render_root: Path) -> None:
    thread = _thread_in(db_session, "Hall")
    assert progress.room_progress(db_session, render_root, thread) == {
        "name": "Hall", "scope": "room", "slug": None, "model": None, "surfaces": None, "versions": [],
        "approved_version": None,
    }


def test_a_composed_room_names_its_model_and_surfaces_by_route(db_session: Session, render_root: Path) -> None:
    thread = _thread_in(db_session, "Hall")
    _compose(db_session, render_root, "room", "Hall", model=True)
    result = progress.room_progress(db_session, render_root, thread)
    assert result is not None
    slug = result["slug"]
    assert slug
    assert result["model"] == f"/compositions/{slug}/versions/1/files/model.glb"
    assert result["surfaces"] == f"/compositions/{slug}/versions/1/files/report.json"
    assert str(render_root) not in repr(result)


def test_a_latest_version_without_a_model_has_no_3d_view(db_session: Session, render_root: Path) -> None:
    thread = _thread_in(db_session, "Hall")
    _compose(db_session, render_root, "room", "Hall", model=False)
    result = progress.room_progress(db_session, render_root, thread)
    assert result is not None
    assert result["slug"] and result["model"] is None and result["surfaces"] is None


def test_an_apartment_scope_reports_the_apartment(db_session: Session, render_root: Path) -> None:
    thread = _thread_in(db_session)
    flat = house_file.upsert_apartment(
        db_session, "Flat", 2550, 120,
        [{"name": "Living", "corners_mm": SQUARE, "height_mm": None, "openings": []}],
    )
    house_file.set_thread_apartment(db_session, thread, flat)
    _compose(db_session, render_root, "apartment", "Flat", model=True)
    result = progress.room_progress(db_session, render_root, thread)
    assert result is not None
    assert (result["name"], result["scope"]) == ("Flat", "apartment")
    assert result["model"] == f"/compositions/{result['slug']}/versions/1/files/model.glb"


def test_the_newest_five_versions_are_listed_newest_first(db_session: Session, render_root: Path) -> None:
    thread = _thread_in(db_session, "Hall")
    composition = house_file.record_composition(db_session, "room", "Hall")
    for number in range(1, 7):
        house_file.record_composition_version(db_session, composition, number, number - 1 or None, [])
        folder = storage.composition_version_dir(render_root, composition.slug, number)
        folder.mkdir(parents=True)
        storage.write_status(folder, status="succeeded")
        (folder / "screenshot.png").write_bytes(b"png")
        if number != 2:
            (folder / "model.glb").write_bytes(b"glb")
    result = progress.room_progress(db_session, render_root, thread)
    assert result is not None
    versions = result["versions"]
    assert [v["version"] for v in versions] == [6, 5, 4, 3, 2]
    slug = composition.slug
    assert versions[0]["model"] == f"/compositions/{slug}/versions/6/files/model.glb"
    assert versions[0]["dimensions"] == f"/compositions/{slug}/versions/6/dimensions"
    assert versions[0]["picture"] == f"/compositions/{slug}/versions/6/files/screenshot.png"
    assert versions[0]["status"] == "succeeded" and versions[0]["items"] == []
    assert versions[-1]["model"] is None and versions[-1]["surfaces"] is None and versions[-1]["dimensions"] is None
    assert result["model"] == versions[0]["model"]
    assert result["approved_version"] is None
    assert all(v["approved_at"] is None for v in versions)


def test_an_approved_composition_version_is_named_on_progress(
    db_session: Session, render_root: Path
) -> None:
    thread = _thread_in(db_session, "Hall")
    composition = house_file.record_composition(db_session, "room", "Hall")
    house_file.record_composition_version(db_session, composition, 1, None, [])
    house_file.record_composition_version(db_session, composition, 2, 1, [])
    for number in (1, 2):
        folder = storage.composition_version_dir(render_root, composition.slug, number)
        folder.mkdir(parents=True)
        storage.write_status(folder, status="succeeded")
    house_file.approve_composition_version(db_session, render_root, composition.slug, 1)
    result = progress.room_progress(db_session, render_root, thread)
    assert result is not None
    assert result["approved_version"] == 1
    by_number = {v["version"]: v["approved_at"] for v in result["versions"]}
    assert by_number[1] is not None and by_number[2] is None
