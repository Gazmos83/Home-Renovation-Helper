## Why

The end-to-end review of 2026-10-15 asks to "port pricing functionality from the old repo". Most of it is already ported (`pricing-researcher`, `combine-pricing-pages`, `studio-pricing-and-agent-settings-tabs`). The Studio Pricing tab has Prices, Snapshots and Remnants, the price list has "Add an entry" and "Paste a toom URL", the Pieces page has "Price this version", and the Researcher has `price_cut_list` and `manage_remnants`. Three things are still open, and on 2026-10-18 the owner asked for all three:
- **Nobody has checked the whole thing since 2026-10-06.** The last browser pass of the price-list pages is from 2026-10-06. The pages have moved into Design Studio tabs since then.
- **The chat does not show the priced cut list.** "What will this cost?" in a piece conversation reaches the Researcher, which calls `price_cut_list`. But the tool's summary (`backend/plugins/material_cost/tool.py` `summarise`) gives only the category totals and a sheet count per material. The hardware lines, edge-band lines and their prices are left out, although the stored pricing has them (`result["hardware"]`, `result["banding"]`). So the owner gets a total without the list behind it.
- **The archived `pricing-researcher` change still has open tasks.** These are 4.1 (guideline sources), 4.3 (design rules) and 7.1 (README, `.env`, and ticking CLAUDE.md §11 step 5).
  - 4.1 and 4.3 have since been covered by later changes. `backend/config/guideline_sources.yaml` lists `topnotch-shelf-brackets` (`knowledge-source-onboarding`). `backend/config/design_rules.yaml` ships four cited rules: `shelf-bracket-count`, `shelf-bracket-spacing`, `shelf-pin-count` and `hinge-count` (`guideline-hardware-counts`).
  - What is left is paperwork. The README still says the rules file "ships empty", and build step 5 is still unticked.

## What Changes

- **Verification pass first (bounded).** A browser and API pass over the pricing flow:
  - price list: add an entry, set an override, paste a toom URL, refresh, a refused non-toom URL;
  - snapshots and remnants: create, delete and one refusal each;
  - "Price this version" on an approved version on the Pieces page;
  - the chat price question.
  
  The findings are written into `tasks.md`. A defect it finds is fixed in this change only if the fix fits the change's time box; anything larger becomes a new change, `TODO(user)`.
- **The chat shows the priced cut list.** `price_cut_list` returns every priced line, not only totals:
  - each sheet material: sheets, use and cost;
  - each hardware line: item, quantity and cost, or "unpriced" with its reason;
  - each edge-band line;
  - the cut service and delivery;
  - the total, and whether the pricing is complete.
  
  The Researcher shows these lines as one table in its reply. The reply view already renders tables. No price is stated that is not in the stored pricing.
- **The Researcher's approval hint follows the app.** When the version is not approved, the Researcher tells the owner where the Approve control is. Today it names "the Pieces page or the conversation's project panel". If `workspace-opens-inspector` has landed, it names the version's inspector instead.
- **Old tasks closed.**
  - The README's pricing section is updated: the shipped design rules, and the guideline sources now listed.
  - CLAUDE.md §11 step 5 is ticked.
  - The archived change's open tasks 4.1, 4.3 and 7.1 get a note saying which later change closed them.
- **Unchanged:** §5a stays exactly as it is.
  - toom is the only supplier, and Bauhaus, Kaufland and OKI stay excluded;
  - prices come only from lawful sources, and a 403 is an answer;
  - a missing price makes the pricing incomplete and is never guessed;
  - only an approved version is priced.

Ladder: none of the three steps (no schema or generator change). Agents touched: the **Researcher** (tool output and instructions). The **render guard** and the **bpy allow-list** are **not affected**.

Estimate: about 90 minutes:
- verification pass, about 30 minutes;
- summary and instructions, about 35 minutes;
- docs and close-out, about 15 minutes;
- fixes, a 10-minute buffer.

If the verification pass finds more than one small defect, those defects are split into a follow-up change rather than stretching this one.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `cut-list-pricing`: an added requirement that a price question answered in the conversation shows every priced line of the stored pricing.

## Impact

- `backend/plugins/material_cost/tool.py`: `summarise` lists hardware, banding, cut service and delivery lines.
- `backend/app/agent/instructions/researcher.md`: the table rule and the approval hint.
- Tests: `tests/test_material_cost*.py` / `tests/test_pricing_loop.py` (lines listed, unpriced lines named, no price outside the stored pricing), `tests/test_instructions.py`. Written now, run in the batch check.
- `README.md` pricing section; `CLAUDE.md` §11 step 5; a closing note in `openspec/changes/archive/2026-10-07-pricing-researcher/tasks.md`.
- Frontend: no code change expected, since the reply view renders GFM tables (`frontend/src/components/chat/Reply.tsx`). The verification pass may add fixes.
- Relation: `workspace-opens-inspector` (same review batch) moves the Approve control. Whichever change lands second updates the hint's wording.
