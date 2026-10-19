"""token-budget: counting, trimming, too-large refusal, daily ceiling."""

from __future__ import annotations

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import StructuredTool
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.budget import (
    DEFAULT_DAILY_CEILING,
    IMAGE_TOKENS,
    BudgetRefused,
    RequestBudget,
    check_daily,
    count,
    fit,
    prepare,
    refusal_message,
)
from app.auth.accounts import ensure_owner
from app.db.models import ModelUsage
from app.observability.usage import tokens_today
from conftest import OWNER_PASSWORD

SYSTEM = [SystemMessage("You are the workshop assistant.")]


def _exchange(n: int, words: int = 40) -> list[BaseMessage]:
    return [
        HumanMessage(f"question {n} " + "about plywood " * words, id=f"h{n}"),
        AIMessage(f"answer {n} " + "birch veneer " * words, id=f"a{n}"),
    ]


def _tool_exchange(n: int) -> list[BaseMessage]:
    call = {"name": "cut_list", "args": {"package_id": str(n)}, "id": f"call-{n}"}
    return [
        HumanMessage(f"price package {n} " + "please " * 30, id=f"h{n}"),
        AIMessage("", tool_calls=[call], id=f"a{n}"),
        ToolMessage("priced at 12 EUR " * 20, tool_call_id=f"call-{n}", id=f"t{n}"),
        AIMessage(f"package {n} costs 12 EUR", id=f"f{n}"),
    ]


def test_everything_is_kept_when_it_fits() -> None:
    history = [*_exchange(1), *_exchange(2), HumanMessage("and now?")]
    budget = RequestBudget(limit=32_000, output_reserve=2_048)
    request = fit(budget, SYSTEM, history)
    assert request == [*SYSTEM, *history]


def test_a_long_thread_is_trimmed_with_the_note_and_the_stored_thread_unchanged() -> None:
    history: list[BaseMessage] = []
    for n in range(40):
        history += _exchange(n)
    current = HumanMessage("what did you say about the last board?", id="now")
    stored = list(history) + [current]
    budget = RequestBudget(limit=3_000, output_reserve=500)

    request = fit(budget, SYSTEM, stored)

    assert count(request) <= budget.usable
    assert request[-1] is current
    assert stored[-1] is current
    assert len(stored) == 81
    note = request[len(SYSTEM)]
    assert isinstance(note, SystemMessage)
    assert "earlier exchange(s)" in note.content
    first_kept = next(m for m in request if isinstance(m, (HumanMessage, AIMessage)))
    assert isinstance(first_kept, HumanMessage)


def test_a_tool_call_is_never_separated_from_its_result() -> None:
    history: list[BaseMessage] = []
    for n in range(25):
        history += _tool_exchange(n)
    history.append(HumanMessage("and the next one?"))
    budget = RequestBudget(limit=2_500, output_reserve=400)

    request = fit(budget, SYSTEM, history)

    call_ids = {c["id"] for m in request if isinstance(m, AIMessage) for c in m.tool_calls}
    result_ids = {m.tool_call_id for m in request if isinstance(m, ToolMessage)}
    assert call_ids == result_ids
    assert call_ids


def test_a_too_large_message_is_refused_with_no_call() -> None:
    huge = HumanMessage("x " * 20_000)
    budget = RequestBudget(limit=4_000, output_reserve=500)
    with pytest.raises(BudgetRefused) as caught:
        fit(budget, SYSTEM, [huge])
    assert caught.value.kind == "input_too_large"
    assert caught.value.needed > caught.value.usable == budget.usable


def test_images_are_counted_at_a_fixed_cost() -> None:
    text = HumanMessage("hi")
    image = HumanMessage(
        content=[
            {"type": "text", "text": "hi"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xx"}},
        ]
    )
    assert count([image]) >= count([text]) + IMAGE_TOKENS


def test_tool_schemas_count_as_mandatory() -> None:
    def lookup(product: str) -> str:
        return ""

    tool = StructuredTool.from_function(lookup, description="Look a product up. " + "detail " * 200)
    message = [HumanMessage("hi")]
    assert count(message, [tool]) > count(message)


def test_the_ceiling_refuses_across_two_turns(migrated_database: str) -> None:
    from uuid import uuid4

    from app.db.session import make_engine

    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("DELETE FROM model_usage WHERE model_id = 'deepseek/deepseek-v4-pro-0813'"))
        owner = ensure_owner(session, "owner@example.com", OWNER_PASSWORD)
        session.add(
            ModelUsage(
                id=uuid4(),
                model_id="deepseek/deepseek-v4-pro-0813",
                operation="chat.designer",
                input_tokens=1_000,
                output_tokens=500,
                estimated_tokens=1_800,
                user_id=owner.id,
            )
        )
        session.commit()
    used = tokens_today(engine, "deepseek/deepseek-v4-pro-0813", "Europe/Berlin")
    assert used == 1_500
    with pytest.raises(BudgetRefused) as caught:
        check_daily(used, needed=1_000, ceiling=2_000)
    assert caught.value.kind == "daily_limit"
    engine.dispose()


def test_a_row_without_token_figures_counts_its_estimate(migrated_database: str) -> None:
    from uuid import uuid4

    from app.db.session import make_engine

    engine = make_engine(migrated_database)
    with Session(engine) as session:
        session.execute(text("DELETE FROM model_usage WHERE model_id = 'openai/gpt-5.6-luna'"))
        owner = ensure_owner(session, "owner@example.com", OWNER_PASSWORD)
        session.add(
            ModelUsage(
                id=uuid4(),
                model_id="openai/gpt-5.6-luna",
                operation="chat.foreman",
                input_tokens=None,
                output_tokens=None,
                estimated_tokens=900,
                user_id=owner.id,
            )
        )
        session.commit()
    assert tokens_today(engine, "openai/gpt-5.6-luna", "Europe/Berlin") == 900
    engine.dispose()


def test_prepare_refuses_the_daily_ceiling_before_the_call() -> None:
    budget = RequestBudget(limit=32_000, output_reserve=100)
    with pytest.raises(BudgetRefused) as caught:
        prepare(
            budget,
            "sys",
            [HumanMessage("hi")],
            used_today=DEFAULT_DAILY_CEILING,
            daily_ceiling=DEFAULT_DAILY_CEILING,
        )
    assert caught.value.kind == "daily_limit"


def test_refusal_names_the_role_and_not_a_slug() -> None:
    text = refusal_message("designer", BudgetRefused("daily_limit", 10, 1))
    assert text.startswith("Lil' Glitty can't take this on right now:")
    assert "midnight" in text
    assert "deepseek" not in text
    assert "token" not in text


def _long_thread() -> tuple[list[BaseMessage], HumanMessage]:
    history: list[BaseMessage] = []
    for n in range(40):
        history += _exchange(n)
    return history, HumanMessage("what did you say about the last board?", id="now")


def test_dropped_exchanges_are_replaced_by_their_summary() -> None:
    from app.agent.prompts import CLOSE_TOKEN, SUMMARY_LABEL

    history, current = _long_thread()
    seen: list[list[BaseMessage]] = []

    def summarize(dropped: list[BaseMessage]) -> str:
        seen.append(dropped)
        return "Rooms: hall 1200 × 3000 mm. Pieces: hall-bench v2. Open: the wood."

    budget = RequestBudget(limit=3_000, output_reserve=500)
    request = fit(budget, SYSTEM, [*history, current], summarize=summarize)

    assert count(request) <= budget.usable
    assert len(seen) == 1 and seen[0][0].id == "h0"
    kept_ids = {m.id for m in request}
    assert not kept_ids & {m.id for m in seen[0]}
    summary = request[len(SYSTEM)]
    assert isinstance(summary, SystemMessage)
    assert summary.content.startswith(SUMMARY_LABEL)
    assert "hall 1200 × 3000 mm" in summary.content and summary.content.endswith(CLOSE_TOKEN)
    assert "earlier exchange(s)" not in str([m.content for m in request])
    assert request[-1] is current


def test_no_summary_or_one_too_large_falls_back_to_the_note() -> None:
    history, current = _long_thread()
    budget = RequestBudget(limit=3_000, output_reserve=500)
    for answer in (None, "", "decisions " * 5_000):
        request = fit(budget, SYSTEM, [*history, current], summarize=lambda _dropped, a=answer: a)
        note = request[len(SYSTEM)]
        assert "earlier exchange(s)" in note.content
        assert count(request) <= budget.usable


def test_nothing_is_summarised_when_everything_fits() -> None:
    history = [*_exchange(1), *_exchange(2), HumanMessage("and now?")]

    def summarize(_dropped):
        raise AssertionError("no summary call when nothing is dropped")

    assert fit(RequestBudget(limit=32_000, output_reserve=2_048), SYSTEM, history, summarize=summarize) == [*SYSTEM, *history]
