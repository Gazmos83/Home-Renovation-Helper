## 1. Verification pass

- [ ] 1.1 Browser and API pass, with **no render tier** (`pnpm dev` + API on a throwaway database, owner signed in):
  - Design Studio → Pricing → Prices: "Add an entry" (a panel with sheet size), a duplicate key refused, override set and cleared, "Paste a toom URL" with a real toom product (captured, or the refusal recorded as an answer), refresh, a non-toom URL refused in plain words;
  - Snapshots: create, a future date refused, delete;
  - Remnants: an oversize remnant refused, add, remove;
  - Pieces: "Price this version" on an approved version, with the pricing shown;
  - chat: "what will this cost?" in that piece's conversation.
  
  Record each finding here as found / fixed / split. A fix over about 15 minutes, or a second fix, becomes a new change (`TODO(user)` to prioritise).

## 2. Priced lines in the chat

- [x] 2.1 In `backend/plugins/material_cost/tool.py`, extend `summarise` with a Markdown table:
  - one row per sheet material, hardware line, band line, cut service and delivery, plus a Total row;
  - unpriced lines shown as "unpriced";
  - amounts formatted with `euros()`;
  - the existing bullets kept.
  
  Write tests (do not run yet) for:
  - "Complete pricing in the chat";
  - "Unpriced hardware line";
  - every amount in the table appearing in the stored pricing.
- [x] 2.2 In `backend/app/agent/instructions/researcher.md`:
  - add the rule to show the tool's table as given;
  - set the approval hint to where the Approve control is at apply time (the version's inspector if `workspace-opens-inspector` has landed).
  
  Update `tests/test_instructions.py` and `tests/test_pricing_loop.py` expectations for "Version not approved" (do not run yet).

## 3. Close-out

- [x] 3.1 README "Pricing, the price list and guidelines":
  - state the four shipped design rules and the listed guideline source;
  - remove "it ships empty".
  
  Add the closing note under 4.1, 4.3 and 7.1 in `openspec/changes/archive/2026-10-07-pricing-researcher/tasks.md` (closed by `knowledge-source-onboarding`, `guideline-hardware-counts` and this change) and tick them.
- [x] 3.2 Tick CLAUDE.md §11 step 5 with `openspec/changes/pricing-completion`.

## 4. Checks

- [x] 4.1 Run `uv run ruff check .` in `backend/` and `pnpm lint && pnpm test` in `frontend/` if a frontend file changed. pytest is deferred to the batch check after the last change of the 2026-10-18 review batch (skip RunPod/offload tests, throwaway `TEST_DATABASE_URL`).
- [ ] 4.2 Browser pass, with **no render tier**: in a conversation bound to an approved, priced piece, "what will this cost?" shows the table with each line and the total, and an unpriced line shows "unpriced".
