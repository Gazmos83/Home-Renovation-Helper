"""feedback-capture: the chat tool that records a spoken reaction to a render."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.foreman import last_reply
from app.agent.tools.base import Confirmation
from app.agent.tools.render_feedback import preview, record_render_feedback, run
from app.db.models import RenderFeedback, RenderRun
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness


def add_run(tool_state, *, key="turntable", version=1, tier="draft", age_minutes=0, outcome="succeeded", package="bench"):
    with Session(tool_state.engine) as session:
        run_ = RenderRun(
            id=uuid4(), package_id=package, version=version, render_key=key, tier=tier,
            outcome=outcome, slot="builder", model="deepseek/deepseek-v4-pro-0813",
            trace_id="b" * 32, started_at=datetime.now(UTC) - timedelta(minutes=age_minutes),
        )
        session.add(run_)
        session.commit()
        return run_.id


def stored(tool_state) -> list[tuple[RenderRun, RenderFeedback]]:
    with Session(tool_state.engine) as session:
        rows = session.execute(
            select(RenderRun, RenderFeedback).join(RenderFeedback, RenderFeedback.run_id == RenderRun.id)
        ).all()
        return [(a, b) for a, b in rows]


def test_the_tool_proposes_what_it_read_and_stores_nothing_until_yes(make_ctx, tool_state) -> None:
    add_run(tool_state)
    ctx = make_ctx(package_id="bench")
    shown = preview({"rating": "down", "comment": "far too dark"}, ctx)
    assert isinstance(shown, Confirmation) and shown.subject == "render_feedback"
    assert "thumbs down" in shown.summary and "bench version 1 turntable (draft)" in shown.summary
    assert "far too dark" in shown.summary
    assert shown.proposal["rating"] == "down" and shown.proposal["comment"] == "far too dark"
    assert stored(tool_state) == []
    assert "confirmation" in run({"rating": "down"}, ctx)
    assert stored(tool_state) == []


def test_an_approved_rating_is_stored_with_the_comment(make_ctx, tool_state) -> None:
    add_run(tool_state)
    result = run({"rating": "down", "comment": "  far too dark "}, replace(make_ctx(package_id="bench"), approved=True))
    assert result == "Recorded a thumbs down on bench version 1 turntable (draft)."
    [(_, feedback)] = stored(tool_state)
    assert (feedback.rating, feedback.comment) == ("down", "far too dark")


def test_the_default_target_is_the_most_recent_succeeded_render(make_ctx, tool_state) -> None:
    add_run(tool_state, key="turntable", version=1, age_minutes=30)
    newest = add_run(tool_state, key="still", version=2, tier="draft", age_minutes=5)
    add_run(tool_state, key="turntable", version=2, age_minutes=1, outcome="failed")
    add_run(tool_state, key="still", version=3, age_minutes=0, package="other")
    shown = preview({"rating": "up"}, make_ctx(package_id="bench"))
    assert shown.proposal["render"] == "still" and shown.proposal["version"] == 2
    run({"rating": "up"}, replace(make_ctx(package_id="bench"), approved=True))
    [(rated_run, _)] = stored(tool_state)
    assert rated_run.id == newest


def test_a_named_render_and_version_are_honoured(make_ctx, tool_state) -> None:
    add_run(tool_state, key="turntable", version=1, age_minutes=30)
    add_run(tool_state, key="still", version=2, age_minutes=1)
    shown = preview({"rating": "up", "render": "turntable", "version": 1}, make_ctx(package_id="bench"))
    assert (shown.proposal["render"], shown.proposal["version"]) == ("turntable", 1)
    detail = add_run(tool_state, key="detail-still", version=1, tier="final", age_minutes=2)
    shown = preview({"rating": "down", "render": "detail-still"}, make_ctx(package_id="bench"))
    assert "detailed still (final)" in shown.summary
    run({"rating": "down", "render": "detail-still"}, replace(make_ctx(package_id="bench"), approved=True))
    assert stored(tool_state)[0][0].id == detail


def test_nothing_rendered_is_refused(make_ctx, tool_state) -> None:
    add_run(tool_state, outcome="queued")
    assert "no finished render" in preview({"rating": "up"}, make_ctx(package_id="bench"))
    assert "no finished render" in run({"rating": "up"}, replace(make_ctx(package_id="bench"), approved=True))
    assert stored(tool_state) == []


def test_no_bound_piece_unknown_render_and_bad_rating_are_refused(make_ctx, tool_state) -> None:
    add_run(tool_state)
    assert "no piece bound" in preview({"rating": "up"}, make_ctx())
    assert "unknown render" in preview({"rating": "up", "render": "ultra"}, make_ctx(package_id="bench"))
    assert "'up' or 'down'" in preview({"rating": "sideways"}, make_ctx(package_id="bench"))
    assert "longer than" in preview({"rating": "up", "comment": "x" * 1001}, make_ctx(package_id="bench"))


def test_a_package_id_the_model_supplies_is_ignored(make_ctx, tool_state) -> None:
    add_run(tool_state, package="bench")
    add_run(tool_state, package="other", age_minutes=-5)  # newer, but not this conversation's piece
    shown = preview({"rating": "up", "package_id": "other"}, make_ctx(package_id="bench"))
    assert shown.proposal["package_id"] == "bench"


def test_the_rating_is_traced_when_tracing_is_on(make_ctx, tool_state) -> None:
    add_run(tool_state)
    seen: list[dict] = []

    class Tracer:
        def record_feedback(self, **fields) -> None:
            seen.append(fields)

    tool_state.tracing = Tracer()
    run({"rating": "up", "comment": "lovely"}, replace(make_ctx(package_id="bench"), approved=True))
    assert seen[0]["rating"] == "up" and seen[0]["comment"] == "lovely"
    assert seen[0]["trace_id"] == "b" * 32 and seen[0]["slot"] == "builder"


def test_the_builder_asks_and_records_only_on_yes(tool_state, make_ctx) -> None:
    from tests.test_foreman import _build_piece

    _build_piece(tool_state, make_ctx)
    add_run(tool_state, key="turntable", version=1)
    models = fake_models(
        foreman={"decisions": [{"specialist": "builder", "reason": "reaction"}]},
        builder={
            "steps": [
                [tool_call("record_render_feedback", {"rating": "down", "comment": "too dark"}, "c1")],
                "Noted.",
            ]
        },
    )
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    harness.turn("the draft is too dark 👎")
    [pause] = harness.snapshot().interrupts
    assert pause.value["subject"] == "render_feedback"
    assert stored(tool_state) == []
    state = harness.answer("yes")
    assert last_reply(state) == "Noted."
    [(_, feedback)] = stored(tool_state)
    assert (feedback.rating, feedback.comment) == ("down", "too dark")


def test_declining_stores_nothing(tool_state, make_ctx) -> None:
    from tests.test_foreman import _build_piece

    _build_piece(tool_state, make_ctx)
    add_run(tool_state)
    models = fake_models(
        foreman={"decisions": [{"specialist": "builder", "reason": "reaction"}]},
        builder={"steps": [[tool_call("record_render_feedback", {"rating": "up"}, "c1")], "Ok, not recorded."]},
    )
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    harness.turn("nice 👍")
    harness.answer("no")
    assert stored(tool_state) == []
    assert "The rating was not recorded." in str(harness.snapshot().values["messages"][-2].content)


def test_both_builder_and_lighting_may_name_it() -> None:
    from app.agent.instructions import load_instructions

    loaded = load_instructions()
    assert "record_render_feedback" in loaded["builder"].tools
    assert "record_render_feedback" in loaded["lighting"].tools
    assert record_render_feedback.name == "record_render_feedback"


# --- restyle variants (two-tier-renders) -----------------------------------------------------------


def publish_variant(tool_state, variant: str = "walnut-draft", label: str = "Walnut", version: int = 1) -> None:
    import json

    from app.blender import storage
    from app.restyle import store

    folder = store.variant_dir(storage.version_dir(tool_state.settings.render_root, "bench", version), variant)
    folder.mkdir(parents=True)
    (folder / "still.png").write_bytes(b"png")
    (folder / "scene.json").write_text(json.dumps({"label": label, "tier": "draft"}), encoding="utf-8")


def test_a_variant_rated_in_chat_is_proposed_by_default_and_stored_only_on_yes(make_ctx, tool_state) -> None:
    add_run(tool_state, key="turntable", version=1, age_minutes=30)
    publish_variant(tool_state)
    variant = add_run(tool_state, key="variant:walnut-draft", version=1, tier="draft", age_minutes=1)
    args = {"rating": "up", "comment": "the walnut one is great"}
    shown = preview(args, make_ctx(package_id="bench"))
    assert shown.proposal["render"] == "variant:walnut-draft"
    assert 'bench version 1 restyle walnut-draft (draft) with the comment "the walnut one is great"' in shown.summary
    assert stored(tool_state) == []
    result = run(args, replace(make_ctx(package_id="bench"), approved=True))
    assert result == "Recorded a thumbs up on bench version 1 restyle walnut-draft (draft)."
    [(rated_run, feedback)] = stored(tool_state)
    assert rated_run.id == variant and feedback.comment == "the walnut one is great"


def test_a_variant_named_by_its_look_or_label_is_found(make_ctx, tool_state) -> None:
    publish_variant(tool_state)
    publish_variant(tool_state, "sage-green-draft", "Sage green")
    walnut = add_run(tool_state, key="variant:walnut-draft", version=1, age_minutes=5)
    add_run(tool_state, key="variant:sage-green-draft", version=1, age_minutes=1)
    for name in ("walnut", "Walnut", "variant:walnut-draft", "walnut-draft"):
        shown = preview({"rating": "up", "render": name}, make_ctx(package_id="bench"))
        assert shown.proposal["render"] == "variant:walnut-draft", name
    run({"rating": "up", "render": "walnut"}, replace(make_ctx(package_id="bench"), approved=True))
    assert stored(tool_state)[0][0].id == walnut
    assert "unknown render 'teak'" in preview({"rating": "up", "render": "teak"}, make_ctx(package_id="bench"))


def test_a_replaced_variant_is_not_the_default_target(make_ctx, tool_state) -> None:
    add_run(tool_state, key="turntable", version=1, age_minutes=30)
    add_run(tool_state, key="variant:oak-draft", version=1, age_minutes=1)  # its folder is gone
    shown = preview({"rating": "down"}, make_ctx(package_id="bench"))
    assert shown.proposal["render"] == "turntable"
