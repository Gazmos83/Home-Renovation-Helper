## 1. Storage

- [x] 1.1 Add the `VersionVerdict` model and the nullable `slot` and `model` columns on `PieceVersion`, with Alembic `0027_version_verdicts` (design decisions 1 and 2). Verify with `uv run alembic upgrade head`, then `downgrade -1` and `upgrade head` again, and a model test: a `mismatch` row without a note is refused by the check constraint, and deleting the version removes its verdict.
- [x] 1.2 Give `house_file.record_version` optional `slot` and `model`, and pass `ctx.slot` and `ctx.model` from `create_piece` and `revise_package.record_next` (design decision 2). Verify with `test_revise.py` and `test_create_piece` cases: a version made in a Designer turn records slot `designer` and its model, and a version recorded without them stores none. Also check that homeowner version routes do not return the two fields (`test_packages`).

## 2. Domain

- [x] 2.1 Write `app/feedback/verdicts.py` with `give`, `clear`, `set_status`, `current`, `open_for_piece`, `summary` and `notes` (design decision 3). Verify with a new `tests/test_version_verdicts.py` covering the version-verdict scenarios: blockout marked wrong (stored, open), mismatch without a note refused, changed mind (one `matches` verdict), unknown version refused naming it, resolved leaves the open list, approval not blocked and the verdict stays open, version deleted removes the verdict, note over 1 000 characters refused, and note neutralised.
- [x] 2.2 Add `summary` and `notes` grouping by the version's slot and model, with no slot or model grouped as none. Verify in `test_version_verdicts.py`: two Designer mismatches and one matches give 1 / 2, and an origin-less version counts under none.

## 3. Routes and tracing

- [x] 3.1 Add the owner routes `GET/PUT/DELETE /api/packages/{id}/versions/{n}/verdict` and `PATCH .../verdict/status`, and the gated admin `verdicts` and `verdicts/notes` routes (design decision 4). Verify with API tests: no session gives 401, a disabled developer panel gives 404 on admin routes, and a refusal returns its reason and status.
- [x] 3.2 Add `tracing.record_verdict` and call it after a stored or changed verdict (design decision 7). Verify with tests: tags `version-verdict`, `verdict:mismatch`, the slot and the model; an unreachable tracer still stores the verdict with no error to the owner; nothing is sent with tracing off.

## 4. Agents

- [x] 4.1 Create the plugin `plugins/version_verdict/` (manifest role `designer`, toggleable, on by default) with `record_version_verdict` using `preview` → `Confirmation` and `run` gated on `ctx.approved` (design decision 5). Verify with plugin tests: "v4 is wrong, the side drawers are missing" gives a proposal naming version 4 and the note, nothing is stored before yes, `no` stores nothing, no bound piece is refused with a question, the latest version is used when none is named, and the manifest loads at startup.
- [x] 4.2 Add `include_version_verdicts` to `MemorySettings` and the open-verdicts block to the slice in `foreman.py` and `prompts.py` (design decision 6). Verify with `test_memory_settings.py` (default on, reset) and Foreman or prompt tests from the house-file delta: the Designer's context lists v4's note labelled version 4 in the house-file block, neutralised, a resolved verdict is not listed, another piece's verdict is not listed, and the setting off lists none.
- [x] 4.3 Mention the verdict tool and the open-verdicts block in `app/agent/instructions/designer.md` (propose a verdict only when the owner says a version is right or wrong; treat open verdicts as things not to repeat). Verify with `test_instructions.py`.
  Also added one Foreman routing rule: the owner stating a version is right or wrong goes to the Designer, a reaction to a render's look to the Builder. Without it the Designer's tool could not be reached from chat.

## 5. Frontend

- [x] 5.1 Add the API functions and types in `lib/api.ts`, and a `VersionVerdict` component above the tabs in `InspectorView` (design decision 8). Verify with Vitest from the studio-ui delta: no verdict shows the question and both buttons; "Doesn't match" with an empty note does not save; a saved mismatch shows its note and "open", with resolve and dismiss; resolved hides those controls; switching versions shows that version's verdict; and no model, token or cost text appears.
- [x] 5.2 Add the verdict table and notes list to `routes/admin/Feedback.tsx`, and the "Open version verdicts" toggle to `routes/admin/Memory.tsx`. Verify with `Feedback.test.tsx` (counts per slot and model, notes newest first, a no-slot row) and `Memory.test.tsx` (toggle saves and resets).

## 6. Checks

- [x] 6.1 Browser check: open `amesbury-wardrobe` v4 in the inspector, mark it "Doesn't match" with a note, reload and confirm it is kept; open the developer Feedback page and see v4 under no slot or model. No render is started.
  Browser pass 2026-10-16: headless Chrome through Python Playwright (`uv run --no-project --with playwright`), scratch database `home_renovation_verdict_ui` (dropped afterwards), a copy of `amesbury-wardrobe` v1–v4 in a scratch render root, backend on 8100 with tracing off and Vite on 5180 (`API_PROXY`); the owner's 8000 and 5173 were untouched. No build, render or model call. All 9 checks passed: (1) v4 with no verdict asks "Does this match what you confirmed?" with both buttons; (2) "Doesn't match" with an empty note is refused in place; (3) a saved mismatch shows its note and "open", above the Model / Cut list / Renders tabs; (4) it is kept after a reload; (5) no model, token or cost text in the section; (6) v3 shows its own, empty verdict; (7) "Mark resolved" shows resolved and removes resolve and dismiss; (8) the developer Feedback page counts v4 under no agent / no model and lists its note; (9) clearing returns to the question. The note was a labelled test note, not the owner's.
- [x] 6.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"` (RunPod and offload test files excluded) and `pnpm test`, `pnpm lint` and `pnpm build`. Verify that all pass, and record any failure that belongs to another change.
  Run 2026-10-16: `ruff check .` clean; `pytest -m "not slow"` (RunPod and offload files excluded) 2660 passed, 43 skipped, 2 failed: `test_foreman.py` and `test_tool_toggles.py` list the Designer's exact bound tools and now also name `record_version_verdict`; both files then passed (64). `test_engineering_registry.py` pins the head migration and now names `0027_version_verdicts`. `pnpm test` 476 passed; `pnpm lint` and `pnpm build` clean.
- [x] 6.3 Owner check: in the Amesbury Wardrobe conversation, tell the chat what is wrong with v4 (e.g. "v4 is wrong, …"), answer yes to the proposed verdict, then ask for a revision and confirm the reply addresses the note. This needs the owner's own note and real model calls, so it is left to the owner; the context part is covered by `test_version_verdict_context.py` with fake models.
  Owner check 2026-10-16: passed.

## 7. Compact verdict row (owner's request, 2026-10-16)

- [x] 7.1 Replace the inspector's verdict question and buttons with a thumbs up / thumbs down row; the note field appears only once a thumb is chosen; thumbs up saves at once with an optional note, thumbs down needs a note; pressing the chosen thumb again clears. Verify with `VersionVerdict.test.tsx` and `PieceInspector.test.tsx`, `pnpm lint` and `pnpm build`.
- [x] 7.2 Browser check of the compact row on a scratch stack (no render, no model call).
  Browser pass 2026-10-16, same scratch setup as 6.1 (database dropped afterwards; the owner's 8000 and 5173 untouched). 7 of 7 passed: only two thumbs and no note field on a version with no verdict; thumbs down opens the note and an empty note is refused; a note saved with Enter shows "open"; kept after a reload with thumbs down pressed; Mark resolved shows "resolved" and hides resolve and dismiss; thumbs up on v3 saves at once with an optional note field; pressing it again clears.
