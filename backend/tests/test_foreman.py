"""design-agents: Foreman routing, the specialists' loops, prompt shape, thread isolation."""

from __future__ import annotations

from dataclasses import replace

from langchain_core.messages import HumanMessage

from app.agent import house_file
from app.agent.foreman import MAX_TOOL_ROUNDS, last_reply
from app.agent.prompts import UNTRUSTED_CONTENT_PREAMBLE
from app.agent.tools.base import ToolDeps
from app.agent.tools.create_piece import run as create_run
from tests.api_helpers import desk
from tests.conftest import wait_for_status
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness
from tests.test_review_evidence import _png

HALL = {
    "room_name": "Hall",
    "corners_mm": [[0, 0], [1200, 0], [1200, 3000], [0, 3000]],
    "ceiling_height_mm": 2400,
    "purpose": "a bench by the front door",
    "budget_eur": 400,
}


def decision(specialist: str) -> dict:
    return {"specialist": specialist, "reason": "test"}


def _bind_piece(tool_state, harness, *, screenshot: bool) -> None:
    folder = tool_state.settings.render_root / "hall-bench" / "v1"
    folder.mkdir(parents=True)
    (folder / "input.json").write_text("{}", encoding="utf-8")
    if screenshot:
        _png(folder / "screenshot.png")
    with ToolDeps(tool_state).session() as session:
        house_file.record_piece(session, "hall-bench", "Hall bench")
        house_file.record_version(session, "hall-bench", 1)
        house_file.touch_thread(session, harness.thread, package_id="hall-bench")
        session.commit()


def test_a_new_wish_with_no_piece_goes_to_intake_whatever_the_model_says(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("designer")]}, intake={"replies": ["Tell me more."]})
    state = make_harness(tool_state, models).turn("I want a bench")
    assert state["specialist"] == "intake"
    assert models["designer"].calls == 0


def test_the_builder_is_never_chosen_without_a_piece_with_a_version(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("builder")]}, intake={"replies": ["First a design."]})
    state = make_harness(tool_state, models).turn("render me a turntable")
    assert state["specialist"] == "intake"
    assert models["builder"].calls == 0
    assert last_reply(state) == "First a design."


def test_with_a_confirmed_brief_but_no_piece_the_builder_request_goes_to_the_designer(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("builder")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={"replies": ["Let me design it first."]},
    )
    harness = make_harness(tool_state, models)
    harness.turn("a hall bench, 1200 wide")
    harness.answer("yes")
    state = harness.turn("now render it")
    assert state["specialist"] == "designer"
    assert models["builder"].calls == 0


def test_a_bound_piece_with_a_version_lets_the_builder_answer(tool_state, make_ctx) -> None:
    create_run({"package_id": "bench", "spec": desk()}, replace(make_ctx(), approved=True))
    from app.blender import storage

    wait_for_status(storage.version_dir(tool_state.settings.render_root, "bench", 1))
    models = fake_models(foreman={"decisions": [decision("builder")]}, builder={"replies": ["Ready."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    state = harness.turn("show me the bench")
    assert state["specialist"] == "builder"
    assert last_reply(state) == "Ready."


def test_a_pending_confirmation_resumes_in_the_specialist_that_raised_it(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved. Shall I design it?"]},
    )
    harness = make_harness(tool_state, models)

    paused = harness.turn("a hall bench, 1200 wide, 2400 high, 400 euro")
    interrupts = harness.snapshot().interrupts
    assert len(interrupts) == 1
    assert interrupts[0].value["subject"] == "brief"
    assert models["intake"].calls == 1

    resumed = harness.answer("yes")
    assert last_reply(resumed) == "Saved. Shall I design it?"
    assert models["intake"].calls == 2
    assert models["foreman"].calls == 1          # not asked again on resume
    assert models["designer"].calls == 0
    assert paused is not None
    assert not harness.snapshot().interrupts


def test_the_round_cap_forces_a_text_answer_with_no_tools_bound(tool_state) -> None:
    loop_call = [tool_call("cut_list", {"package_id": "ghost"}, "c")]
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={
            "tool_call_scripts": [loop_call for _ in range(MAX_TOOL_ROUNDS + 3)],
            "replies": ["I could not finish; the cut list is still outstanding."],
        },
    )
    harness = make_harness(tool_state, models)
    harness.turn("hall bench")
    harness.answer("yes")
    state = harness.turn("list the parts of ghost")

    designer = models["designer"]
    assert designer.calls == MAX_TOOL_ROUNDS + 1
    assert designer.bound_tools == []
    assert "No further tool calls are available" in designer.last_prompt_text()
    assert last_reply(state) == "I could not finish; the cut list is still outstanding."


def test_the_prompt_carries_the_guard_once_and_binds_only_the_headers_tools(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={"replies": ["Designing."]},
    )
    harness = make_harness(tool_state, models)
    harness.turn("hall bench")
    harness.answer("yes")
    harness.turn("design it")

    system = str(models["designer"].prompts[-1][0].content)
    assert system.count(UNTRUSTED_CONTENT_PREAMBLE) == 1
    assert system.endswith(UNTRUSTED_CONTENT_PREAMBLE)
    assert set(models["designer"].bound_tools) == {
        "create_piece", "revise_package", "cut_list", "room_fit", "search_guidelines",
    }
    assert models["intake"].bound_tools == ["record_brief", "record_plan"]
    # The Foreman's own prompt is guarded and binds nothing.
    foreman_prompt = "\n".join(str(m.content) for m in models["foreman"].decision_prompts[-1])
    assert foreman_prompt.count(UNTRUSTED_CONTENT_PREAMBLE) == 1


def test_the_house_file_reaches_intake_and_the_designer_but_not_as_an_instruction(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={"tool_call_scripts": [[tool_call("record_brief", HALL)]], "replies": ["Saved."]},
        designer={"replies": ["Designing."]},
    )
    harness = make_harness(tool_state, models)
    harness.turn("hall bench")
    harness.answer("yes")
    harness.turn("design it")
    assert "Hall: 1200 × 3000 mm, ceiling 2400 mm" in models["designer"].last_prompt_text()
    assert "budget_eur: 400" in models["designer"].last_prompt_text()


def test_two_threads_do_not_share_a_conversation(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("intake")]},
        intake={"replies": ["First answer.", "Second answer."]},
    )
    one = make_harness(tool_state, models)
    two = make_harness(tool_state, models)
    two.graph = one.graph  # the same compiled graph and checkpointer, two threads

    one.turn("a secret about the hall")
    two.turn("something else")

    second_prompt = "\n".join(str(m.content) for m in models["intake"].prompts[-1])
    assert "something else" in second_prompt
    assert "a secret about the hall" not in second_prompt
    assert [m.content for m in one.snapshot().values["messages"] if isinstance(m, HumanMessage)] == [
        "a secret about the hall"
    ]


def test_the_builder_can_answer_for_an_apartment_with_a_shell_but_not_before(tool_state, make_ctx) -> None:
    from app.agent import house_file
    from app.agent.tools.base import ToolDeps
    from plugins.blender_build.tool import run_shell
    from tests.test_record_plan import PLAN

    models = fake_models(
        foreman={"decisions": [decision("builder"), decision("builder")]},
        intake={"replies": ["First the plan."]},
        builder={"replies": ["The shell is ready."]},
    )
    harness = make_harness(tool_state, models)
    with ToolDeps(tool_state).session() as session:
        house_file.upsert_apartment(
            session, "Flat", 2550, 120,
            [{"name": r["name"], "corners_mm": r["corners_mm"], "openings": r.get("openings", [])} for r in PLAN["rooms"]],
        )
        session.commit()

    # An apartment with no shell version gives the Builder nothing to work on.
    first = harness.turn("show me the flat")
    assert first["specialist"] == "intake" and models["builder"].calls == 0

    run_shell({"apartment_name": "Flat"}, make_ctx())
    second = harness.turn("show me the flat now")
    assert second["specialist"] == "builder"
    assert "Apartments: Flat (2 room(s), shell v1)" in models["builder"].last_prompt_text()
    assert last_reply(second) == "The shell is ready."


def test_the_reviewer_is_chosen_when_a_render_exists(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("reviewer")]},
        reviewer={"replies": ["The screenshot matches the brief."]},
    )
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=True)
    state = harness.turn("check the bench against the brief")
    assert state["specialist"] == "reviewer"
    assert last_reply(state) == "The screenshot matches the brief."


def test_the_reviewer_is_never_chosen_without_a_screenshot_or_render(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("reviewer")]},
        builder={"replies": ["Build it first so there is a screenshot to check."]},
        reviewer={"replies": ["should not run"]},
    )
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=False)
    state = harness.turn("check the bench against the brief")
    assert state["specialist"] == "builder"
    assert models["reviewer"].calls == 0
    assert last_reply(state) == "Build it first so there is a screenshot to check."


def test_the_reviewer_binds_only_revision_review(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("reviewer")]},
        reviewer={"replies": ["Checked."]},
    )
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=True)
    harness.turn("check it")
    assert models["reviewer"].bound_tools == ["revision_review"]


def test_a_price_question_goes_to_the_researcher_even_without_a_brief_or_piece(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("researcher")]},
        intake={"replies": ["should not run"]},
        researcher={"replies": ["I can look that up."]},
    )
    state = make_harness(tool_state, models).turn("what does a birch ply sheet cost?")
    assert state["specialist"] == "researcher"
    assert models["intake"].calls == 0
    assert last_reply(state) == "I can look that up."


def test_the_researcher_binds_exactly_its_five_tools(tool_state) -> None:
    models = fake_models(foreman={"decisions": [decision("researcher")]}, researcher={"replies": ["Ok."]})
    make_harness(tool_state, models).turn("price it")
    assert set(models["researcher"].bound_tools) == {
        "search_catalog_knowledge", "check_live_listing", "compare_products", "price_cut_list", "manage_remnants",
    }


def _build_piece(tool_state, make_ctx) -> None:
    create_run({"package_id": "bench", "spec": desk()}, replace(make_ctx(), approved=True))
    from app.blender import storage

    wait_for_status(storage.version_dir(tool_state.settings.render_root, "bench", 1))


def test_lighting_is_chosen_for_a_built_piece(tool_state, make_ctx) -> None:
    _build_piece(tool_state, make_ctx)
    models = fake_models(
        foreman={"decisions": [decision("lighting")]},
        lighting={"replies": ["Shall I start a detail pass?"]},
    )
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    state = harness.turn("make the oak look realistic")
    assert state["specialist"] == "lighting"
    assert last_reply(state) == "Shall I start a detail pass?"


def test_lighting_is_never_chosen_without_a_successful_build(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("lighting")]},
        builder={"replies": ["Build it first."]},
        lighting={"replies": ["should not run"]},
    )
    harness = make_harness(tool_state, models)
    _bind_piece(tool_state, harness, screenshot=False)
    state = harness.turn("make the oak look realistic")
    assert state["specialist"] == "builder"
    assert models["lighting"].calls == 0


def test_lighting_with_no_piece_goes_to_intake(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [decision("lighting")]},
        intake={"replies": ["Tell me what to design."]},
    )
    state = make_harness(tool_state, models).turn("photoreal please")
    assert state["specialist"] == "intake"
    assert models["lighting"].calls == 0


def test_lighting_binds_exactly_the_detail_tools_and_is_text_only(tool_state, make_ctx) -> None:
    from app.agent.models.routing import IMAGE_SLOTS

    _build_piece(tool_state, make_ctx)
    models = fake_models(foreman={"decisions": [decision("lighting")]}, lighting={"replies": ["Ok."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    harness.turn("detail it")
    assert models["lighting"].bound_tools == [
        "start_detail_pass", "run_detail_script", "detail_screenshot", "render_detail",
        "record_render_feedback",
    ]
    assert "lighting" not in IMAGE_SLOTS


# --- render feedback reaches the Designer and Lighting, not Intake (feedback-capture) ----------------


def _rate(tool_state, comment: str, *, version: int = 1, key: str = "turntable", minutes: int = 0) -> None:
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from sqlalchemy.orm import Session

    from app.db.models import RenderFeedback, RenderRun

    when = datetime.now(UTC) - timedelta(minutes=minutes)
    with Session(tool_state.engine) as session:
        run = RenderRun(
            id=uuid4(), package_id="bench", version=version, render_key=key, tier="draft",
            outcome="succeeded", started_at=when,
        )
        session.add(run)
        session.flush()
        session.add(RenderFeedback(run_id=run.id, rating="down", comment=comment, created_at=when, updated_at=when))
        session.commit()


def test_recent_render_feedback_reaches_the_designer_and_lighting_but_not_intake(tool_state, make_ctx) -> None:
    _build_piece(tool_state, make_ctx)
    _rate(tool_state, "doors look too thick")
    models = fake_models(
        foreman={"decisions": [decision("designer"), decision("lighting"), decision("intake")]},
        designer={"replies": ["Noted."]},
        lighting={"replies": ["Noted."]},
        intake={"replies": ["Noted."]},
    )
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    for _ in range(3):
        harness.turn("anything")
    line = '- v1 · turntable · draft · down — "doors look too thick"'
    assert line in models["designer"].last_prompt_text()
    assert line in models["lighting"].last_prompt_text()
    assert "Recent render feedback" not in models["intake"].last_prompt_text()


def test_only_the_five_newest_ratings_are_given(tool_state, make_ctx) -> None:
    _build_piece(tool_state, make_ctx)
    for index in range(7):
        _rate(tool_state, f"comment {index}", minutes=70 - index)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Ok."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    harness.turn("tweak it")
    text = models["designer"].last_prompt_text()
    assert [f"comment {i}" in text for i in range(7)] == [False, False, True, True, True, True, True]
    assert text.index("comment 6") < text.index("comment 2")


def test_a_piece_with_no_ratings_gets_no_feedback_section(tool_state, make_ctx) -> None:
    _build_piece(tool_state, make_ctx)
    models = fake_models(foreman={"decisions": [decision("designer")]}, designer={"replies": ["Ok."]})
    harness = make_harness(tool_state, models)
    harness.start(package_id="bench")
    harness.turn("tweak it")
    assert "Recent render feedback" not in models["designer"].last_prompt_text()
