## 1. Records

- [x] 1.1 Migration `0008_render_feedback` and models (`render_runs`, `render_feedback`). Verify upgrade and downgrade, and no autogenerate drift
- [x] 1.2 Write `app/feedback/runs.py` (record a run, set its outcome, latest succeeded run per key; failures logged, never raised) and wire it into the render tool (origin from `configurable` and the slot's model) and the renders route (no origin), with `run_render`'s new `on_outcome` callback. Verify `tests/test_render_runs.py` (fake launcher, tier `draft`) covers an agent-started run with thread, trace, prompt, slot and model; an HTTP-started run without them; outcome `succeeded` and `failed`; and a database error not stopping the render

## 2. Ratings

- [x] 2.1 Write `app/feedback/ratings.py` (upsert, clear, read, summary, comments) and `app/api/feedback.py` (homeowner renders list and rating routes, `/admin/feedback` and comments). Verify `tests/test_feedback_api.py` covers each spec scenario: rate, re-rate, clear, re-render unrated, nothing rendered → 409, comment over 1 000 refused, 401 without the cookie, admin 404 when the panel is disabled, and no slot, model or prompt in any homeowner response
- [x] 2.2 Add `Tracing.record_feedback`. Verify `tests/test_langfuse_tracing.py` (fake client) covers a score on the run's trace with value and comment; the feedback span's tags (`render-feedback`, `rating:down`, `tier:draft`, `slot:builder`, `model:<slug>`); no score without a trace id; and tracing off or raising leaving the rating stored

## 3. Agents

- [x] 3.1 Create `plugins/render_feedback/` with `record_render_feedback` (confirmation, bound package from the conversation, default target the latest succeeded run), add the manifest's optional `also_for`, and name the tool in `builder.md` and `lighting.md`. Verify `tests/test_record_render_feedback.py` covers the `yes`/`no` paths, the default target, a named render key and version, a refusal when nothing is rendered, and a model-supplied package id ignored, and `tests/test_plugin_manifest.py` and `tests/test_instructions.py` cover `also_for` accepted, refused when it repeats or names the role, and a stranger agent naming the tool refused
- [x] 3.2 Add the "Recent render feedback" lines to the house note for the Designer and Lighting. Verify `tests/test_prompts.py` covers five newest lines on the bound piece, delimiter neutralisation, and that Intake gets none

## 4. Studio

- [x] 4.1 Add `frontend/src/routes/Pieces.tsx` (+ navigation link) with Vitest coverage: rate up/down, comment saved, clear, refusal shown beside the render, legacy render without a run labelled, and no model text rendered. Verify `pnpm test` and `pnpm lint` pass
- [x] 4.2 Add `frontend/src/routes/admin/Feedback.tsx` (+ admin route) with Vitest coverage of the grouped table and the comment list. Verify `pnpm test` passes
- [ ] 4.3 Browser check of both pages against a running backend with one fixture piece rendered at tier `draft` (rate, reload, clear; read the summary). Record the check in the commit message

## 5. Verification

- [x] 5.1 README (rating renders, where the developer reads feedback) and CLAUDE.md §11 step 9 tick
- [x] 5.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, `uv run pytest --blender -m blender` (renders at tier `draft` only), and `pnpm lint && pnpm test && pnpm build`. Verify all pass and record the counts in the commit message
