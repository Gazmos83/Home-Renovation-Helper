"""`uv run python -m app.evals [--split held_out|all]`: one evaluation run, one report.

Reads the real corpus in `DATABASE_URL` inside read-only transactions. Every model
call goes through the gateway and is metered against the run's own ceiling.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.agent.instructions import load_instructions
from app.agent.models.openrouter_client import (
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    build_chat_model,
)
from app.agent.models.profiles import Profiles, output_token_limit
from app.agent.models.routing import load_routing, read_routing_overrides
from app.config import REPO_ROOT, ConfigurationError, Settings, load_settings
from app.db.session import make_engine
from app.embedding import MODEL_NAME
from app.evals.budget import RunBudget
from app.evals.config import DEFAULT_EVAL_CONFIG, load_eval_config
from app.evals.golden import GoldenSetError, check_keys, load_golden
from app.evals.report import RunSummary, send_scores, write_report
from app.evals.run import (
    LocalEmbeddings,
    RunState,
    answer,
    answer_messages,
    judge_finished,
    ragas_metrics,
    read_only_session,
    researcher_system,
    retrieve,
    score_question,
)


def _model(settings: Settings, profiles: Profiles, slug: str, budget: RunBudget):
    kwargs = profiles.profile_for(slug).model_kwargs(slug)
    meter = budget.meter(kwargs.get("max_tokens") or output_token_limit(slug))
    # The meter only: no UsageRecorder (agent budgets stay untouched) and no
    # Langfuse handler (it would export prompts holding passage text).
    return build_chat_model(settings, model_id=slug, callbacks=[meter], **kwargs)


def run(settings: Settings, config_path: Path, split: str, only: list[str] | None = None) -> Path:
    config = load_eval_config(config_path)
    engine = make_engine(settings.database_url)
    routing = load_routing(overrides=read_routing_overrides(engine))
    profiles = Profiles(engine)
    instruction = load_instructions()["researcher"]
    researcher_slug = routing.model_for(instruction.slot)
    entries = load_golden(config.golden_set)
    if split == "held_out":
        entries = [entry for entry in entries if entry.split == "held_out"]
    if only:
        unknown = sorted(set(only) - {entry.id for entry in entries})
        if unknown:
            raise GoldenSetError(f"--only names questions not in the set: {', '.join(unknown)}")
        entries = [entry for entry in entries if entry.id in only]

    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.run_config import RunConfig

    budget = RunBudget(config.token_ceiling)
    researcher = _model(settings, profiles, researcher_slug, budget)
    judge = LangchainLLMWrapper(
        _model(settings, profiles, config.judge, budget),
        run_config=RunConfig(timeout=int(REQUEST_TIMEOUT_SECONDS), max_retries=MAX_RETRIES),
        # Keep the judge's own profile and ask for one completion per request.
        bypass_temperature=True,
        bypass_n=True,
        is_finished_parser=judge_finished,
    )
    metrics = ragas_metrics(judge, LangchainEmbeddingsWrapper(LocalEmbeddings()))
    system = researcher_system(instruction.text)
    state = RunState(judge=config.judge)

    async def score_all(session):
        results = []
        for entry in entries:
            retrieved = retrieve(session, entry)
            messages = answer_messages(system, entry, retrieved) if entry.path != "engineering" else []
            results.append(
                await score_question(entry, retrieved, lambda messages=messages: answer(researcher, messages), metrics, state)
            )
        return results

    with read_only_session(engine) as session:
        check_keys(session, entries)
        results = asyncio.run(score_all(session))

    started = datetime.now(UTC)
    summary = RunSummary(
        run_id=started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        results=results,
        judge=config.judge,
        researcher=researcher_slug,
        embedding_model=MODEL_NAME,
        golden_set=str(
            config.golden_set.relative_to(REPO_ROOT) if config.golden_set.is_relative_to(REPO_ROOT) else config.golden_set
        ),
        golden_sha256=hashlib.sha256(config.golden_set.read_bytes()).hexdigest(),
        tokens_used=budget.used,
        token_ceiling=config.token_ceiling,
        split_mode=split,
    )
    path = write_report(config.report_dir, summary, started.date())
    if settings.tracing_enabled:
        from app.observability.langfuse import _build

        client, _handler = _build(settings)
        send_scores(client, summary)
    else:
        print("Langfuse is not configured (LANGFUSE_HOST and keys); scores were not sent", file=sys.stderr)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.evals", description=__doc__)
    parser.add_argument("--split", choices=("held_out", "all"), default="all")
    parser.add_argument("--config", type=Path, default=DEFAULT_EVAL_CONFIG)
    parser.add_argument("--only", help="comma-separated question ids, for a re-run of chosen rows")
    args = parser.parse_args(argv)
    try:
        path = run(load_settings(), args.config, args.split, args.only.split(",") if args.only else None)
    except (ConfigurationError, GoldenSetError) as error:
        print(f"evaluation stopped: {error}", file=sys.stderr)
        return 2
    print(f"report written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
