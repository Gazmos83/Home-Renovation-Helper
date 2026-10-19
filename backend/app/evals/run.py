"""Retrieve, answer and score each golden question, one call at a time.

Retrieval is called with the agent tools' own arguments, and the Researcher sees
exactly the text its tool would return. Scores come from Ragas metrics called
sample by sample (`single_turn_ascore`), so a budget refusal is known per
question and metric; `ragas.evaluate()` would hide it as NaN.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Final
from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.agent.foreman import ROLE_NOTE, SPECIALIST_LABELS
from app.agent.models.openrouter_client import GatewayError, gateway_errors
from app.agent.prompts import (
    CLOSE_TOKEN,
    FORMATTING_NOTE,
    OPEN_PREFIX,
    compose_agent_prompt,
)
from app.config import ConfigurationError
from app.embedding import embed, embed_one
from app.engineering.chat import wrapped_packet
from app.engineering.registry import current_rights, permits
from app.engineering.retrieval import search_engineering
from app.engineering.schemas import Scope, SearchIn
from app.evals.budget import BudgetExhausted
from app.evals.golden import GoldenEntry
from app.retrieval import search_knowledge
from plugins.catalog_research.tool import CATALOG_CATEGORIES
from plugins.catalog_research.tool import search_result as catalog_result
from plugins.guidelines.tool import search_result as guideline_result

ID_METRICS: Final = ("id_based_context_recall", "id_based_context_precision")
CONTEXT_METRICS: Final = ("llm_context_precision_with_reference", "context_recall")
ANSWER_METRICS: Final = ("faithfulness", "answer_relevancy", "factual_correctness")
ALL_METRICS: Final = ID_METRICS + CONTEXT_METRICS + ANSWER_METRICS

BUDGET: Final = "budget"
# A gateway that refuses the slug itself is a configuration error: the run stops.
_FATAL_GATEWAY: Final = {"unauthorized", "forbidden", "refused"}
_WRAPPED: Final = re.compile(re.escape(OPEN_PREFIX) + r".*?" + re.escape(CLOSE_TOKEN), re.DOTALL)
logger = logging.getLogger("app")
_TOOL_NAMES: Final = {"catalog": "search_catalog_knowledge", "guideline": "search_guidelines"}


@contextmanager
def read_only_session(engine: Engine) -> Iterator[Session]:
    """A session whose every transaction is read-only, so the database refuses any write."""
    with Session(engine) as session:
        event.listen(
            session,
            "after_begin",
            lambda _session, _transaction, connection: connection.exec_driver_sql("SET TRANSACTION READ ONLY"),
        )
        try:
            yield session
        finally:
            session.rollback()


@dataclass(frozen=True)
class Retrieved:
    ids: list[str]
    contexts: list[str]  # each wrapped in the untrusted-content delimiters
    tool_text: str
    local_only: list[str] = field(default_factory=list)  # evidence without remote-use rights


def retrieve(session: Session, entry: GoldenEntry) -> Retrieved:
    """The question's path, with the arguments its agent tool uses."""
    if entry.path == "engineering":
        result = search_engineering(session, SearchIn(query=entry.question), remote=True)
        packets = result["evidence"]
        local_only = [
            packet["evidence_id"]
            for packet in packets
            if not permits(
                current_rights(session, UUID(packet["version_id"])),
                Scope.REMOTE,
                block_id=packet["block_id"],
                pages=packet["block"].get("pages"),
            )
        ]
        contexts = [wrapped_packet(packet) for packet in packets]
        return Retrieved(
            ids=[packet["evidence_id"] for packet in packets],
            contexts=contexts,
            tool_text="\n\n".join(contexts),
            local_only=local_only,
        )
    if entry.path == "catalog":
        hits = search_knowledge(session, entry.question, limit=5, categories=CATALOG_CATEGORIES)
        text = catalog_result(hits)
    else:
        hits = search_knowledge(session, entry.question.strip(), limit=5, categories=["guideline"])
        text = guideline_result(hits)
    return Retrieved(
        ids=[f"{hit.url}#{hit.chunk_index}" for hit in hits],
        contexts=_WRAPPED.findall(text),
        tool_text=text,
    )


def researcher_system(instruction_text: str) -> str:
    """The Researcher's system prompt as the Foreman composes it on a turn with no house slice."""
    return compose_agent_prompt(
        instruction_text,
        ROLE_NOTE.format(role=SPECIALIST_LABELS["researcher"]),
        FORMATTING_NOTE,
    )


def answer_messages(system: str, entry: GoldenEntry, retrieved: Retrieved) -> list[BaseMessage]:
    """System, question, the tool call and its result: one call, no tool loop."""
    call_id = f"eval-{entry.id}"
    return [
        SystemMessage(system),
        HumanMessage(entry.question),
        AIMessage(
            "",
            tool_calls=[{"name": _TOOL_NAMES[entry.path], "args": {"query": entry.question}, "id": call_id}],
        ),
        ToolMessage(retrieved.tool_text, tool_call_id=call_id),
    ]


def answer(model: Any, messages: list[BaseMessage]) -> str:
    with gateway_errors(operation="evals.researcher"):
        return model.invoke(messages).text


def judge_finished(response: Any) -> bool:
    """Ragas's finish check, logging the reason when a judge reply did not end with "stop"."""
    reasons = []
    for batch in response.generations:
        for generation in batch:
            info = generation.generation_info or {}
            message = getattr(generation, "message", None)
            reasons.append(info.get("finish_reason") or (message.response_metadata.get("finish_reason") if message else None))
    finished = all(reason in (None, "stop") for reason in reasons)
    if not finished:
        logger.warning("judge reply did not finish", extra={"context": {"finish_reasons": reasons}})
    return finished


class LocalEmbeddings(Embeddings):
    """The application's own bge-m3 embeddings, for `ResponseRelevancy`."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return embed_one(text)


@dataclass
class QuestionResult:
    entry: GoldenEntry
    scores: dict[str, float] = field(default_factory=dict)
    unscored: dict[str, str] = field(default_factory=dict)
    note: str | None = None
    answer: str | None = None  # the Researcher's reply, kept for the report's hand check


@dataclass
class RunState:
    judge: str
    exhausted: bool = False


async def _score(
    name: str, metric: Any, sample: Any, result: QuestionResult, state: RunState, *, model: bool
) -> None:
    if model and state.exhausted:
        result.unscored[name] = BUDGET
        return
    from ragas.exceptions import LLMDidNotFinishException, RagasOutputParserException

    try:
        with gateway_errors(operation=f"evals.{name}"):
            value = await metric.single_turn_ascore(sample)
    except BudgetExhausted:
        state.exhausted = True
        result.unscored[name] = BUDGET
        return
    except GatewayError as error:
        if error.error_class in _FATAL_GATEWAY:
            raise ConfigurationError(f"eval judge {state.judge} blocked by gateway: {error.reason}") from error
        result.unscored[name] = f"gateway: {error.error_class}"
        return
    except LLMDidNotFinishException:
        # The judge's reply was cut off (finish reason other than "stop"); one metric, not the run.
        result.unscored[name] = "judge did not finish"
        return
    except RagasOutputParserException:
        result.unscored[name] = "judge reply unreadable"
        return
    if value is None or math.isnan(value):
        result.unscored[name] = "no value"
        return
    result.scores[name] = float(value)


async def score_question(
    entry: GoldenEntry,
    retrieved: Retrieved,
    respond: Callable[[], str],
    metrics: Mapping[str, Any],
    state: RunState,
) -> QuestionResult:
    """Every metric that applies to this question, in order; ID metrics always run."""
    from ragas import SingleTurnSample

    result = QuestionResult(entry)
    ids = SingleTurnSample(retrieved_context_ids=retrieved.ids, reference_context_ids=entry.expected)
    for name in ID_METRICS:
        await _score(name, metrics[name], ids, result, state, model=False)

    model_metrics = CONTEXT_METRICS + (ANSWER_METRICS if entry.path != "engineering" else ())
    if retrieved.local_only:
        result.note = "ID metrics only: remote-use rights (" + ", ".join(retrieved.local_only) + ")"
        for name in model_metrics:
            result.unscored[name] = "remote-use rights"
        return result

    contexts = SingleTurnSample(
        user_input=entry.question, reference=entry.reference, retrieved_contexts=retrieved.contexts
    )
    for name in CONTEXT_METRICS:
        if not retrieved.contexts:
            result.unscored[name] = "nothing retrieved"
        else:
            await _score(name, metrics[name], contexts, result, state, model=True)

    if entry.path == "engineering":
        return result
    response = None
    if not state.exhausted:
        try:
            response = respond()
            result.answer = response
        except BudgetExhausted:
            state.exhausted = True
        except GatewayError as error:
            if error.error_class in _FATAL_GATEWAY:
                raise ConfigurationError(f"Researcher model blocked by gateway: {error.reason}") from error
            for name in ANSWER_METRICS:
                result.unscored[name] = f"answer failed: {error.error_class}"
            return result
    if response is None:
        for name in ANSWER_METRICS:
            result.unscored[name] = BUDGET
        return result
    answered = SingleTurnSample(
        user_input=entry.question,
        response=response,
        reference=entry.reference,
        retrieved_contexts=retrieved.contexts,
    )
    for name in ANSWER_METRICS:
        await _score(name, metrics[name], answered, result, state, model=True)
    return result


def ragas_metrics(judge_llm: Any, embeddings: Any) -> dict[str, Any]:
    """The seven Ragas metrics, keyed by their Ragas names, with the gateway judge."""
    from ragas.metrics import (
        FactualCorrectness,
        Faithfulness,
        IDBasedContextPrecision,
        IDBasedContextRecall,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    metrics = [
        IDBasedContextRecall(),
        IDBasedContextPrecision(),
        LLMContextPrecisionWithReference(llm=judge_llm),
        LLMContextRecall(llm=judge_llm),
        Faithfulness(llm=judge_llm),
        ResponseRelevancy(llm=judge_llm, embeddings=embeddings),
        FactualCorrectness(llm=judge_llm),
    ]
    by_name = {metric.name: metric for metric in metrics}
    assert set(by_name) == set(ALL_METRICS), sorted(by_name)
    return by_name
