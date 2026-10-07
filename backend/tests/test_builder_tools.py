"""design-agents: the Builder's `blender_build` and `render_turntable` (tier `draft` only)."""

from __future__ import annotations

import json
import re
from dataclasses import replace

from sqlalchemy import text

from app.agent import house_file
from app.agent.tools.base import Confirmation
from app.agent.tools.blender_build import run as build_run
from app.agent.tools.create_piece import run as create_run
from app.agent.tools.render_turntable import preview as render_preview
from app.agent.tools.render_turntable import run as render_run
from app.agent.tools.room_fit import run as fit_run
from app.blender import storage
from tests.api_helpers import desk
from tests.blender_fakes import fake_pipeline_launch, png_size
from tests.conftest import wait_for_status

LIVING = [[0, 0], [6000, 0], [6000, 3500], [0, 3500]]


def folder_of(tool_state, version: int = 1):
    return storage.version_dir(tool_state.settings.render_root, "bench", version)


def made(make_ctx, tool_state, *, wait: bool = True) -> None:
    create_run({"package_id": "bench", "spec": desk()}, replace(make_ctx(), approved=True))
    if wait:
        wait_for_status(folder_of(tool_state))


def test_a_build_already_started_is_waited_for_and_reported_with_its_screenshot(make_ctx, tool_state) -> None:
    tool_state.blender_launch = fake_pipeline_launch(delay=0.4, calls=tool_state.launched)
    made(make_ctx, tool_state, wait=False)
    assert (storage.read_status(folder_of(tool_state)) or {}).get("status") in ("queued", "running")
    result = build_run({"package_id": "bench"}, make_ctx())
    assert len(tool_state.launched) == 1
    assert result == "Built bench version 1. Screenshot: /packages/bench/versions/1/files/screenshot.png"
    assert (folder_of(tool_state) / "screenshot.png").is_file()


def unbuilt(tool_state) -> None:
    """A version folder holding only its input, as one left by a failed start is."""
    folder = folder_of(tool_state)
    folder.mkdir(parents=True)
    (folder / "input.json").write_text(json.dumps(desk()), encoding="utf-8")


def test_an_unbuilt_version_is_built_and_waited_for(make_ctx, tool_state) -> None:
    unbuilt(tool_state)
    tool_state.launched.clear()

    result = build_run({"package_id": "bench"}, make_ctx())
    assert result.startswith("Built bench version 1.")
    assert len(tool_state.launched) == 1


def test_an_already_built_version_is_reported_without_rebuilding(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    launched = len(tool_state.launched)
    result = build_run({"package_id": "bench"}, make_ctx())
    assert "already built; nothing was rebuilt" in result
    assert len(tool_state.launched) == launched


def test_a_failed_build_reports_why(make_ctx, tool_state) -> None:
    from tests.blender_fakes import fake_failure_launch

    tool_state.blender_launch = fake_failure_launch
    made(make_ctx, tool_state, wait=False)
    wait_for_status(folder_of(tool_state), "failed")
    result = build_run({"package_id": "bench"}, make_ctx())
    assert "failed" in result and "boom" in result


def render(make_ctx, **fields):
    args = {"package_id": "bench", "tier": "draft", "kind": "turntable", **fields}
    shown = render_preview(args, make_ctx())
    return shown, render_run(args, make_ctx())


def test_a_draft_turntable_is_enqueued_with_its_estimate_and_viewer(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    shown, result = render(make_ctx)
    assert shown is None
    assert result.startswith("Started a draft turntable of bench version 1: about")
    assert "/packages/bench/versions/1/files/viewer.html" in result
    state = wait_for_status(folder_of(tool_state), "succeeded")
    job = wait_job(folder_of(tool_state), "turntable")
    assert job["tier"] == "draft"
    assert png_size(folder_of(tool_state) / "frames" / "frame_000.png") == (600, 600)
    assert state["status"] == "succeeded"


def wait_job(folder, key: str, seconds: float = 10.0) -> dict:
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        job = (storage.read_status(folder) or {}).get("renders", {}).get(key) or {}
        if job.get("status") == "succeeded":
            return job
        time.sleep(0.05)
    raise AssertionError(f"render {key} never succeeded")


def test_a_final_pauses_with_the_estimate_and_runs_only_on_approval(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    args = {"package_id": "bench", "tier": "final", "kind": "turntable"}
    shown = render_preview(args, make_ctx())
    assert isinstance(shown, Confirmation)
    assert shown.subject == "final_render"
    assert shown.proposal["tier"] == "final"
    assert "A final render needs your approval" in shown.summary
    assert not any("render_turntable" in " ".join(call) for call in tool_state.launched)

    declined = render_run(args, make_ctx())
    assert "approval" in declined
    renders_before = [c for c in tool_state.launched if any("render_turntable.py" in part for part in c)]
    assert renders_before == []

    started = render_run(args, replace(make_ctx(), approved=True))
    assert started.startswith("Started a final turntable")
    wait_job(folder_of(tool_state), "turntable")


def test_raw_frames_are_refused_naming_the_field(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    launched = len(tool_state.launched)
    shown, result = render(make_ctx, frames=100)
    assert isinstance(shown, str)
    assert "frames cannot be set on a render" in result
    assert len(tool_state.launched) == launched


def test_no_tier_is_refused(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    result = render_run({"package_id": "bench"}, make_ctx())
    assert "a tier is required" in result


def test_no_benchmark_is_refused(make_ctx, tool_state) -> None:
    made(make_ctx, tool_state)
    from sqlalchemy.orm import Session

    with Session(tool_state.engine) as session:
        session.execute(text("DELETE FROM operator_settings WHERE key LIKE 'render:%'"))
        session.commit()
    _, result = render(make_ctx)
    assert "no benchmark has been run" in result


def test_an_unbuilt_version_cannot_be_rendered(make_ctx, tool_state) -> None:
    unbuilt(tool_state)
    _, result = render(make_ctx)
    assert "is not built yet" in result


def test_a_room_render_carries_the_room_fit_document(make_ctx, tool_deps, tool_state) -> None:
    made(make_ctx, tool_state)
    with tool_deps.session() as session:
        house_file.upsert_room(session, "Living room", LIVING, 2600)
        session.commit()
    fitted = fit_run(
        {"room_name": "Living room", "package_id": "bench", "wall": 0, "offset_mm": 500}, make_ctx()
    )
    document = json.loads(re.search(r"Room document[^:]*: (\{.*\})$", fitted, re.MULTILINE).group(1))

    shown, result = render(make_ctx, kind="still", room=document)
    assert shown is None
    assert "/packages/bench/versions/1/files/room/still.png" in result
    job = wait_job(folder_of(tool_state), "room-still")
    assert job["tier"] == "draft"
    scene = json.loads((folder_of(tool_state) / "room" / "scene.json").read_text(encoding="utf-8"))
    assert scene


# --- apartment shells (tier `draft` only) -------------------------------------------------

def seed_apartment(tool_deps) -> None:
    from tests.test_record_plan import PLAN

    with tool_deps.session() as session:
        house_file.upsert_apartment(
            session, "Flat", PLAN["ceiling_height_mm"], PLAN["wall_thickness_mm"],
            [{"name": r["name"], "corners_mm": r["corners_mm"], "openings": r.get("openings", [])}
             for r in PLAN["rooms"]],
        )
        session.commit()


def build_shell_run(make_ctx, name: str = "Flat") -> str:
    from plugins.blender_build.tool import run_shell

    return run_shell({"apartment_name": name}, make_ctx())


def test_a_shell_is_built_waited_for_and_reported_with_its_screenshot(make_ctx, tool_deps, tool_state) -> None:
    seed_apartment(tool_deps)
    result = build_shell_run(make_ctx)
    assert result == "Built Flat shell version 1. Screenshot: /apartments/flat/shell/versions/1/files/screenshot.png"
    folder = storage.shell_version_dir(tool_state.settings.render_root, "flat", 1)
    assert (storage.read_status(folder) or {}).get("status") == "succeeded"
    assert any("build_shell.py" in " ".join(argv) for argv in tool_state.launched)


def test_an_unchanged_shell_is_reported_not_rebuilt_and_a_changed_one_gets_a_new_version(
    make_ctx, tool_deps, tool_state
) -> None:
    seed_apartment(tool_deps)
    build_shell_run(make_ctx)
    launched = len(tool_state.launched)
    again = build_shell_run(make_ctx)
    assert "already built from these rooms; nothing was rebuilt" in again
    assert len(tool_state.launched) == launched

    with tool_deps.session() as session:
        apartment = house_file.apartment_by_name(session, "Flat")
        house_file.upsert_apartment(
            session, "Flat", 2600, 120,
            [{"name": "Bedroom", "corners_mm": [[5200, 0], [8400, 0], [8400, 3800], [5200, 3800]]}],
        )
        assert apartment is not None
        session.commit()
    assert build_shell_run(make_ctx).startswith("Built Flat shell version 2.")


def test_an_unknown_apartment_lists_the_known_ones(make_ctx, tool_deps) -> None:
    seed_apartment(tool_deps)
    result = build_shell_run(make_ctx, "Villa")
    assert "no apartment 'Villa'" in result and "Flat" in result


def test_a_draft_shell_turntable_is_enqueued_with_its_estimate_and_viewer(make_ctx, tool_deps, tool_state) -> None:
    seed_apartment(tool_deps)
    build_shell_run(make_ctx)
    args = {"shell": "Flat", "tier": "draft", "kind": "turntable"}
    assert render_preview(args, make_ctx()) is None
    result = render_run(args, make_ctx())
    assert result.startswith("Started a draft turntable of the Flat shell version 1: about")
    assert "/apartments/flat/shell/versions/1/files/viewer.html" in result
    folder = storage.shell_version_dir(tool_state.settings.render_root, "flat", 1)
    job = wait_job(folder, "turntable")
    assert job["tier"] == "draft"
    assert png_size(folder / "frames" / "frame_000.png") == (600, 600)


def test_a_shell_render_needs_a_tier_refuses_raw_frames_and_pauses_for_final(make_ctx, tool_deps, tool_state) -> None:
    seed_apartment(tool_deps)
    build_shell_run(make_ctx)
    launched = len(tool_state.launched)
    assert "a tier is required" in render_run({"shell": "Flat"}, make_ctx())
    assert "frames cannot be set on a render" in render_run({"shell": "Flat", "tier": "draft", "frames": 100}, make_ctx())
    pause = render_preview({"shell": "Flat", "tier": "final"}, make_ctx())
    assert isinstance(pause, Confirmation) and pause.subject == "final_render"
    assert len(tool_state.launched) == launched


def test_a_render_names_a_piece_or_a_shell_not_both_nor_neither(make_ctx, tool_deps) -> None:
    seed_apartment(tool_deps)
    for args in ({"tier": "draft"}, {"tier": "draft", "package_id": "bench", "shell": "Flat"}):
        assert "name exactly one target" in render_run(args, make_ctx())


def test_an_unbuilt_shell_cannot_be_rendered(make_ctx, tool_deps) -> None:
    seed_apartment(tool_deps)
    assert "no built shell yet" in render_run({"shell": "Flat", "tier": "draft"}, make_ctx())


# --- a composed room (room-composition) ---------------------------------------------------


def composed(make_ctx, tool_deps, tool_state, *, wait: bool = True) -> None:
    from plugins.compose_room.tool import run as compose_run

    with tool_deps.session() as session:
        house_file.upsert_room(session, "Wohnen", [[0, 0], [5000, 0], [5000, 4000], [0, 4000]], 2600)
        session.commit()
    made(make_ctx, tool_state)
    with tool_deps.session() as session:
        house_file.approve_version(session, "bench", 1)
        session.commit()
    items = [{"id": "bench", "type": "piece", "package_id": "bench", "version": 1,
              "placement": {"wall": 1, "offset_mm": 500}}]
    compose_run({"room": "Wohnen", "items": items}, replace(make_ctx(), approved=True))
    if wait:
        wait_for_status(storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1))


def test_a_draft_turntable_of_a_composition_starts_with_its_estimate(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    args = {"composition": "Wohnen", "tier": "draft"}
    assert render_preview(args, make_ctx()) is None
    result = render_run(args, make_ctx())
    assert result.startswith("Started a draft turntable of Wohnen version 1: about")
    assert "/compositions/wohnen/versions/1/files/viewer.html" in result and "no longer approved" not in result
    folder = storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1)
    job = wait_job(folder, "turntable")
    assert job["tier"] == "draft"
    assert png_size(folder / "frames" / "frame_000.png") == (600, 600)


def test_a_composition_final_pauses_and_raw_values_are_refused(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    launched = len(tool_state.launched)
    pause = render_preview({"composition": "Wohnen", "tier": "final", "kind": "still"}, make_ctx())
    assert isinstance(pause, Confirmation) and pause.subject == "final_render"
    assert "resolution" in render_run({"composition": "Wohnen", "tier": "draft", "resolution": 4000}, make_ctx())
    assert len(tool_state.launched) == launched


def test_a_piece_and_a_composition_together_are_refused(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    result = render_run({"composition": "Wohnen", "package_id": "bench", "tier": "draft"}, make_ctx())
    assert "name exactly one target" in result


def test_an_unbuilt_composition_cannot_be_rendered(make_ctx, tool_deps, tool_state) -> None:
    tool_state.blender_launch = fake_pipeline_launch(delay=1.0, calls=tool_state.launched)
    composed(make_ctx, tool_deps, tool_state, wait=False)
    result = render_run({"composition": "Wohnen", "tier": "draft"}, make_ctx())
    assert "wohnen version 1 is not built yet" in result


def test_the_reply_says_when_a_placed_version_is_no_longer_approved(make_ctx, tool_deps, tool_state) -> None:
    composed(make_ctx, tool_deps, tool_state)
    with tool_deps.session() as session:
        house_file.unapprove_version(session, "bench", 1)
        session.commit()
    result = render_run({"composition": "Wohnen", "tier": "draft", "kind": "still"}, make_ctx())
    assert result.endswith("Note: bench v1 is no longer approved.")
