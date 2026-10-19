"""The dated Markdown report, and the score-only Langfuse trace.

The report never overwrites an earlier one. Langfuse gets numbers keyed by run
and question ID, never question, answer or passage text.
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

from app.evals.run import ALL_METRICS, QuestionResult

logger = logging.getLogger("app")

PATHS: Final = ("catalog", "guideline", "engineering")


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    results: list[QuestionResult]
    judge: str
    researcher: str
    embedding_model: str
    golden_set: str
    golden_sha256: str
    tokens_used: int
    token_ceiling: int
    split_mode: str  # "held_out" or "all"


def _mean(results: Sequence[QuestionResult], metric: str) -> str:
    values = [result.scores[metric] for result in results if metric in result.scores]
    return f"{statistics.fmean(values):.3f} (n={len(values)})" if values else "—"


def _score_table(results: Sequence[QuestionResult]) -> list[str]:
    columns = [*PATHS, "all"]
    lines = ["| Metric | " + " | ".join(columns) + " |", "|---" * (len(columns) + 1) + "|"]
    for metric in ALL_METRICS:
        cells = [_mean([r for r in results if r.entry.path == path], metric) for path in PATHS]
        cells.append(_mean(results, metric))
        lines.append(f"| {metric} | " + " | ".join(cells) + " |")
    return lines


def _cell(result: QuestionResult, metric: str) -> str:
    if metric in result.scores:
        return f"{result.scores[metric]:.2f}"
    return "n/s" if metric in result.unscored else "—"


def render(summary: RunSummary) -> str:
    held_out = [r for r in summary.results if r.entry.split == "held_out"]
    dev = [r for r in summary.results if r.entry.split == "dev"]
    lines = [
        f"# Ragas evaluation, run {summary.run_id}",
        "",
        "## Run",
        "",
        f"- Judge: `{summary.judge}` (through the OpenRouter gateway, its own generation profile)",
        f"- Researcher model: `{summary.researcher}`",
        f"- Embedding model: `{summary.embedding_model}` (local)",
        f"- Golden set: `{summary.golden_set}`, sha256 `{summary.golden_sha256}`",
        f"- Questions: {len(held_out)} held-out, {len(dev)} dev"
        + ("" if summary.split_mode == "all" else " (dev not run)"),
        "- Per path: " + ", ".join(
            f"{path} {sum(r.entry.path == path for r in summary.results)}" for path in PATHS
        ),
        f"- Tokens: {summary.tokens_used} of the run's ceiling of {summary.token_ceiling}",
        "",
        "## What was measured",
        "",
        (
            "Retrieval is the application's own (`search_knowledge` with the catalogue and guideline "
            "tools' limit and categories, `search_engineering` with the remote-use boundary). Answers "
            "are one Researcher call with its routed model and its Foreman-composed instructions, "
            "given the tool's own result text; there is no house-file slice and no tool loop. "
            "Engineering answers are written by code from cited evidence, so engineering questions "
            "get retrieval metrics only."
        ),
        "",
        "## Headline scores (held-out)",
        "",
        *_score_table(held_out),
        "",
        "## Dev split (used for tuning, not part of the headline)",
        "",
        *(_score_table(dev) if dev else ["Not run."]),
        "",
        "## Per question",
        "",
        "| Question | Split | Path | " + " | ".join(ALL_METRICS) + " |",
        "|---" * (len(ALL_METRICS) + 3) + "|",
        *(
            f"| {r.entry.id} | {r.entry.split} | {r.entry.path} | "
            + " | ".join(_cell(r, metric) for metric in ALL_METRICS)
            + " |"
            for r in summary.results
        ),
        "",
        "— does not apply; n/s not scored (see below).",
        "",
        "## Not scored",
        "",
    ]
    unscored = [
        f"- {r.entry.id}: {metric}: {reason}" for r in summary.results for metric, reason in r.unscored.items()
    ]
    notes = [f"- {r.entry.id}: {r.note}" for r in summary.results if r.note]
    lines.extend(notes + unscored or ["Every applicable metric was scored."])
    answered = [r for r in summary.results if r.answer is not None]
    if answered:
        lines.extend(["", "## Answers", "", "The Researcher's reply for each question, as the judge scored it.", ""])
        for r in answered:
            lines.extend([f"### {r.entry.id}", "", f"Reference: {r.entry.reference}", "", "Answer:", ""])
            lines.extend(f"> {line}" if line else ">" for line in r.answer.splitlines())
            lines.append("")
    lines.extend(["", "## Hand check", "", "TODO(user): five judged rows checked by hand.", ""])
    return "\n".join(lines)


def write_report(report_dir: Path, summary: RunSummary, today: date) -> Path:
    """`<date>.md`, else `<date>-2.md` and so on; never overwrites an earlier report."""
    report_dir.mkdir(parents=True, exist_ok=True)
    text = render(summary)
    attempt = 1
    while True:
        path = report_dir / (f"{today.isoformat()}.md" if attempt == 1 else f"{today.isoformat()}-{attempt}.md")
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(text)
            return path
        except FileExistsError:
            attempt += 1


def send_scores(client: Any, summary: RunSummary) -> bool:
    """One trace per run and one numeric score per question and metric. A failure logs and returns False."""
    try:
        with client.start_as_current_observation(
            name=f"ragas-eval {summary.run_id}",
            metadata={"judge": summary.judge, "golden_set_sha256": summary.golden_sha256},
        ) as span:
            trace_id = span.trace_id
        for result in summary.results:
            for metric, value in result.scores.items():
                client.create_score(
                    name=f"ragas.{metric}",
                    value=value,
                    data_type="NUMERIC",
                    trace_id=trace_id,
                    metadata={"question_id": result.entry.id},
                )
        client.flush()
    except Exception as error:  # noqa: BLE001 - the report must not depend on tracing
        logger.warning(
            "ragas scores were not sent to Langfuse",
            extra={"context": {"error_type": type(error).__name__}},
        )
        return False
    return True
