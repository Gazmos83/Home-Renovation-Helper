"""pricing-researcher: built piece -> "what will it cost?" -> price_cut_list -> a reply from the stored pricing."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agent import house_file
from app.agent.foreman import last_reply
from app.agent.tools.base import ToolDeps
from app.pricing.pricing import list_pricings
from tests.fakes import tool_call
from tests.graph_helpers import fake_models, make_harness
from tests.pricing_helpers import clean_pricing
from tests.test_foreman import decision
from tests.test_pricing import home_store, price_the_desk, write_version


def test_the_researcher_prices_the_bound_piece_and_the_reply_has_only_the_stored_figures(tool_state) -> None:
    clean_pricing(tool_state.engine)
    try:
        write_version(tool_state.settings.render_root)
        with Session(tool_state.engine) as session:
            home_store(session)
            price_the_desk(session)
            session.commit()
        models = fake_models(
            foreman={"decisions": [decision("researcher")]},
            researcher={"steps": [[tool_call("price_cut_list", {"package_id": "hall-desk"})], "Here is the price."]},
        )
        harness = make_harness(tool_state, models)
        harness.start()
        with ToolDeps(tool_state).session() as session:
            house_file.record_piece(session, "hall-desk", "Hall desk")
            house_file.record_version(session, "hall-desk", 1)
            house_file.approve_version(session, "hall-desk", 1)
            house_file.touch_thread(session, harness.thread, package_id="hall-desk")
            session.commit()

        state = harness.turn("what will it cost?")

        assert state["specialist"] == "researcher"
        with Session(tool_state.engine) as session:
            rows = list_pricings(session, "hall-desk", 1)
        assert len(rows) == 1
        total = f"{rows[0].total_cents // 100},{rows[0].total_cents % 100:02d} EUR"
        # The model's second prompt carries the tool result, with the stored total in it.
        assert f"total {total}" in models["researcher"].last_prompt_text()
        assert f"Pricing {rows[0].id}" in models["researcher"].last_prompt_text()
        assert last_reply(state) == "Here is the price."
    finally:
        clean_pricing(tool_state.engine)


def test_the_researcher_is_told_to_have_an_unapproved_version_approved_first(tool_state) -> None:
    clean_pricing(tool_state.engine)
    try:
        write_version(tool_state.settings.render_root)
        with Session(tool_state.engine) as session:
            home_store(session)
            price_the_desk(session)
            session.commit()
        models = fake_models(
            foreman={"decisions": [decision("researcher")]},
            researcher={
                "steps": [[tool_call("price_cut_list", {"package_id": "hall-desk"})], "Please approve it first."]
            },
        )
        harness = make_harness(tool_state, models)
        harness.start()
        with ToolDeps(tool_state).session() as session:
            house_file.record_piece(session, "hall-desk", "Hall desk")
            house_file.record_version(session, "hall-desk", 1)
            house_file.touch_thread(session, harness.thread, package_id="hall-desk")
            session.commit()

        state = harness.turn("what will it cost?")

        prompt = models["researcher"].last_prompt_text()
        assert "the cut list cannot be priced" in prompt
        assert "approve it first in the version's inspector" in prompt
        assert last_reply(state) == "Please approve it first."
        with Session(tool_state.engine) as session:
            assert list_pricings(session, "hall-desk", 1) == []
    finally:
        clean_pricing(tool_state.engine)
