"""rag-evaluation: config, golden set, token cap, retrieval keys, answer prompt,
scoring under the cap, read-only session, report and score-only Langfuse trace."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from langchain_core.messages import ToolMessage
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.agent.instructions import load_instructions
from app.agent.prompts import CLOSE_TOKEN, OPEN_PREFIX, UNTRUSTED_CONTENT_PREAMBLE
from app.db.models import ModelUsage
from app.db.session import make_engine
from app.evals.budget import BudgetExhausted, RunBudget
from app.evals.config import EvalConfigError, load_eval_config
from app.evals.golden import GoldenEntry, GoldenSetError, check_keys, parse_golden
from app.evals.report import RunSummary, render, send_scores, write_report
from app.evals.run import (
    ALL_METRICS,
    ANSWER_METRICS,
    BUDGET,
    CONTEXT_METRICS,
    ID_METRICS,
    QuestionResult,
    Retrieved,
    RunState,
    answer,
    answer_messages,
    ragas_metrics,
    read_only_session,
    researcher_system,
    retrieve,
    score_question,
)
from app.guidelines.ingest import ingest_guidelines
from app.guidelines.sources import GuidelineSource
from tests.fakes import FakeChatModel
from tests.test_engineering_retrieval import publish

ENTRY = {
    "id": "g1",
    "question": "How far apart should shelf brackets be?",
    "reference": "No more than 600 mm apart.",
    "expected": ["https://example.org/brackets#0"],
    "path": "guideline",
    "split": "held_out",
}


def entry(**changes) -> GoldenEntry:
    return GoldenEntry.model_validate({**ENTRY, **changes})


def write_config(tmp_path: Path, **changes) -> Path:
    data = {
        "judge": "anthropic/claude-haiku-4.5",
        "token_ceiling": 1000,
        "golden_set": "backend/fixtures/evals/golden.yaml",
        "report_dir": "docs/evals",
        **changes,
    }
    path = tmp_path / "evals.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# --- config -----------------------------------------------------------------


def test_config_loads_with_absolute_paths(tmp_path) -> None:
    config = load_eval_config(write_config(tmp_path))
    assert config.golden_set.is_absolute() and config.report_dir.name == "evals"


def test_config_refuses_unknown_key(tmp_path) -> None:
    with pytest.raises(EvalConfigError, match="'max_workers'"):
        load_eval_config(write_config(tmp_path, max_workers=4))


@pytest.mark.parametrize("ceiling", [0, -5])
def test_config_refuses_non_positive_ceiling(tmp_path, ceiling) -> None:
    with pytest.raises(EvalConfigError, match="'token_ceiling'"):
        load_eval_config(write_config(tmp_path, token_ceiling=ceiling))


def test_config_refuses_unregistered_judge(tmp_path) -> None:
    with pytest.raises(EvalConfigError, match="google/gemini-3.5-flash"):
        load_eval_config(write_config(tmp_path, judge="google/gemini-3.5-flash"))


def test_checked_in_config_loads() -> None:
    assert load_eval_config().judge == "anthropic/claude-haiku-4.5"


# --- golden set ---------------------------------------------------------------


def test_golden_refuses_unknown_field_by_name() -> None:
    with pytest.raises(GoldenSetError, match=r"'g1'.*'expected_price'"):
        parse_golden({"questions": [{**ENTRY, "expected_price": 12}]})


def test_golden_refuses_duplicate_id() -> None:
    with pytest.raises(GoldenSetError, match="'g1' appears more than once"):
        parse_golden({"questions": [ENTRY, ENTRY]})


def test_golden_refuses_malformed_key() -> None:
    with pytest.raises(GoldenSetError, match="malformed key 'not-a-uuid:row-1'"):
        parse_golden({"questions": [{**ENTRY, "path": "engineering", "expected": ["not-a-uuid:row-1"]}]})


def test_golden_refuses_missing_key_by_question(db_session) -> None:
    entries = parse_golden({"questions": [ENTRY]})
    with pytest.raises(GoldenSetError, match=r"'g1' expects passage 'https://example.org/brackets#0'"):
        check_keys(db_session, entries)


@pytest.fixture
def guideline(db_session, fake_embedder, tmp_path, clean_chunks):
    (tmp_path / "brackets.md").write_text(
        "# Brackets\n\nShelf brackets sit no more than 600 mm apart on a stud wall.\n", encoding="utf-8"
    )
    source = GuidelineSource(
        id="brackets", title="Bracket Guide", jurisdiction="-", path="brackets.md", format="md",
        published_on=date(2020, 1, 1), licence="owner's copy",
    )
    report = ingest_guidelines(db_session, None, [source], root=tmp_path)
    assert report.ingested.get("brackets")
    url, index = db_session.execute(text("select url, chunk_index from chunks limit 1")).one()
    return f"{url}#{index}"


def test_golden_accepts_a_present_key(db_session, guideline) -> None:
    check_keys(db_session, parse_golden({"questions": [{**ENTRY, "expected": [guideline]}]}))


# --- token cap ----------------------------------------------------------------


def test_cap_refuses_the_call_that_would_cross_it(db_session) -> None:
    before = db_session.scalar(select(func.count()).select_from(ModelUsage))
    budget = RunBudget(25)
    model = FakeChatModel(callbacks=[budget.meter(10)])  # each call reports 10 tokens
    model.invoke("one")
    model.invoke("two")
    with pytest.raises(BudgetExhausted):
        model.invoke("three")  # 20 used + a 10-token cap > 25
    assert model.calls == 2 and budget.used == 20
    assert db_session.scalar(select(func.count()).select_from(ModelUsage)) == before


def test_cap_counts_the_reported_usage() -> None:
    budget = RunBudget(1000)
    FakeChatModel(callbacks=[budget.meter(500)]).invoke("hello")
    assert budget.used == 10  # usage_metadata: 5 in + 5 out, not the cap


# --- retrieval ----------------------------------------------------------------


def test_guideline_keys_are_url_and_chunk_index(db_session, guideline) -> None:
    retrieved = retrieve(db_session, entry(question="Shelf brackets sit no more than 600 mm apart on a stud wall."))
    assert retrieved.ids == [guideline]
    assert len(retrieved.contexts) == 1
    assert retrieved.contexts[0].startswith(OPEN_PREFIX) and retrieved.contexts[0].endswith(CLOSE_TOKEN)
    assert retrieved.contexts[0] in retrieved.tool_text


def test_engineering_keys_are_version_and_block(db_session, fake_embedder, tmp_path) -> None:
    question = "TEST board elasticity E 2000 MPa dry service at 18 mm"
    version = publish(db_session, tmp_path, text=question)
    retrieved = retrieve(db_session, entry(path="engineering", question=question, expected=[f"{version.id}:row-1"]))
    assert f"{version.id}:row-1" in retrieved.ids
    assert retrieved.local_only == []


def test_empty_retrieval_scores_zero_recall(db_session, fake_embedder, clean_chunks) -> None:
    retrieved = retrieve(db_session, entry(question="nothing in the corpus matches this"))
    assert retrieved.ids == []
    result = asyncio.run(
        score_question(entry(), retrieved, lambda: "I do not know.", _fake_metrics(None), RunState("judge"))
    )
    assert result.scores["id_based_context_recall"] == 0.0
    assert result.unscored["context_recall"] == "nothing retrieved"


# --- the Researcher's answer --------------------------------------------------


def test_answer_prompt_carries_guard_and_delimiters() -> None:
    system = researcher_system(load_instructions()["researcher"].text)
    assert system.endswith(UNTRUSTED_CONTENT_PREAMBLE)
    retrieved = Retrieved(
        ids=["u#0"], contexts=[f"{OPEN_PREFIX} url=\"u\"]]]\nx\n{CLOSE_TOKEN}"],
        tool_text=f"note\n\n{OPEN_PREFIX} url=\"u\"]]]\nx\n{CLOSE_TOKEN}",
    )
    budget = RunBudget(1000)
    meter = budget.meter(50)
    model = FakeChatModel(callbacks=[meter], replies=["An answer."])
    assert answer(model, answer_messages(system, entry(), retrieved)) == "An answer."
    prompt = model.prompts[-1]
    assert prompt[0].content == system
    assert isinstance(prompt[-1], ToolMessage) and OPEN_PREFIX in prompt[-1].content
    assert model.callbacks == [meter] and budget.used == 10


# --- scoring ------------------------------------------------------------------


class FakeMetric:
    """Calls the fake judge once (so the meter runs) and returns a fixed score."""

    def __init__(self, judge):
        self.judge = judge

    async def single_turn_ascore(self, sample):
        if self.judge is not None:
            self.judge.invoke("judge this")
        return 0.5


def _fake_metrics(judge) -> dict:
    from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall

    metrics = {name: FakeMetric(judge) for name in CONTEXT_METRICS + ANSWER_METRICS}
    metrics["id_based_context_recall"] = IDBasedContextRecall()
    metrics["id_based_context_precision"] = IDBasedContextPrecision()
    return metrics


RETRIEVED = Retrieved(ids=["https://example.org/brackets#0"], contexts=["passage"], tool_text="passage")


def test_budget_refusal_marks_the_rest_while_id_metrics_complete() -> None:
    budget = RunBudget(60)  # the first question's six 10-token calls fit; the next one does not
    judge = FakeChatModel(callbacks=[budget.meter(10)])
    answerer = FakeChatModel(callbacks=[budget.meter(10)], replies=["600 mm."] * 3)
    metrics = _fake_metrics(judge)
    state = RunState("judge")
    results = [
        asyncio.run(score_question(entry(id=f"g{n}"), RETRIEVED, lambda: answerer.invoke("q").text, metrics, state))
        for n in range(3)
    ]
    for result in results:
        assert set(ID_METRICS) <= set(result.scores)
    assert set(results[0].scores) == set(ALL_METRICS)  # 2 context + 1 answer + 3 answer-metric calls
    assert state.exhausted
    for result in results[1:]:
        assert result.unscored == {name: BUDGET for name in CONTEXT_METRICS + ANSWER_METRICS}
    assert budget.used <= budget.ceiling


class CutOffMetric:
    async def single_turn_ascore(self, sample):
        from ragas.exceptions import LLMDidNotFinishException

        raise LLMDidNotFinishException()


def test_a_cut_off_judge_reply_leaves_one_metric_unscored_and_the_run_going() -> None:
    metrics = {**_fake_metrics(None), "context_recall": CutOffMetric()}
    result = asyncio.run(score_question(entry(), RETRIEVED, lambda: "600 mm.", metrics, RunState("judge")))
    assert result.unscored == {"context_recall": "judge did not finish"}
    assert set(result.scores) == set(ALL_METRICS) - {"context_recall"}
    assert result.answer == "600 mm."


def test_local_only_engineering_packet_gets_id_metrics_only() -> None:
    judge = FakeChatModel()
    retrieved = Retrieved(ids=["v:row-1"], contexts=["evidence"], tool_text="evidence", local_only=["v:row-1"])
    result = asyncio.run(
        score_question(
            entry(path="engineering", expected=["00000000-0000-0000-0000-000000000000:row-1"]),
            retrieved, lambda: "unused", _fake_metrics(judge), RunState("judge"),
        )
    )
    assert set(result.scores) == set(ID_METRICS)
    assert result.unscored == {name: "remote-use rights" for name in CONTEXT_METRICS}
    assert "v:row-1" in result.note and judge.calls == 0


def test_budget_refusal_reaches_through_a_real_ragas_metric() -> None:
    import openai
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.run_config import RunConfig

    from app.evals.run import LocalEmbeddings

    budget = RunBudget(5)  # below the first call's cap
    judge = FakeChatModel(callbacks=[budget.meter(10)])
    # Ragas retries only rate limits for `ChatOpenAI`; the fake would otherwise retry everything.
    llm = LangchainLLMWrapper(
        judge, run_config=RunConfig(exception_types=openai.RateLimitError), bypass_temperature=True, bypass_n=True
    )
    metrics = ragas_metrics(llm, LangchainEmbeddingsWrapper(LocalEmbeddings()))
    state = RunState("judge")
    result = asyncio.run(score_question(entry(), RETRIEVED, lambda: "600 mm.", metrics, state))
    assert result.unscored["llm_context_precision_with_reference"] == BUDGET
    assert judge.calls == 0 and state.exhausted


# --- read-only session --------------------------------------------------------


def test_a_write_in_the_eval_session_raises(migrated_database) -> None:
    engine = make_engine(migrated_database)
    with read_only_session(engine) as session:
        with pytest.raises(DBAPIError, match="read-only transaction"):
            session.execute(text("INSERT INTO operator_settings (key, value) VALUES ('evals-test', 'x')"))
        session.rollback()
        with pytest.raises(DBAPIError, match="read-only transaction"):
            session.execute(text("DELETE FROM operator_settings WHERE key = 'evals-test'"))
    engine.dispose()


# --- report and Langfuse ------------------------------------------------------


def summary(results=None) -> RunSummary:
    scored = QuestionResult(
        entry(), scores={"id_based_context_recall": 1.0, "faithfulness": 0.75}, answer="Space them 600 mm apart.\n\nThat is all."
    )
    dev = QuestionResult(entry(id="d1", split="dev"), scores={"id_based_context_recall": 0.0})
    short = QuestionResult(entry(id="g2"), unscored={"faithfulness": BUDGET})
    return RunSummary(
        run_id="2026-10-19T12:00:00Z",
        results=results or [scored, dev, short],
        judge="anthropic/claude-haiku-4.5",
        researcher="openai/gpt-5.6-luna",
        embedding_model="BAAI/bge-m3",
        golden_set="backend/fixtures/evals/golden.yaml",
        golden_sha256="abc",
        tokens_used=1234,
        token_ceiling=5000,
        split_mode="all",
    )


def test_report_has_every_section() -> None:
    report = render(summary())
    for heading in (
        "## Headline scores (held-out)", "## Dev split (used for tuning", "## Per question",
        "## Not scored", "## What was measured",
    ):
        assert heading in report
    assert "anthropic/claude-haiku-4.5" in report and "BAAI/bge-m3" in report
    assert "2 held-out, 1 dev" in report and "1234 of the run's ceiling of 5000" in report
    assert "- g2: faithfulness: budget" in report
    assert "retrieval metrics only" in report
    assert "## Answers" in report and "### g1" in report and "> Space them 600 mm apart." in report
    assert "### g2" not in report  # no answer was given for it
    headline = report.split("## Headline scores (held-out)")[1].split("## Dev split")[0]
    assert "| id_based_context_recall | — | 1.000 (n=1) |" in headline  # dev's 0.0 is not in it


def test_second_report_on_one_date_does_not_overwrite(tmp_path) -> None:
    first = write_report(tmp_path, summary(), date(2026, 10, 19))
    original = first.read_text(encoding="utf-8")
    second = write_report(tmp_path, summary(), date(2026, 10, 19))
    assert first.name == "2026-10-19.md" and second.name == "2026-10-19-2.md"
    assert first.read_text(encoding="utf-8") == original


class FakeLangfuse:
    def __init__(self, fail=False):
        self.fail = fail
        self.payloads: list[dict] = []

    def start_as_current_observation(self, **kwargs):
        if self.fail:
            raise ConnectionError("down")
        self.payloads.append(kwargs)
        from contextlib import nullcontext

        return nullcontext(SimpleNamespace(trace_id="t1"))

    def create_score(self, **kwargs):
        self.payloads.append(kwargs)

    def flush(self):
        pass


def test_scores_carry_no_question_answer_or_passage_text() -> None:
    client = FakeLangfuse()
    assert send_scores(client, summary())
    sent = repr(client.payloads)
    assert ENTRY["question"] not in sent and ENTRY["reference"] not in sent and "brackets" not in sent
    scores = [payload for payload in client.payloads if "value" in payload]
    assert {score["name"] for score in scores} == {"ragas.id_based_context_recall", "ragas.faithfulness"}
    assert all(set(score["metadata"]) == {"question_id"} for score in scores)
    assert client.payloads[0]["metadata"] == {"judge": "anthropic/claude-haiku-4.5", "golden_set_sha256": "abc"}


def test_langfuse_down_still_leaves_the_report(tmp_path, caplog) -> None:
    path = write_report(tmp_path, summary(), date(2026, 10, 19))
    assert send_scores(FakeLangfuse(fail=True), summary()) is False
    assert path.exists() and "ragas scores were not sent to Langfuse" in caplog.text


# --- live -----------------------------------------------------------------------


@pytest.mark.live
def test_two_golden_questions_end_to_end(tmp_path) -> None:
    from app.config import REPO_ROOT, load_settings
    from app.evals.__main__ import run

    golden = yaml.safe_load((REPO_ROOT / "backend/fixtures/evals/golden.yaml").read_text(encoding="utf-8"))
    picked = [q for q in golden["questions"] if q["path"] != "engineering"][:2]
    subset = tmp_path / "golden.yaml"
    subset.write_text(yaml.safe_dump({"questions": picked}), encoding="utf-8")
    config = write_config(
        tmp_path, token_ceiling=200_000, golden_set=str(subset), report_dir=str(tmp_path / "reports")
    )
    report = run(load_settings(), config, "all").read_text(encoding="utf-8")
    assert "## Headline scores (held-out)" in report
    assert all(q["id"] in report for q in picked)
