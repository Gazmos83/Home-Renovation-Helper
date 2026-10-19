## Why

The course brief asks for "an AI evaluation report that proves the quality of your application using Ragas or DeepEval" (`docs/Task requirements.md`, Hard). Today the only measurement is `app/engineering/evaluate.py`, a hand-built ID-recall check on fixture blocks. Nothing scores the real corpus with a standard metric, and nothing scores an answer against the passages it was built from. The owner chose Ragas, its scope, dataset, judge and budget on 2026-10-19.

## What Changes

- **Golden set.** About 30 hand-written questions over the real corpus (toom catalogue, design guidelines, engineering sources such as the Wood Handbook). Each question has a reference answer, the passages that answer it (keyed by page URL and chunk position, or by engineering version and block, so the keys survive a re-ingest), the retrieval path it exercises (`catalog`, `guideline` or `engineering`), and a `dev` or `held_out` split. The file is checked in. Only the held-out split is reported, as in `evaluate.py`.
- **Retrieval metrics.** `search_knowledge` and `search_engineering` run on each question unchanged. The run scores Ragas `IDBasedContextRecall` and `IDBasedContextPrecision`, which need no model, and `LLMContextPrecisionWithReference` and `LLMContextRecall`, which use a judge.
- **Answer metrics (catalogue and guideline questions).** The Researcher's routed model and its instructions answer each question from the retrieved passages, wrapped the same way the agent tool wraps them. The run scores `Faithfulness`, `ResponseRelevancy` and `FactualCorrectness` against the reference. Engineering answers are written by code from the evidence the model cites, so they get retrieval metrics only.
- **Judge.** `anthropic/claude-haiku-4.5`, a registry slug, called through the existing OpenRouter gateway with its generation profile. Embeddings for `ResponseRelevancy` use the local `BAAI/bge-m3`. No new provider and no new credential are added.
- **Own token cap.** Each run has a token ceiling, set in an eval config file and enforced in code from the usage the gateway reports. The cap covers both the Researcher answers and the judge calls. When the next call would exceed it, the call is refused, the affected metrics are recorded as "not scored: budget", and the report says so. The eval does not use the agents' daily ceilings.
- **Remote-use boundary kept.** An engineering passage reaches the judge only if its rights permit remote model use. Other questions get the ID metrics only, and the report lists them.
- **Report.** `uv run python -m app.evals` writes `docs/evals/<date>.md`. It contains the score per metric and per path, a table per question, the judge slug, the token count, and the questions that were not scored with the reason. Scores go to Langfuse as numbers keyed by question ID, with no passage text. If Langfuse is down, the run logs that and continues.
- **Offline only.** The run reads the real corpus in `DATABASE_URL` inside a read-only transaction. The golden set refers to real passages, so a fixture test database like the one `evaluate.py` uses would not hold them. It is not part of the default pytest run and has no route or UI.
- **Not changed:** retrieval, ranking, thresholds, agents, prompts and routing.

**Ladder step:** none. **Agents:** none changed. The Researcher's retrieval and answer path is exercised read-only. **Render guard and bpy allow-list:** unaffected.

## Capabilities

### New Capabilities

- `rag-evaluation`: an offline Ragas evaluation of retrieval and answers over a hand-written golden set. It covers the judge through the gateway, a per-run token cap, the remote-use boundary for passages sent to the judge, and a dated report with scores pushed to Langfuse.

### Modified Capabilities

None.

## Impact

- **Backend:** new package `app/evals/` with the CLI, a dataset loader, the runner, the judge wrapper with the token cap, and the report writer. New `config/evals.yaml` for the judge slug, the token ceiling and the golden-set path. New golden set under `backend/fixtures/evals/`. Unit tests for the loader, the cap and the report. A live run is marked `slow`.
- **Dependencies:** `ragas` (0.4.3 resolves for Python 3.14 with prebuilt wheels only, checked 2026-10-19). Ragas pulls in `langchain-community`, `datasets` and others, so `uv add` must not move pinned versions in `uv.lock`. If it would, ask the owner before applying further.
- **Docs:** `docs/evals/` holds the dated reports, which are checked in because they are the course deliverable.
- **Cost:** about 30 questions × 6 metrics with a cheap judge, held under the per-run cap. About 1–2 developer days, plus the owner's time to write and check the golden set.
