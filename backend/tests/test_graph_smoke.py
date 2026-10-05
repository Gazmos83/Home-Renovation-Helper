"""design-agents: one plain turn runs through the Foreman to Intake."""

from __future__ import annotations

from app.agent.foreman import last_reply
from tests.graph_helpers import fake_models, make_harness


def test_a_plain_turn_runs_through_intake(tool_state) -> None:
    models = fake_models(
        foreman={"decisions": [{"specialist": "intake", "reason": "a new wish"}]},
        intake={"replies": ["How wide is the hall?"]},
    )
    harness = make_harness(tool_state, models)

    state = harness.turn("I want a bench for the hall")

    assert state["specialist"] == "intake"
    assert last_reply(state) == "How wide is the hall?"
    assert models["intake"].calls == 1
    assert models["designer"].calls == 0
    assert not harness.snapshot().interrupts
