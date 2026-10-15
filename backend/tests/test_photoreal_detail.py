"""The Lighting & materials tools: confirmation, bound piece, scripts, final render (photoreal-detail)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.agent.tools.base import Confirmation
from app.agent.tools.photoreal_detail import (
    detail_screenshot,
    render_detail,
    run_detail_script,
    start_detail_pass,
)
from app.blender import storage
from app.live.detail_pass import SAVE_TEMPLATE
from app.live.socket_client import LiveRefused
from tests.blender_fakes import png_size
from tests.live_helpers import FakeBlender
from tests.test_builder_tools import folder_of, made, unbuilt, wait_job


@pytest.fixture
def live(tool_state) -> FakeBlender:
    tool_state.live_blender = FakeBlender()
    return tool_state.live_blender


@pytest.fixture
def bound(make_ctx, tool_state):
    """A built piece `bench` bound to the conversation."""
    made(make_ctx, tool_state)
    return lambda **fields: make_ctx(package_id="bench", **fields)


def started(ctx_for):
    return start_detail_pass.run({}, replace(ctx_for(), approved=True))


def test_starting_a_pass_pauses_for_the_owner_and_sends_nothing(bound, live) -> None:
    shown = start_detail_pass.preview({}, bound())
    assert isinstance(shown, Confirmation) and shown.subject == "detail_pass"
    assert "bench version 1" in shown.summary and "replaced" in shown.summary
    assert "not changed" in shown.summary
    assert live.scripts == []


def test_without_the_owners_yes_the_pass_does_not_start(bound, live, tool_state) -> None:
    result = start_detail_pass.run({}, bound())
    assert "confirmation" in result
    assert live.scripts == []
    assert not storage.detail_dir(folder_of(tool_state)).exists()


def test_a_confirmed_pass_copies_the_model_and_opens_it(bound, live, tool_state) -> None:
    before = (folder_of(tool_state) / "model.blend").read_bytes()
    result = started(bound)
    detail = storage.detail_blend_path(folder_of(tool_state))
    assert detail.read_bytes() == before
    assert (folder_of(tool_state) / "model.blend").read_bytes() == before
    assert live.open_file == str(detail)
    assert "detail pass is open on bench version 1" in result and "[[[UNTRUSTED_SOURCE" in result


def test_an_unbuilt_version_is_refused_before_the_pause(make_ctx, tool_state, live) -> None:
    unbuilt(tool_state)
    shown = start_detail_pass.preview({}, make_ctx(package_id="bench"))
    assert isinstance(shown, str) and "not built yet" in shown
    assert live.scripts == []


def test_a_thread_with_no_piece_is_refused(make_ctx, live) -> None:
    shown = start_detail_pass.preview({}, make_ctx())
    assert isinstance(shown, str) and "no piece bound" in shown


def test_the_package_comes_from_the_conversation_not_the_arguments(bound, live, tool_state) -> None:
    result = start_detail_pass.run(
        {"package_id": "other", "filepath": "/etc/passwd", "path": "../x"}, replace(bound(), approved=True)
    )
    assert "bench version 1" in result
    assert live.open_file == str(storage.detail_blend_path(folder_of(tool_state)))


def test_a_script_needs_a_started_pass(bound, live) -> None:
    result = run_detail_script.run({"code": "import bpy\n", "purpose": "x"}, bound())
    assert "no detail pass has been started" in result and live.scripts == []


def test_a_script_runs_after_the_pass_and_the_scene_comes_back_as_text(bound, live) -> None:
    started(bound)
    result = run_detail_script.run({"code": "# AGENT\nimport bpy\n", "purpose": "oak"}, bound())
    assert result.startswith("The script ran.") and "objects: 2" in result


def test_a_refused_script_is_not_sent(bound, live) -> None:
    started(bound)
    sent = len(live.scripts)
    result = run_detail_script.run({"code": "import subprocess\n", "purpose": "x"}, bound())
    assert "subprocess" in result and "Nothing was sent" in result
    assert len(live.scripts) == sent


def test_a_screenshot_is_for_the_owner_and_the_agent_gets_text_only(bound, live, tool_state) -> None:
    started(bound)
    result = detail_screenshot.run({}, bound())
    assert "/packages/bench/versions/1/files/detail/screens/0" in result
    assert "cannot see images" in result
    assert (storage.detail_dir(folder_of(tool_state)) / "screens" / "screen_000.png").is_file()


# --- the detail render -------------------------------------------------------------------------------


def final(**fields):
    """A detail render at `final`; with no kind it is a still, the laptop's detail render."""
    return {"tier": "final", **fields}


def test_a_detail_render_below_final_is_refused_naming_why(bound, live) -> None:
    started(bound)
    shown = render_detail.preview({"tier": "draft"}, bound())
    assert isinstance(shown, str) and "final only" in shown
    shown = render_detail.preview({"tier": "preview"}, bound())
    assert isinstance(shown, str) and "the tiers are draft, final" in shown


def test_a_local_detail_turntable_is_refused_without_asking(bound, live, tool_state) -> None:
    started(bound)
    shown = render_detail.preview(final(kind="turntable"), bound())
    assert isinstance(shown, str)
    assert "on the laptop a detail render is a still" in shown and "only on the render server" in shown
    result = render_detail.run(final(kind="turntable"), replace(bound(), approved=True))
    assert "only on the render server" in result
    assert not any("render_turntable.py" in " ".join(c) for c in tool_state.launched)


def test_a_missing_tier_and_raw_values_are_refused(bound, live) -> None:
    started(bound)
    assert "a tier is required" in render_detail.run({}, bound())
    assert "frames cannot be set on a render" in render_detail.run(final(frames=100), bound())
    assert "engine cannot be set on a render" in render_detail.run(final(engine="CYCLES"), bound())


def test_a_detail_render_needs_a_started_pass(bound, live, tool_state) -> None:
    result = render_detail.run(final(), bound())
    assert "no detail pass has been started" in result
    assert not any(
        part.endswith(("render_turntable.py", "render_still.py"))
        for call in tool_state.launched for part in call
    )


def test_the_final_pauses_with_the_estimate_and_does_not_run_unapproved(bound, live, tool_state) -> None:
    started(bound)
    shown = render_detail.preview(final(), bound())
    assert isinstance(shown, Confirmation) and shown.subject == "detail_render"
    assert shown.proposal["tier"] == "final" and shown.proposal["source"] == "detail"
    assert "tier final" in shown.summary and "detailed copy" in shown.summary
    assert shown.proposal["kind"] == "still" and "a still" in shown.summary
    declined = render_detail.run(final(), bound())
    assert "approval" in declined
    assert not any("render_still.py" in " ".join(c) for c in tool_state.launched)


def test_an_approved_final_saves_the_live_file_then_renders_the_detail_copy(bound, live, tool_state) -> None:
    started(bound)
    folder = folder_of(tool_state)
    result = render_detail.run(final(), replace(bound(), approved=True))
    assert result.startswith("Started a final still of the detailed bench version 1")
    assert result.endswith("When it finishes, a Review button appears in this chat.")
    assert "viewer.html" not in result
    job = wait_job(folder, "detail-still")
    assert job["tier"] == "final"
    assert png_size(storage.detail_dir(folder) / "still.png") == (1500, 1500)
    assert SAVE_TEMPLATE in live.scripts
    argv = next(c for c in tool_state.launched if any("render_still.py" in p for p in c))
    assert argv[argv.index("--blend") + 1] == str(storage.detail_blend_path(folder))
    assert not (folder / "still.png").exists()


def test_a_closed_blender_does_not_stop_the_final(bound, live, tool_state) -> None:
    started(bound)

    async def closed(kind, params=None):
        raise LiveRefused("Blender is not open with the MCP addon")

    live.command = closed
    result = render_detail.run(final(kind="still"), replace(bound(), approved=True))
    assert result.startswith("Started a final still")
    wait_job(folder_of(tool_state), "detail-still")
    assert (storage.detail_dir(folder_of(tool_state)) / "still.png").is_file()


# --- a composed room (room-composition) -------------------------------------------------


def test_a_detail_pass_lights_a_composed_room_on_a_copy(make_ctx, tool_deps, tool_state, live) -> None:
    from tests.test_builder_tools import composed

    composed(make_ctx, tool_deps, tool_state)
    room = storage.composition_version_dir(tool_state.settings.render_root, "wohnen", 1)
    document_before = (room / storage.INPUT_FILE).read_bytes()
    blend_before = (room / "model.blend").read_bytes()
    target = {"composition": "Wohnen"}

    shown = start_detail_pass.preview(target, make_ctx())
    assert isinstance(shown, Confirmation) and "wohnen version 1" in shown.summary
    result = start_detail_pass.run(target, replace(make_ctx(), approved=True))
    assert "detail pass is open on wohnen version 1" in result
    detail = storage.detail_blend_path(room)
    assert detail.read_bytes() == blend_before and live.open_file == str(detail)

    script = {**target, "code": "import bpy\nbpy.data.lights['LGT_Ceiling'].energy = 400\n", "purpose": "warmer ceiling light"}
    assert "refused" not in run_detail_script.run(script, make_ctx()).lower()
    shot = detail_screenshot.run(target, make_ctx())
    assert "/compositions/wohnen/versions/1/files/detail/screens/0" in shot

    assert "final" in render_detail.run({**target, "tier": "draft"}, make_ctx())
    pause = render_detail.preview({**target, "tier": "final", "kind": "still"}, make_ctx())
    assert isinstance(pause, Confirmation) and pause.subject == "detail_render"
    assert (room / storage.INPUT_FILE).read_bytes() == document_before, "nothing is written to the composition"


def test_an_approved_final_detail_render_posts_a_notice(bound, live, tool_deps, tool_state) -> None:
    from tests.graph_helpers import make_harness
    from tests.test_builder_tools import wait_notices

    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    started(bound)
    render_detail.run(final(), replace(bound(thread_id=harness.thread), approved=True))
    assert wait_notices(tool_deps, harness.thread) == [("succeeded", "final", "bench", 1)]
