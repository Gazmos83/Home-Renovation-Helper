"""restyle-variants: a batch renders one draft turntable per variant behind the guard, with fake launchers."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from app.blender import storage
from app.blender.launch import LaunchResult
from app.blender.restyle_runner import RestyleJob, run_restyle
from app.blender.runner import RENDER_SCRIPTS, launch_unguarded
from app.render.benchmark_store import Benchmark
from app.render.guard import RenderNotAuthorised, authorise
from app.render.tiers import load_tiers
from app.restyle import store
from app.restyle.presets import DEFAULT_LOOKS_PATH, DEFAULT_STYLES_PATH, load_presets
from app.restyle.request import piece_variants, room_variants
from tests.blender_fakes import arg_value, fake_pipeline_launch
from tests.test_runner import BIN, new_composition, new_version

TIERS = load_tiers()
BENCH = Benchmark(2.5, "t")
PRESETS = load_presets(DEFAULT_LOOKS_PATH, DEFAULT_STYLES_PATH)
SPEC = {"materials": {"carcass": {"material": "18 mm birch plywood", "thickness_mm": 18}}}


def _run(coro):
    return asyncio.run(coro)


def _tickets(plans, ids, *, record="piece", package_id="desk", tier="draft"):
    return [
        RestyleJob(
            authorise(package_id=package_id, version=1, kind="turntable", tier=tier, tiers=TIERS,
                      benchmark=BENCH, record=record, source="restyle", variant=variant),
            plan, variant,
        )
        for plan, variant in zip(plans, ids, strict=True)
    ]


def _go(root: Path, jobs, launch, **kwargs):
    return _run(run_restyle(jobs, root=root, blender_bin=BIN, timeout=60,
                            semaphore=asyncio.Semaphore(1), launch=launch, **kwargs))


def _digest(folder: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in folder.iterdir() if path.is_file()
    }


def _plans(*looks: str):
    return piece_variants(SPEC, [{"carcass": look} for look in looks], PRESETS)


def test_three_variants_publish_one_turntable_each_and_leave_the_version_alone(tmp_path: Path) -> None:
    folder = new_version(tmp_path, built=True)
    (folder / "spec.json").write_text(json.dumps(SPEC), encoding="utf-8")
    (folder / "still.png").write_bytes(b"own-still")
    before = _digest(folder)
    plans = _plans("walnut", "oak", "sage-green")
    ids = store.allocate_ids(folder, [p.base_id for p in plans], "draft")
    calls: list[list[str]] = []
    result = _go(tmp_path, _tickets(plans, ids), fake_pipeline_launch(calls=calls))
    assert result.outcome == "succeeded" and result.failed == []
    assert [item["id"] for item in store.list_variants(folder)] == ids
    for variant in ids:
        record = json.loads((store.variant_dir(folder, variant) / "scene.json").read_text(encoding="utf-8"))
        assert record["source"] == "restyle" and record["tier"] == "draft"
        assert record["note"] == "appearance only, not a priced material"
        assert (store.variant_dir(folder, variant) / "still.png").stat().st_size > 0
        frames = sorted(p.name for p in (store.variant_dir(folder, variant) / "frames").iterdir())
        assert frames == [f"frame_{i:03d}.png" for i in range(12)]
        assert (store.variant_dir(folder, variant) / "viewer.html").is_file()
    assert _digest(folder) == before, "the version's own files are unchanged"
    assert [arg_value(a, "--tier-resolution") for a in calls] == ["800"] * 3
    assert [arg_value(a, "--tier-frames") for a in calls] == ["12"] * 3
    assert all(Path(a[a.index("--python") + 1]).name == "render_restyle.py" for a in calls)
    assert not [p for p in store.variants_dir(folder).iterdir() if p.name.startswith(".")]


def test_one_failed_variant_is_named_and_the_others_stay(tmp_path: Path) -> None:
    folder = new_version(tmp_path, built=True)
    plans = _plans("walnut", "oak", "sage-green")
    ids = store.allocate_ids(folder, [p.base_id for p in plans], "draft")
    good = fake_pipeline_launch()
    seen = {"n": 0}

    async def flaky(argv, cwd, timeout):
        seen["n"] += 1
        if seen["n"] == 2:
            return LaunchResult(exit_code=1, stderr_tail="render: RuntimeError: boom", timed_out=False)
        return await good(argv, cwd, timeout)

    outcomes = []
    per_variant: list[tuple[str, str]] = []
    result = _go(
        tmp_path, _tickets(plans, ids), flaky, on_outcome=outcomes.append,
        on_variant=lambda job, outcome: per_variant.append((job.variant_id, outcome)),
    )
    assert [o.variant_id for o in result.failed] == [ids[1]]
    assert "boom" in result.failed[0].error
    assert {item["id"] for item in store.list_variants(folder)} == {ids[0], ids[2]}
    assert outcomes == ["failed"]
    assert per_variant == [(ids[0], "succeeded"), (ids[1], "failed"), (ids[2], "succeeded")]


def test_a_variant_missing_a_frame_fails_and_publishes_nothing(tmp_path: Path) -> None:
    folder = new_version(tmp_path, built=True)
    plans = _plans("walnut")
    ids = store.allocate_ids(folder, [p.base_id for p in plans], "draft")
    good = fake_pipeline_launch()

    async def short(argv, cwd, timeout):
        reply = await good(argv, cwd, timeout)
        out = Path(arg_value(argv, "--out"))
        (out / "frames" / "frame_011.png").unlink()
        return reply

    result = _go(tmp_path, _tickets(plans, ids), short)
    assert result.failed and "frame_011.png" in result.failed[0].error
    assert store.list_variants(folder) == []


def test_the_thirteenth_variant_replaces_the_oldest(tmp_path: Path) -> None:
    folder = new_version(tmp_path, built=True)
    for index in range(store.MAX_VARIANTS):
        target = store.variants_dir(folder) / f"old-{index:02d}"
        target.mkdir(parents=True)
        write_still_into(target)
        (target / "scene.json").write_text(json.dumps({"created_at": f"2026-01-{index + 1:02d}"}), encoding="utf-8")
    plans = _plans("walnut")
    ids = store.allocate_ids(folder, [p.base_id for p in plans], "draft")
    result = _go(tmp_path, _tickets(plans, ids), fake_pipeline_launch())
    assert result.replaced == ["old-00"]
    names = [item["id"] for item in store.list_variants(folder)]
    assert len(names) == store.MAX_VARIANTS and "old-00" not in names and ids[0] in names


def write_still_into(target: Path) -> None:
    (target / "still.png").write_bytes(b"x")


def test_a_ticket_for_another_variant_launches_nothing(tmp_path: Path) -> None:
    folder = new_version(tmp_path, built=True)
    plans = _plans("walnut")
    jobs = _tickets(plans, ["walnut-draft"])
    wrong = RestyleJob(jobs[0].ticket, jobs[0].plan, "oak-draft")
    calls: list[list[str]] = []
    result = _go(tmp_path, [wrong], fake_pipeline_launch(calls=calls))
    assert calls == [] and result.failed and "different render" in result.failed[0].error
    assert store.list_variants(folder) == []


def test_a_used_ticket_is_refused_on_a_second_run(tmp_path: Path) -> None:
    folder = new_version(tmp_path, built=True)
    jobs = _tickets(_plans("walnut"), ["walnut-draft"])
    _go(tmp_path, jobs, fake_pipeline_launch())
    calls: list[list[str]] = []
    again = _go(tmp_path, jobs, fake_pipeline_launch(calls=calls))
    assert calls == [] and again.failed and "already used" in again.failed[0].error
    assert folder.is_dir()


def test_the_restyle_script_is_a_render_script_a_build_cannot_launch() -> None:
    assert "render_restyle.py" in RENDER_SCRIPTS
    with pytest.raises(RenderNotAuthorised):
        _run(launch_unguarded(
            [str(BIN), "--python", "generators/render_restyle.py"], cwd=Path("."), timeout=1,
            semaphore=asyncio.Semaphore(1), launch=fake_pipeline_launch(),
        ))


def test_a_room_restyle_passes_the_composition_inputs_and_the_style(tmp_path: Path) -> None:
    folder = new_composition(tmp_path, [], built=True)
    plans = room_variants(["japandi"], PRESETS)
    calls: list[list[str]] = []
    jobs = _tickets(plans, ["japandi-draft"], record="room", package_id="wohnen")
    result = _go(tmp_path, jobs, fake_pipeline_launch(calls=calls))
    assert result.outcome == "succeeded"
    argv = calls[0]
    assert arg_value(argv, "--spec") == str(folder / storage.INPUT_FILE)
    assert arg_value(argv, "--pieces") == str(tmp_path) and "--blend" not in argv
    assert (store.variant_dir(folder, "japandi-draft") / "still.png").is_file()


def test_allocated_ids_are_unique_and_built_from_presets_only(tmp_path: Path) -> None:
    folder = new_version(tmp_path, built=True)
    assert store.allocate_ids(folder, ["walnut", "walnut"], "draft") == ["walnut-draft", "walnut-draft-2"]
    target = store.variants_dir(folder) / "walnut-draft"
    target.mkdir(parents=True)
    (target / "still.png").write_bytes(b"x")
    (target / "scene.json").write_text("{}", encoding="utf-8")
    assert store.allocate_ids(folder, ["walnut"], "draft") == ["walnut-draft-2"]
    # Every id fits a variant render key, `variant:<id>` (two-tier-renders).
    assert all(len(f"variant:{i}") <= 96 for i in store.allocate_ids(folder, ["x" * 90], "draft"))
