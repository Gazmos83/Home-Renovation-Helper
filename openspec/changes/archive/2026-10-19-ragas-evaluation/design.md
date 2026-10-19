## Context

See proposal.md (Why) and `specs/rag-evaluation/spec.md`. Current state:

- **Catalogue and guideline retrieval** is `search_knowledge` (`app/retrieval.py:36`).
  - The tools call it with `limit=5` and `categories=CATALOG_CATEGORIES` (`plugins/catalog_research/tool.py:103`) or `categories=["guideline"]` (`plugins/guidelines/tool.py`).
  - Hits are `SearchHit` rows from `chunks`.
  - The serial `id` is lost when a page is deleted or shrinks. `(url, chunk_index)` survives an upsert.
- **Engineering retrieval** is `search_engineering(session, SearchIn, remote=True)`.
  - Packets carry `evidence_id = "<version_id>:<block_id>"`.
  - Chunk UUIDs are recreated on every publish.
- **No function maps a question to an answer and its contexts** short of the full Foreman graph (`app/agent/chat.py:425`).
  - The Researcher is one bound-tools `invoke` inside `specialist_graph` (`app/agent/foreman.py:1292`). Its instructions are in `app/agent/instructions/researcher.md`.
  - Tool results are `DATED_NOTE`/`CITE_NOTE` + `wrap_passages([Passage.from_hit(h) …])`.
- **Engineering answers** go through `render_answer` (`app/engineering/chat.py:425`). The model only picks IDs, and code writes the text.
- **Models** are built with `build_chat_model(settings, model_id=…, **profile kwargs)` (`app/agent/models/openrouter_client.py:137`).
  - Wrap calls in `gateway_errors(operation=…)`.
  - Usage is read by `_token_counts` (`app/observability/usage.py:82`), or from `AIMessage.usage_metadata`.
  - Langfuse is attached per call through the run config, not when the model is built.
- **`evaluate.py`** is the house pattern: an argparse CLI, a dev/held-out split chosen in the fixture, and a report of the held-out split only. It works on fixture writes in a test database, rolled back.
- **pytest:** `live` tests are auto-skipped unless `--live` (`conftest.py:232`).

## Goals / Non-Goals

**Goals:**
- One command produces a defensible, dated report from the real corpus and the real retrieval and answer path.
- Every model call goes through the existing gateway and is metered against a per-run cap.
- No passage text leaves for Langfuse.

**Non-Goals:**
- Changing or tuning retrieval from the results. Any tuning is a later OpenSpec change.
- Agent tool-call or goal metrics.
- Running in CI or the default test suite.
- A UI or `/admin` page.
- Generating a test set synthetically.

## Decisions

1. **Score sample by sample, one call at a time; do not use `ragas.evaluate()`.**
   - Loop over questions and metrics with `await metric.single_turn_ascore(SingleTurnSample(...))`.
   - This makes the budget refusal exact: we know which question and metric ran out. It keeps the run to one call at a time, which the laptop and the cap prefer.
   - About 30 × 7 calls is small.
   - *Alternative:* `evaluate()` with `RunConfig(max_workers=1)`. It hides per-row failures as NaN, and we could not tell a budget refusal from a judge error.

2. **Judge LLM: `LangchainLLMWrapper(build_chat_model(...))`; embeddings: `LangchainEmbeddingsWrapper` over a tiny `Embeddings` adapter around `app.embedding.embed`/`embed_one`.**
   - This reuses provider routing, the explicit credential, timeouts and the slug's generation profile.
   - *Alternative:* Ragas 0.4's `llm_factory` with a raw `AsyncOpenAI` client. That would duplicate the gateway setup and skip `PROVIDER_ROUTING` (llm-gateway requirement: providers must support the parameters).
   - Pin `ragas==0.4.3`, because the wrapper path is the older API.

3. **Token cap as a LangChain callback with `raise_error=True`, attached to both eval models (Researcher and judge).**
   - `on_chat_model_start` refuses the call when `used + max_tokens > ceiling`, by raising `BudgetExhausted`.
   - `on_llm_end` adds the response usage with `_token_counts`.
   - The runner catches `BudgetExhausted` per call and records "not scored: budget". After the first refusal, later model calls are skipped without being attempted, while ID metrics continue.
   - *Alternative:* the app's `RequestBudget`. It counts an estimate against the agents' daily ceilings, and the owner chose a separate cap.
   - `UsageRecorder` is deliberately not attached, so `model_usage` and the agents' daily totals stay untouched.

4. **Researcher answer step = one model call, no tool loop.**
   - System: the Researcher's instructions, composed by the same function the Foreman uses for that specialist, including the code-composed guard.
   - Human: the question.
   - Then one tool-result-shaped message holding exactly the string the tool would return for those hits (the same note + `wrap_passages`).
   - Ragas `retrieved_contexts` = the passage texts in that string.
   - *Alternative:* bind the real tools and loop. The model might search again with different words, so the retrieval being scored would no longer be the retrieval that was measured. The owner asked for the RAG answer quality, not for routing.

5. **Passage keys: `"<url>#<chunk_index>"` for catalogue and guideline passages, `"<version_id>:<block_id>"` for engineering.**
   - They are used both as Ragas `reference_context_ids` and as the retrieved IDs.
   - Validation looks each key up before any call and refuses missing ones (spec: stale passage).

6. **Read-only on the real database.**
   - `make_engine(settings.database_url)`, one session, `SET TRANSACTION READ ONLY` as the first statement, and rollback at the end.
   - The database enforces that nothing is written.
   - This departs from `evaluate.py`'s test database on purpose: the golden set refers to real passages.

7. **Remote-use boundary.**
   - Engineering retrieval runs with `remote=True`, as the tool does, so retrieved evidence is already limited to remote-permitted blocks.
   - The runner still checks every engineering packet's rights flag before a judge call and downgrades the question to ID metrics if one fails. This defends against future changes.
   - Passages are passed to Ragas inside the same untrusted-content delimiters the agents see.

8. **Langfuse: scores only, from a dedicated client call; no callback on eval models.**
   - Attaching the LangChain handler would export prompts that contain passage text, so it is not attached.
   - After scoring, the runner creates one trace per run, named `ragas-eval <run_id>`, with metadata `{judge, golden_set_sha256}` only.
   - It sends `create_score(name="ragas.<metric>", value=…, trace_id=…, metadata={"question_id": …})`. A failure logs a warning and continues.

9. **Layout.**
   - `app/evals/`: `__main__.py` (CLI: `--set`, `--config`, `--split all|held_out`), `golden.py` (Pydantic models with `extra="forbid"`, plus the loader and key check), `budget.py` (callback), `run.py` (retrieve, answer, score), `report.py` (Markdown).
   - `config/evals.yaml`: `judge: anthropic/claude-haiku-4.5`, `token_ceiling`, `golden_set: backend/fixtures/evals/golden.yaml`, `report_dir: docs/evals`.
   - Report name: `docs/evals/YYYY-MM-DD.md`, then `-2`, `-3` and so on, never overwriting an earlier report.

## Risks / Trade-offs

- **Ragas's transitive dependencies may move pins in `uv.lock`** (langchain-community, datasets) → `uv add ragas==0.4.3` in apply, then review the lock diff before anything else. Stop and ask the owner if `langchain`/`langchain-openai`/`langgraph` would change major versions.
- **Haiku judges small, mixed German/English catalogue passages** → judge prompts stay Ragas defaults. Spot-check 5 judged rows by hand in the first report and record the result in it.
- **The golden set ties the eval to today's corpus** → stale keys fail loudly before any cost. Re-keying is a manual edit.
- **A one-shot Researcher answer differs from a full conversation** (no house-file slice, no Foreman) → the report states exactly what was measured.
- **`ResponseRelevancy` generates its questions with the judge and embeds them locally** → bge-m3 is already loaded by retrieval, so there is no new model, at the cost of extra CPU time per question.
- **Sequential scoring is slow** (minutes) → acceptable for an offline report.

## Migration Plan

- There is no schema migration and no runtime change. Roll back by removing `app/evals/`, `config/evals.yaml` and the dependency.
