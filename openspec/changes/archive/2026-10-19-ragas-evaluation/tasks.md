## 1. Dependency

- [x] 1.1 Run `uv add ragas==0.4.3` in `backend/`, then review the `uv.lock` diff. Verify that `langchain`, `langchain-openai`, `langgraph` and `langfuse` keep their major versions and that `uv run pytest -m "not slow"` still passes. If a major version would move, stop and ask the owner.

## 2. Golden set and config

- [x] 2.1 Add `config/evals.yaml` (judge slug, `token_ceiling`, golden-set path, report directory) and its loader. It refuses unknown keys, a non-positive ceiling and a judge slug outside the registry, naming the key or slug. Verify with unit tests for each refusal.
- [x] 2.2 Add `app/evals/golden.py`: Pydantic entries with `extra="forbid"` (`id`, `question`, `reference`, `expected` keys, `path` in `catalog|guideline|engineering`, `split` in `dev|held_out`), unique IDs, and a lookup of every expected key in a read-only session before any call. Verify with `db_session` tests that an unknown field, a duplicate ID and a missing key are each refused by name.
- [x] 2.3 Draft about 30 questions (guideline only by the owner's decision of 2026-10-19: the database holds no catalogue chunks, and no published engineering source grants remote model use; about a third `dev`) from real passages in the corpus into `backend/fixtures/evals/golden.yaml`. The owner then checks and corrects every reference answer and key. Verify that the loader accepts the file against the real database and that the owner has signed it off (`TODO(user)` until they do).

## 3. Runner

- [x] 3.1 Add the per-run token-cap callback (`app/evals/budget.py`). It refuses before a call when used + output cap > ceiling and adds the reported usage after each call. Verify with a fake chat model that it refuses the call that would cross the cap, counts usage from `usage_metadata`, and writes no `model_usage` rows.
- [x] 3.2 Add retrieval per path with the agent tools' arguments (`search_knowledge` with the tool's limit and categories; `search_engineering` with `remote=True`), mapped to passage keys. Verify with `fake_embedder` that the keys come back in the `url#chunk_index` and `version:block` forms and that an empty result yields zero ID recall.
- [x] 3.3 Add the one-shot Researcher answer. It uses the Researcher's routed model and the Foreman's system-prompt composition for that specialist, plus the tool-shaped passage message, with the budget callback attached and no Langfuse handler. Verify with a fake model that the prompt contains the delimiters and guard, and that no callback other than the budget is attached.
- [x] 3.4 Add sequential scoring: ID context recall and precision for every question; LLM context precision and recall for every question passing the remote-use check; faithfulness, response relevancy and factual correctness for `catalog` and `guideline` questions. Use the judge through `build_chat_model` and the local bge-m3 embeddings adapter. Verify with a fake judge that a `BudgetExhausted` refusal marks the remaining model metrics "not scored: budget" while ID metrics complete, and that a local-only engineering packet is downgraded to ID metrics with its reason.
- [x] 3.5 Run the database session as `SET TRANSACTION READ ONLY`. Verify with a test that a write attempted inside the eval session raises.

## 4. Report and Langfuse

- [x] 4.1 Add `app/evals/report.py`. It writes the headline (held-out) scores per metric and per path, a separate dev section, a per-question table, the judge, the embedding model, the split sizes, tokens against the ceiling, the unscored items with reasons and the note on engineering answer metrics. The name is `docs/evals/<date>.md`, then `-2` and so on. Verify with unit tests that a second run on the same date does not overwrite the first and that every section is present.
- [x] 4.2 Send scores to Langfuse: one run trace with metadata (judge, golden-set sha256), one numeric score per metric and question with only `question_id` in metadata. If Langfuse fails, log and continue. Verify with a fake client that no payload contains question, answer or passage text, and that a raising client still leaves the report written.
- [x] 4.3 Add the CLI `uv run python -m app.evals [--split held_out|all]`, plus a `live`-marked test that runs two golden questions end to end through the gateway. Verify `uv run pytest -m "not slow"` skips it and `uv run pytest --live -k evals` passes. `TODO(user)`: this needs the OpenRouter key and costs a few cents.

## 5. First report

- [x] 5.1 5.1 Run the full evaluation once and check `docs/evals/<date>.md` in. Hand-check 5 judged rows and record that check in the report. Verify the report exists, the token count is under the ceiling, and the scores appear in Langfuse. 2026-10-19: report written (787,776 of 1,500,000 tokens); 5 rows re-run with answers (`2026-10-19-2.md`) and the hand check confirmed by the owner. Langfuse is not configured on this host, so no scores were sent; the CLI says so. The owner declared the evaluation complete.
- [x] 5.2 5.2 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (alone, on the isolated test database), and verify both are clean. 2026-10-19: ruff clean; 3227 passed, 4 failed. The 4 failures (migration head `0031_blueprints`, approval wording, a hardware item) come from other uncommitted work and fail without this change too.
