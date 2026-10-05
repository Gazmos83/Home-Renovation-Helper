"""token-budget: a specialist refusal is a 200 reply naming the role, nothing pending."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.agent.foreman import build_graph, last_reply
from app.agent.models.budgets import Budgets
from app.agent.tools.base import ToolDeps
from app.auth.accounts import ensure_owner
from app.db.models import ModelUsage, OperatorSetting
from conftest import OWNER_EMAIL, OWNER_PASSWORD
from tests.fakes import tool_call
from tests.graph_helpers import Harness, fake_models
from tests.test_foreman import HALL, decision

DESIGNER_SLUG = "deepseek/deepseek-v4-pro-0813"


def test_the_designers_daily_refusal_is_a_200_naming_the_designer(tool_state) -> None:
    with Session(tool_state.engine) as session:
        owner = ensure_owner(session, OWNER_EMAIL, OWNER_PASSWORD)
        session.merge(
            OperatorSetting(
                key=f"budget:{DESIGNER_SLUG}",
                value=json.dumps({"context_budget_tokens": 32000, "daily_token_ceiling": 50}),
                updated_at=datetime.now(UTC),
            )
        )
        session.add(
            ModelUsage(
                id=uuid4(),
                model_id=DESIGNER_SLUG,
                operation="chat.designer",
                input_tokens=40,
                output_tokens=20,
                estimated_tokens=80,
                user_id=owner.id,
            )
        )
        session.commit()

    models = fake_models(
        foreman={"decisions": [decision("intake"), decision("designer")]},
        intake={
            "tool_call_scripts": [[tool_call("record_brief", HALL)]],
            "replies": ["Saved."],
        },
        designer={"replies": ["should not run"]},
    )
    graph = build_graph(
        tool_state.engine,
        tool_state.settings,
        model_provider=models.__getitem__,
        model_ids=lambda slot: DESIGNER_SLUG if slot == "designer" else f"fake/{slot}",
        checkpointer=InMemorySaver(),
        deps=ToolDeps(tool_state),
        budgets=Budgets(tool_state.engine),
    )
    harness = Harness(graph=graph, models=models, state=tool_state)
    harness.start()
    harness.turn("a hall bench")
    harness.answer("yes")
    state = harness.turn("design it")
    reply = last_reply(state)
    assert "Designer" in reply
    assert "midnight" in reply
    assert DESIGNER_SLUG not in reply
    assert "token" not in reply
    assert models["designer"].calls == 0
    assert not harness.snapshot().interrupts
