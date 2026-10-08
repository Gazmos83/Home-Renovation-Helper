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
