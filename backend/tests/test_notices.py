"""studio-layout: the render notice is written by code from the quote and the outcome,
placed after the messages the thread held, and never raises."""

from __future__ import annotations

from types import SimpleNamespace

from app.agent import house_file, notices
from app.agent.tools.base import ToolDeps
from app.render.guard import RenderQuote
from tests.graph_helpers import make_harness


def quote(tiers, tier: str = "draft", **fields) -> RenderQuote:
    base = {
        "package_id": "hall-bench",
        "version": 1,
        "kind": "turntable",
        "room": False,
        "tier": tiers.get(tier),
        "frames": 12,
        "estimate_seconds": 30.0,
    }
    return RenderQuote(**{**base, **fields})


def stored(tool_state, thread):
    with ToolDeps(tool_state).session() as session:
        return [
            (n.outcome, n.tier, n.text, n.package_id, n.version, n.after_messages)
            for n in house_file.notices_for(session, thread)
        ]


def test_a_finished_draft_turntable_of_a_piece_is_noticed(tool_state) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    harness.turn("hello")
    notices.post(ToolDeps(tool_state), harness.thread, quote(tool_state.tiers), "succeeded")
    [(outcome, tier, text, package, version, after)] = stored(tool_state, harness.thread)
    assert (outcome, tier, package, version) == ("succeeded", "draft", "hall-bench", 1)
    assert text == (
        "The draft turntable of hall-bench version 1 is ready. You can also check it in the Project panel."
    )
    assert after == len(harness.snapshot().values["messages"]) > 0


def test_a_final_still_and_a_detail_pass_name_what_they_are(tool_state) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    deps = ToolDeps(tool_state)
    notices.post(deps, harness.thread, quote(tool_state.tiers, "final", kind="still", version=3), "succeeded")
    notices.post(deps, harness.thread, quote(tool_state.tiers, "final", source="detail"), "succeeded")
    first, second = stored(tool_state, harness.thread)
    assert first[2].startswith("The final still of hall-bench version 3 is ready.")
    assert (first[3], first[4]) == ("hall-bench", 3)
    assert second[2].startswith("The final detail turntable of hall-bench version 1 is ready.")
    assert second[2].endswith("Project panel.")


def test_a_shell_and_a_composition_notice_has_no_piece_and_no_panel_sentence(tool_state) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    deps = ToolDeps(tool_state)
    notices.post(deps, harness.thread, quote(tool_state.tiers, package_id="flat", record="shell"), "succeeded")
    notices.post(deps, harness.thread, quote(tool_state.tiers, "preview", package_id="wohnen", record="room"), "succeeded")
    shell, room = stored(tool_state, harness.thread)
    assert shell[2] == "The draft turntable of the flat shell version 1 is ready."
    assert room[2] == "The preview turntable of wohnen version 1 is ready."
    assert (shell[3], shell[4], room[3], room[4]) == (None, None, None, None)


def test_a_failed_render_says_so_without_error_text(tool_state) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    notices.post(ToolDeps(tool_state), harness.thread, quote(tool_state.tiers, "preview", version=2), "failed")
    [(outcome, tier, text, *_)] = stored(tool_state, harness.thread)
    assert (outcome, tier) == ("failed", "preview")
    assert text == (
        "The preview turntable of hall-bench version 2 did not finish, so nothing new was published. "
        "You can ask for it again."
    )


def test_a_checkpointer_that_is_down_logs_and_writes_nothing(tool_state, caplog) -> None:
    harness = make_harness(tool_state)
    broken = SimpleNamespace(get_state=lambda config: (_ for _ in ()).throw(RuntimeError("down")))
    tool_state.graph = broken
    notices.post(ToolDeps(tool_state), harness.thread, quote(tool_state.tiers), "succeeded")
    assert stored(tool_state, harness.thread) == []
    assert "could not post a render notice" in caplog.text
    tool_state.graph = None
    notices.post(ToolDeps(tool_state), harness.thread, quote(tool_state.tiers), "succeeded")
    assert stored(tool_state, harness.thread) == []


def test_a_deleted_thread_gets_nothing_and_no_thread_posts_nothing(tool_state) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    deps = ToolDeps(tool_state)
    with deps.session() as session:
        house_file.delete_thread(session, harness.thread)
        session.commit()
    notices.post(deps, harness.thread, quote(tool_state.tiers), "succeeded")
    notices.post(deps, None, quote(tool_state.tiers), "succeeded")
    assert stored(tool_state, harness.thread) == []


# --- build notices (version-cleanup-and-inspection) ---------------------------------------


def built(tool_state, thread):
    with ToolDeps(tool_state).session() as session:
        return [
            (n.kind, n.outcome, n.tier, n.text, n.package_id, n.version)
            for n in house_file.notices_for(session, thread)
        ]


def test_a_finished_build_posts_a_build_notice(tool_state) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    harness.turn("hello")
    notices.post_build(ToolDeps(tool_state), harness.thread, "hall-bench", 2, "succeeded")
    assert built(tool_state, harness.thread) == [
        ("build", "succeeded", None, "hall-bench version 2 is built.", "hall-bench", 2)
    ]


def test_a_failed_build_says_so_without_error_text(tool_state) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    notices.post_build(ToolDeps(tool_state), harness.thread, "hall-bench", 2, "failed")
    [(kind, outcome, _tier, text, *_)] = built(tool_state, harness.thread)
    assert (kind, outcome) == ("build", "failed")
    assert text == "hall-bench version 2 did not build. You can ask for it again."


def test_a_build_with_no_thread_or_a_deleted_thread_posts_nothing(tool_state) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    deps = ToolDeps(tool_state)
    with deps.session() as session:
        house_file.delete_thread(session, harness.thread)
        session.commit()
    notices.post_build(deps, harness.thread, "hall-bench", 1, "succeeded")
    notices.post_build(deps, None, "hall-bench", 1, "succeeded")
    assert built(tool_state, harness.thread) == []


def test_a_build_notice_that_cannot_be_posted_is_logged(tool_state, caplog) -> None:
    harness = make_harness(tool_state)
    tool_state.graph = None
    notices.post_build(ToolDeps(tool_state), harness.thread, "hall-bench", 1, "succeeded")
    assert built(tool_state, harness.thread) == []
    assert "could not post a build notice" in caplog.text


def test_follow_build_reads_the_outcome_from_the_status_when_the_future_is_done(tool_state) -> None:
    from concurrent.futures import Future

    from app.blender import storage

    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    deps = ToolDeps(tool_state)
    folder = storage.version_dir(tool_state.settings.render_root, "hall-bench", 3)
    storage.write_status(folder, status="failed", error="Traceback: /home/secret/boom")
    future: Future = Future()
    notices.follow_build(deps, harness.thread, future, "hall-bench", 3)
    assert built(tool_state, harness.thread) == []
    future.set_result(None)
    [(kind, outcome, _tier, text, package, version)] = built(tool_state, harness.thread)
    assert (kind, outcome, package, version) == ("build", "failed", "hall-bench", 3)
    assert "secret" not in text and "Traceback" not in text
    notices.follow_build(deps, None, Future(), "hall-bench", 3)
    notices.follow_build(deps, harness.thread, None, "hall-bench", 3)


def test_a_revision_confirmed_in_a_conversation_posts_its_build_notice(tool_state, make_ctx) -> None:
    import time
    from dataclasses import replace

    from app.agent.tools.create_piece import run as create_run
    from app.agent.tools.revise_package import run as revise_run
    from app.blender import storage
    from tests.api_helpers import desk
    from tests.conftest import wait_for_status

    harness = make_harness(tool_state)
    tool_state.graph = harness.graph
    ctx = replace(make_ctx(thread_id=harness.thread), approved=True)
    create_run({"package_id": "hall-bench", "spec": desk()}, ctx)
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 1))
    revise_run({"package_id": "hall-bench", "changes": {"modules": {"cabinet": {"shelves": 3}}}}, ctx)
    wait_for_status(storage.version_dir(tool_state.settings.render_root, "hall-bench", 2))
    deadline = time.monotonic() + 5
    while len(built(tool_state, harness.thread)) < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert [(n[0], n[1], n[4], n[5]) for n in built(tool_state, harness.thread)] == [
        ("build", "succeeded", "hall-bench", 1), ("build", "succeeded", "hall-bench", 2),
    ]
