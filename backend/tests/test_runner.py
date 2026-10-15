"""The runner's lifecycle, driven by fake launchers (no Blender)."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from app.blender import storage
from app.blender.launch import LaunchResult
from app.blender.runner import (
    mark_build_queued,
    mark_render_queued,
    run_build,
    run_render,
    shows_dimensions,
)
from app.render.benchmark_store import Benchmark, RemoteBenchmark
from app.render.guard import RenderNotAuthorised, authorise
from app.render.tiers import load_tiers
from tests.blender_fakes import (
    BUILD_FILES,
    arg_value,
    fake_failure_launch,
    fake_hanging_launch,
    fake_missing_binary_launch,
    fake_success_launch,
    write_build_files,
    write_frames,
    write_still,
)

BIN = Path("/fake/blender")
TIERS = load_tiers()
BENCH = Benchmark(2.5, "t")


def run(coro):
    return asyncio.run(coro)


def new_version(root: Path, package_id: str = "desk", version: int = 1, *, built: bool = False) -> Path:
    folder = storage.version_dir(root, package_id, version)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text("{}", encoding="utf-8")
    mark_build_queued(folder)
    if built:
        seed = folder / "_seed"
        write_build_files(seed)
        for name in BUILD_FILES:
            (seed / name).replace(folder / name)
        shutil.rmtree(seed)
        storage.write_status(folder, status="succeeded")
    return folder


def build(root: Path, launch, *, package_id: str = "desk", version: int = 1, semaphore=None, timeout: float = 60):
    return run_build(
        root=root, blender_bin=BIN, timeout=timeout, package_id=package_id, version=version,
        semaphore=semaphore or asyncio.Semaphore(1), launch=launch,
    )


def ticket(kind="turntable", tier="draft", *, room=False, version=1, package_id="desk"):
    return authorise(
        package_id=package_id, version=version, kind=kind, tier=tier, tiers=TIERS,
        benchmark=BENCH, room=room, approval="yes",
    )


def render(root: Path, t, launch, *, semaphore=None, timeout: float = 60, **kwargs):
    return run_render(
        t, root=root, blender_bin=BIN, timeout=timeout,
        semaphore=semaphore or asyncio.Semaphore(1), launch=launch, **kwargs,
    )


def render_writer(out: Path, argv: list[str]) -> None:
    size = int(arg_value(argv, "--tier-resolution"))
    if any(part.endswith("render_still.py") for part in argv):
        write_still(out, size=size)
    else:
        write_frames(out, frames=int(arg_value(argv, "--tier-frames")), size=size)


def room_writer(kind: str):
    def write(out: Path, argv: list[str]) -> None:
        scene = json.loads(Path(arg_value(argv, "--scene")).read_text(encoding="utf-8"))
        assert scene["marker"] == "room-doc"
        assert (Path(arg_value(argv, "--package")) / "model.blend").is_file()
        size = int(arg_value(argv, "--tier-resolution"))
        if kind == "still":
            write_still(out, size=size)
        else:
            write_frames(out, frames=int(arg_value(argv, "--tier-frames")), size=size)

    return write


# --- builds ----------------------------------------------------------------------------------


def test_a_successful_build_publishes_the_six_files_and_records_it(render_root: Path) -> None:
    folder = new_version(render_root)
    run(build(render_root, fake_success_launch()))
    status = storage.read_status(folder)
    assert status["status"] == "succeeded" and status["error"] is None
    assert status["started_at"] and status["finished_at"]
    assert {p.name for p in folder.iterdir() if not p.name.startswith(".")} == (
        set(storage.BUILD_FILES) | {storage.INPUT_FILE, storage.STATUS_FILE}
    )
    assert [p for p in folder.iterdir() if p.name.startswith(".")] == []


def test_a_non_zero_exit_fails_with_a_safe_error_and_publishes_nothing(render_root: Path) -> None:
    folder = new_version(render_root)
    run(build(render_root, fake_failure_launch))
    status = storage.read_status(folder)
    assert status["status"] == "failed" and "boom" in status["error"]
    assert not any((folder / name).exists() for name in storage.BUILD_FILES)
    assert [p for p in folder.iterdir() if p.name.startswith(".")] == []


def test_a_timeout_fails_the_build(render_root: Path) -> None:
    folder = new_version(render_root)
    run(build(render_root, fake_hanging_launch))
    assert "timed out" in storage.read_status(folder)["error"]


def test_a_missing_binary_fails_the_build(render_root: Path) -> None:
    folder = new_version(render_root)
    run(build(render_root, fake_missing_binary_launch))
    assert "could not be started" in storage.read_status(folder)["error"]


def test_the_error_strips_the_render_root_and_is_bounded(render_root: Path) -> None:
    folder = new_version(render_root)

    async def verbose(argv, cwd, timeout):
        return LaunchResult(1, f"build: failed in {render_root}/desk/v1 " + "x" * 2000, False)

    run(build(render_root, verbose))
    error = storage.read_status(folder)["error"]
    assert str(render_root) not in error and len(error) <= 500


def test_an_incomplete_build_publishes_nothing(render_root: Path) -> None:
    folder = new_version(render_root)

    def missing_screenshot(out: Path, argv: list[str]) -> None:
        write_build_files(out)
        (out / "screenshot.png").unlink()

    run(build(render_root, fake_success_launch(missing_screenshot)))
    status = storage.read_status(folder)
    assert status["status"] == "failed" and "publish:" in status["error"]
    assert not any((folder / name).exists() for name in storage.BUILD_FILES)


def test_two_builds_never_overlap_under_one_semaphore(render_root: Path) -> None:
    new_version(render_root, "a-desk")
    new_version(render_root, "b-desk")
    tracker: list[int] = []
    launch = fake_success_launch(delay=0.05, tracker=tracker)

    async def both():
        semaphore = asyncio.Semaphore(1)
        await asyncio.gather(
            build(render_root, launch, package_id="a-desk", semaphore=semaphore),
            build(render_root, launch, package_id="b-desk", semaphore=semaphore),
        )

    run(both())
    for pid in ("a-desk", "b-desk"):
        assert storage.read_status(storage.version_dir(render_root, pid, 1))["status"] == "succeeded"


# --- renders ---------------------------------------------------------------------------------


def test_a_draft_still_publishes_and_records_its_tier(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    calls: list[list[str]] = []
    run(render(render_root, ticket("still"), fake_success_launch(render_writer, calls=calls)))
    assert (folder / "still.png").is_file()
    entry = storage.read_status(folder)["renders"]["still"]
    assert entry["status"] == "succeeded" and entry["tier"] == "draft"
    assert entry["actual_seconds"] is not None and entry["estimate_seconds"] > 0
    record = json.loads((folder / "scene.json").read_text(encoding="utf-8"))["still"]
    assert record["tier"] == "draft"
    argv = calls[0]
    assert (arg_value(argv, "--tier-frames"), arg_value(argv, "--tier-resolution"),
            arg_value(argv, "--tier-engine")) == ("12", "800", "BLENDER_EEVEE")


def test_a_draft_turntable_publishes_exactly_twelve_frames_and_a_viewer(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    run(render(render_root, ticket("turntable"), fake_success_launch(render_writer)))
    assert sorted(p.name for p in (folder / "frames").iterdir()) == [f"frame_{i:03d}.png" for i in range(12)]
    assert (folder / "viewer.html").is_file()
    assert storage.read_status(folder)["renders"]["turntable"]["status"] == "succeeded"
    assert [p for p in folder.iterdir() if p.name.startswith(".")] == []


def test_a_new_turntable_replaces_the_old_one_whole(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    run(render(render_root, ticket("turntable", "draft"), fake_success_launch(render_writer)))
    run(render(render_root, ticket("turntable", "final"), fake_success_launch(render_writer)))
    assert len(list((folder / "frames").iterdir())) == 36


def test_still_and_turntable_records_are_both_kept(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    run(render(render_root, ticket("still"), fake_success_launch(render_writer)))
    run(render(render_root, ticket("turntable"), fake_success_launch(render_writer)))
    assert set(json.loads((folder / "scene.json").read_text(encoding="utf-8"))) == {"still", "turntable"}


def test_a_missing_frame_fails_naming_it_and_publishes_nothing(render_root: Path) -> None:
    folder = new_version(render_root, built=True)

    def hole(out: Path, argv: list[str]) -> None:
        write_frames(out, frames=12, size=800, skip_empty=7)

    run(render(render_root, ticket("turntable"), fake_success_launch(hole)))
    entry = storage.read_status(folder)["renders"]["turntable"]
    assert entry["status"] == "failed" and "frame_007.png" in entry["error"]
    assert not (folder / "frames").exists() and not (folder / "viewer.html").exists()
    assert [p for p in folder.iterdir() if p.name.startswith(".")] == []


def test_a_render_failure_publishes_nothing(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    run(render(render_root, ticket("still"), fake_failure_launch))
    assert storage.read_status(folder)["renders"]["still"]["status"] == "failed"
    assert not (folder / "still.png").exists()


def test_a_room_render_publishes_under_room(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    run(render(render_root, ticket("still", room=True), fake_success_launch(room_writer("still")),
               scene_document={"marker": "room-doc"}))
    assert (folder / "room" / "still.png").is_file()
    assert not (folder / "still.png").exists()
    assert storage.read_status(folder)["renders"]["room-still"]["status"] == "succeeded"
    assert [p for p in folder.iterdir() if p.name.startswith(".")] == []


def test_a_used_ticket_is_refused_and_launches_nothing_more(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    calls: list[list[str]] = []
    t = ticket("still")
    launch = fake_success_launch(render_writer, calls=calls)
    run(render(render_root, t, launch))
    with pytest.raises(RenderNotAuthorised):
        run(render(render_root, t, launch))
    assert len(calls) == 1
    assert storage.read_status(folder)["renders"]["still"]["status"] == "failed"


def test_the_runner_runs_exactly_the_request_the_ticket_names(render_root: Path) -> None:
    """The version, kind and tier come from the ticket, never from the caller."""
    new_version(render_root, built=True)
    new_version(render_root, version=2, built=True)
    calls: list[list[str]] = []
    run(render(render_root, ticket("still", version=2),
               fake_success_launch(render_writer, calls=calls)))
    assert "/v2/" in calls[0][calls[0].index("--blend") + 1]
    assert (storage.version_dir(render_root, "desk", 2) / "still.png").is_file()
    assert not (storage.version_dir(render_root, "desk", 1) / "still.png").exists()


def test_only_a_piece_turntable_is_asked_for_its_dimension_lines(render_root: Path) -> None:
    new_version(render_root, built=True)
    calls: list[list[str]] = []
    run(render(render_root, ticket("turntable"), fake_success_launch(render_writer, calls=calls)))
    run(render(render_root, ticket("still"), fake_success_launch(render_writer, calls=calls)))
    turntable, still = calls
    assert "--dimensions" in turntable
    assert "--dimensions" not in still


def test_dimension_lines_are_never_asked_of_a_room_shell_composition_or_detail_render() -> None:
    def quote(**kwargs):
        return authorise(
            package_id="desk", version=1, kind=kwargs.pop("kind", "turntable"), tier="draft",
            tiers=TIERS, benchmark=BENCH, approval="yes", **kwargs,
        ).quote

    assert shows_dimensions(quote())
    assert not shows_dimensions(quote(kind="still"))
    assert not shows_dimensions(quote(room=True))
    assert not shows_dimensions(quote(record="shell"))
    assert not shows_dimensions(quote(record="room"))
    # A detail turntable runs only on the render server (two-tier-renders).
    assert not shows_dimensions(
        authorise(package_id="desk", version=1, kind="turntable", tier="final", tiers=TIERS,
                  benchmark=BENCH, approval="yes", source="detail", target="remote",
                  remote_benchmark=RemoteBenchmark(0.2, 40.0, "t")).quote
    )


def test_the_timeout_scales_with_the_tier(render_root: Path) -> None:
    new_version(render_root, built=True)
    seen: list[float] = []

    async def spy(argv, cwd, timeout):
        seen.append(timeout)
        render_writer(Path(arg_value(argv, "--out")), argv)
        return LaunchResult(0, "", False)

    run(render(render_root, ticket("still", "draft"), spy, timeout=600))
    run(render(render_root, ticket("still", "final"), spy, timeout=600))
    # A final may run 6 hours at the 600 s default (local-detail-turntable).
    assert seen == [600, 21_600]


def test_on_finished_runs_after_a_success_only(render_root: Path) -> None:
    new_version(render_root, built=True)
    done: list[tuple[str, float]] = []
    callback = lambda quote, actual: done.append((quote.tier.name, actual))
    run(render(render_root, ticket("still"), fake_failure_launch, on_finished=callback))
    assert done == []
    run(render(render_root, ticket("still"), fake_success_launch(render_writer), on_finished=callback))
    assert [name for name, _ in done] == ["draft"]


def test_a_second_render_reads_queued_until_the_first_finishes(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    first, second = ticket("still"), ticket("turntable")
    mark_render_queued(folder, first)
    mark_render_queued(folder, second)
    tracker: list[int] = []
    launch = fake_success_launch(render_writer, delay=0.15, tracker=tracker)
    seen: dict[str, str] = {}

    async def go():
        semaphore = asyncio.Semaphore(1)
        tasks = [
            asyncio.create_task(render(render_root, first, launch, semaphore=semaphore)),
            asyncio.create_task(render(render_root, second, launch, semaphore=semaphore)),
        ]
        await asyncio.sleep(0.07)
        renders = storage.read_status(folder)["renders"]
        seen["still"], seen["turntable"] = renders["still"]["status"], renders["turntable"]["status"]
        await asyncio.gather(*tasks)

    run(go())
    assert seen == {"still": "running", "turntable": "queued"}
    renders = storage.read_status(folder)["renders"]
    assert renders["still"]["status"] == renders["turntable"]["status"] == "succeeded"


def test_a_render_launch_without_a_ticket_is_refused(render_root: Path) -> None:
    from app.blender.runner import launch_guarded

    calls: list[list[str]] = []

    async def go(candidate):
        return await launch_guarded(
            candidate, expected=("desk", 1, "still", False), argv=["blender"], cwd=render_root,
            timeout=1, semaphore=asyncio.Semaphore(1), launch=fake_success_launch(calls=calls),
        )

    for not_a_ticket in (None, "yes", object(), {"tier": "draft"}):
        with pytest.raises(RenderNotAuthorised, match="needs a ticket"):
            run(go(not_a_ticket))
    assert calls == []


# --- detail renders (photoreal-detail) -----------------------------------------------------------


def detail_ticket(kind="still", *, version=1, package_id="desk"):
    return authorise(
        package_id=package_id, version=version, kind=kind, tier="final", tiers=TIERS,
        benchmark=BENCH, approval="yes", source="detail",
    )


def with_detail_copy(folder: Path) -> Path:
    copy = storage.detail_blend_path(folder)
    copy.parent.mkdir(exist_ok=True)
    copy.write_bytes(b"BLENDER-detail")
    return copy


def test_a_final_detail_still_renders_the_copy_and_publishes_under_detail(render_root: Path) -> None:
    # On the laptop a detail render is a still (two-tier-renders).
    folder = new_version(render_root, built=True)
    copy = with_detail_copy(folder)
    (folder / "still.png").write_bytes(b"own")
    calls: list[list[str]] = []
    run(render(render_root, detail_ticket(), fake_success_launch(render_writer, calls=calls)))
    argv = calls[0]
    assert arg_value(argv, "--blend") == str(copy)
    assert "--dimensions" not in argv
    assert (arg_value(argv, "--tier-resolution"), arg_value(argv, "--tier-engine")) == ("1500", "CYCLES")
    detail = storage.detail_dir(folder)
    assert (detail / "still.png").is_file()
    assert (folder / "still.png").read_bytes() == b"own"
    record = json.loads((detail / "scene.json").read_text(encoding="utf-8"))["still"]
    assert record["source"] == "detail" and record["tier"] == "final"
    entry = storage.read_status(folder)["renders"]["detail-still"]
    assert entry["status"] == "succeeded" and entry["tier"] == "final"
    assert "still" not in storage.read_status(folder)["renders"]
    assert [p for p in folder.iterdir() if p.name.startswith(".")] == []


def test_a_final_detail_still_publishes_under_detail(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    with_detail_copy(folder)
    run(render(render_root, detail_ticket("still"), fake_success_launch(render_writer)))
    assert (storage.detail_dir(folder) / "still.png").is_file()
    assert not (folder / "still.png").exists()


def test_a_detail_render_without_the_copy_fails_and_launches_nothing(render_root: Path) -> None:
    folder = new_version(render_root, built=True)
    calls: list[list[str]] = []
    run(render(render_root, detail_ticket(), fake_success_launch(render_writer, calls=calls)))
    entry = storage.read_status(folder)["renders"]["detail-still"]
    assert entry["status"] == "failed" and "detail.blend" in entry["error"]
    assert calls == []


def test_the_live_file_is_saved_before_a_detail_render_and_a_failure_does_not_stop_it(
    render_root: Path,
) -> None:
    folder = new_version(render_root, built=True)
    with_detail_copy(folder)
    order: list[str] = []

    async def before() -> None:
        order.append("saved")
        raise RuntimeError("Blender is closed")

    def writer(out: Path, argv: list[str]) -> None:
        order.append("rendered")
        render_writer(out, argv)

    run(render(render_root, detail_ticket("still"), fake_success_launch(writer), before=before))
    assert order == ["saved", "rendered"]
    assert storage.read_status(folder)["renders"]["detail-still"]["status"] == "succeeded"


def test_a_model_ticket_cannot_launch_a_detail_render(render_root: Path) -> None:
    """The runner passes the ticket's own source; a ticket for another source is refused."""
    import asyncio as aio

    from app.blender.runner import launch_guarded

    t = ticket("turntable", "draft")
    calls: list[list[str]] = []
    launch = fake_success_launch(render_writer, calls=calls)
    with pytest.raises(RenderNotAuthorised):
        run(launch_guarded(
            t, expected=("desk", 1, "turntable", False, "piece", "detail"), argv=["x"],
            cwd=render_root, timeout=5, semaphore=aio.Semaphore(1), launch=launch,
        ))
    assert calls == []


# --- room compositions (room-composition) ------------------------------------------------


def new_composition(root: Path, items: list[dict], *, built: bool = False) -> Path:
    folder = storage.composition_version_dir(root, "wohnen", 1)
    folder.mkdir(parents=True)
    (folder / storage.INPUT_FILE).write_text(
        json.dumps({"kind": "room_composition", "scope": {"room": "Wohnen"}, "items": items}), encoding="utf-8"
    )
    mark_build_queued(folder)
    if built:
        from tests.blender_fakes import write_composition_files

        seed = folder / "_seed"
        write_composition_files(seed)
        for name in storage.COMPOSITION_FILES:
            (seed / name).replace(folder / name)
        shutil.rmtree(seed)
        storage.write_status(folder, status="succeeded")
    return folder


PIECE = {"id": "desk", "type": "piece", "package_id": "desk", "version": 1}


def build_room(root: Path, launch, models_root: Path):
    return run_build(
        root=root, blender_bin=BIN, timeout=60, package_id="wohnen", version=1,
        semaphore=asyncio.Semaphore(1), launch=launch, record="room", models_root=models_root,
    )


def test_a_composition_build_runs_its_generator_and_publishes_three_files(render_root: Path, tmp_path: Path) -> None:
    from tests.blender_fakes import fake_pipeline_launch

    new_version(render_root, built=True)
    folder = new_composition(render_root, [PIECE])
    calls: list[list[str]] = []
    run(build_room(render_root, fake_pipeline_launch(calls=calls), tmp_path / "models"))
    assert storage.read_status(folder)["status"] == "succeeded"
    assert {p.name for p in folder.iterdir()} == {*storage.COMPOSITION_FILES, storage.INPUT_FILE, storage.STATUS_FILE}
    argv = calls[0]
    assert Path(argv[argv.index("--python") + 1]).name == "build_composition.py"
    assert arg_value(argv, "--pieces") == str(render_root)
    assert arg_value(argv, "--models") == str(tmp_path / "models")
    assert "--tier-frames" not in argv, "a composition build never renders"


def test_a_placed_piece_that_is_not_built_fails_the_build_naming_it(render_root: Path, tmp_path: Path) -> None:
    new_version(render_root)  # queued, never built
    folder = new_composition(render_root, [PIECE])
    calls: list[list[str]] = []
    run(build_room(render_root, fake_success_launch(calls=calls), tmp_path / "models"))
    status = storage.read_status(folder)
    assert status["status"] == "failed"
    assert status["error"] == "desk version 1 is not built; a placed piece must be built before the room is"
    assert calls == [], "nothing is launched, and the piece is never built implicitly"
    assert not (folder / "model.blend").exists()


def test_a_composition_turntable_renders_through_its_own_script_into_the_version(render_root: Path, tmp_path: Path) -> None:
    from tests.blender_fakes import fake_pipeline_launch

    folder = new_composition(render_root, [], built=True)
    t = authorise(package_id="wohnen", version=1, kind="turntable", tier="draft", tiers=TIERS,
                  benchmark=BENCH, record="room")
    calls: list[list[str]] = []
    run(render(render_root, t, fake_pipeline_launch(calls=calls), models_root=tmp_path / "models"))
    assert storage.read_status(folder)["renders"]["turntable"]["status"] == "succeeded"
    assert len(list((folder / "frames").iterdir())) == 12 and (folder / "viewer.html").is_file()
    argv = calls[0]
    assert Path(argv[argv.index("--python") + 1]).name == "render_composition.py"
    assert arg_value(argv, "--kind") == "turntable"
    assert (arg_value(argv, "--tier-frames"), arg_value(argv, "--tier-resolution")) == ("12", "800")


def test_the_composition_renderer_is_a_render_script_a_build_cannot_launch() -> None:
    from app.blender.runner import RENDER_SCRIPTS

    assert "render_composition.py" in RENDER_SCRIPTS
    assert "build_composition.py" not in RENDER_SCRIPTS


def test_a_build_passes_the_versions_frozen_hardware_inputs_and_an_old_one_does_not(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    new = new_version(tmp_path, "cabinet")
    (new / storage.HARDWARE_INPUTS_FILE).write_text('{"data_sheets": {}, "rules": {}}', encoding="utf-8")
    old = new_version(tmp_path, "shelf")
    for package_id in ("cabinet", "shelf"):
        run(build(tmp_path, fake_success_launch(calls=calls), package_id=package_id))
    with_inputs, without = calls
    assert arg_value(with_inputs, "--hardware-data") == str(new / storage.HARDWARE_INPUTS_FILE)
    assert "--hardware-data" not in without and old.is_dir()
