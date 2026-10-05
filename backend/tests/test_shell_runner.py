"""apartment-shell: shell builds and renders through the runner, with fake launchers."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.blender import storage
from app.blender.runner import launch_guarded, mark_build_queued, run_build, run_render
from app.render.benchmark_store import Benchmark
from app.render.guard import RenderNotAuthorised, authorise
from app.render.tiers import load_tiers
from tests.blender_fakes import arg_value, fake_pipeline_launch

BIN = Path("/fake/blender")
TIERS = load_tiers()
BENCH = Benchmark(2.5, "t")


def run(coro):
    return asyncio.run(coro)


def new_shell(root: Path, slug: str = "flat", version: int = 1) -> Path:
    folder = storage.shell_version_dir(root, slug, version)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text("{}", encoding="utf-8")
    mark_build_queued(folder)
    return folder


def build_shell(root: Path, launch, slug: str = "flat", version: int = 1):
    return run_build(
        root=root, blender_bin=BIN, timeout=60, package_id=slug, version=version,
        semaphore=asyncio.Semaphore(1), launch=launch, record="shell",
    )


def shell_ticket(kind: str = "turntable", tier: str = "draft", slug: str = "flat"):
    return authorise(
        package_id=slug, version=1, kind=kind, tier=tier, tiers=TIERS, benchmark=BENCH,
        approval="yes", record="shell",
    )


def test_a_shell_build_publishes_the_four_shell_files(render_root: Path) -> None:
    folder = new_shell(render_root)
    calls: list[list[str]] = []
    run(build_shell(render_root, fake_pipeline_launch(calls=calls)))
    status = storage.read_status(folder)
    assert status["status"] == "succeeded" and status["error"] is None
    assert {p.name for p in folder.iterdir() if not p.name.startswith(".")} == (
        set(storage.SHELL_FILES) | {storage.INPUT_FILE, storage.STATUS_FILE}
    )
    assert any(part.endswith("build_shell.py") for part in calls[0])
    assert arg_value(calls[0], "--spec").endswith("/shells/flat/v1/input.json")


def test_a_draft_shell_turntable_publishes_twelve_frames_in_the_shell_folder(render_root: Path) -> None:
    folder = new_shell(render_root)
    run(build_shell(render_root, fake_pipeline_launch()))
    calls: list[list[str]] = []
    t = shell_ticket()
    assert t.quote.record == "shell" and t.quote.tier.name == "draft"
    run(run_render(
        t, root=render_root, blender_bin=BIN, timeout=60, semaphore=asyncio.Semaphore(1),
        launch=fake_pipeline_launch(calls=calls),
    ))
    assert len(list((folder / "frames").glob("frame_*.png"))) == 12
    assert (folder / "viewer.html").is_file()
    entry = storage.read_status(folder)["renders"]["turntable"]
    assert entry["status"] == "succeeded" and entry["tier"] == "draft"
    assert arg_value(calls[0], "--blend").endswith("/shells/flat/v1/model.blend")
    assert (arg_value(calls[0], "--tier-frames"), arg_value(calls[0], "--tier-resolution")) == ("12", "600")


def test_a_shell_ticket_never_matches_a_piece_of_the_same_id(render_root: Path) -> None:
    t = shell_ticket(slug="desk")
    assert t.matches("desk", 1, "turntable", False, "shell")
    assert not t.matches("desk", 1, "turntable", False)
    assert not t.matches("desk", 1, "turntable", False, "piece")

    piece = authorise(
        package_id="desk", version=1, kind="turntable", tier="draft", tiers=TIERS,
        benchmark=BENCH, approval="yes",
    )
    assert not piece.matches("desk", 1, "turntable", False, "shell")


def test_a_shell_ticket_cannot_launch_a_piece_render(render_root: Path) -> None:
    t = shell_ticket(slug="desk")
    with pytest.raises(RenderNotAuthorised, match="different render"):
        run(launch_guarded(
            t, expected=("desk", 1, "turntable", False, "piece"), argv=["blender"], cwd=render_root,
            timeout=1, semaphore=asyncio.Semaphore(1), launch=fake_pipeline_launch(),
        ))
    assert not t.consumed


def test_a_shell_build_that_fails_is_recorded_with_a_safe_error(render_root: Path) -> None:
    from tests.blender_fakes import fake_failure_launch

    folder = new_shell(render_root)
    run(build_shell(render_root, fake_failure_launch))
    status = storage.read_status(folder)
    assert status["status"] == "failed" and "boom" in status["error"]
    assert [p.name for p in folder.iterdir() if p.name.startswith(".build-out")] == []


def test_the_restart_sweep_fails_a_queued_shell_build(render_root: Path) -> None:
    folder = new_shell(render_root)
    assert storage.sweep_orphaned_statuses(render_root) == 1
    assert storage.read_status(folder)["status"] == "failed"


def test_shells_are_reserved_so_no_piece_can_hide_them(render_root: Path) -> None:
    with pytest.raises(storage.InvalidPackageId):
        storage.validate_package_id("shells")
    new_shell(render_root)
    assert storage.list_packages(render_root) == []
    assert storage.list_shells(render_root) == [("flat", [1])]


@pytest.mark.parametrize(
    ("name", "slug"),
    [("Example one-bed", "example-one-bed"), ("  Flat 4B!  ", "flat-4b"), ("Wohnung Süd", "wohnung-s-d")],
)
def test_an_apartment_name_becomes_a_slug(name: str, slug: str) -> None:
    assert storage.apartment_slug(name) == slug


def test_a_name_without_letters_or_digits_has_no_slug() -> None:
    with pytest.raises(storage.InvalidPackageId):
        storage.apartment_slug("---")
