## Context

See proposal.md (Why). The approach builds on this current state:

- **Routing.** The Foreman sends price, stock and product questions to the Researcher, with or without a room (`backend/app/agent/foreman.py`, the rule "A price or product question is the Researcher's whatever else holds"; `instructions/foreman.md`).
- **`price_cut_list`** (`backend/plugins/material_cost/tool.py` `run_price`):
  - it prices the approved version and returns `NOT_APPROVED` otherwise;
  - the stored row is described by `app/pricing/pricing.py` `describe_pricing`;
  - `summarise` turns that into text, but writes only the category totals, the total, the sheet lines per material, the cut-charge question, the cut counts and the unpriced lines.
- **The stored result holds more than is reported.** `result["hardware"]` lists every hardware line (id, item, qty, cost_cents), `result["banding"]` the edge-band lines, and `result["delivery"]` the delivery line.
- **Display.** The chat reply view renders GFM Markdown tables with the shadcn table (`frontend/src/components/chat/Reply.tsx`).
- **The Researcher's approval hint** points to "the Approve control on the Pieces page or the conversation's project panel" (`instructions/researcher.md`).
- **Old tasks.** The archived `2026-10-07-pricing-researcher` change has 4.1, 4.3 and 7.1 open.
  - Today's config holds one guideline source and four cited rules.
  - The README pricing section still says the design-rules file "ships empty".

## Goals / Non-Goals

**Goals:**
- One pass that tells the owner whether the pricing works today, with any small defect fixed.
- The chat answer to "what will this cost?" shows the priced lines, not only a total.
- The old change's loose ends are closed and build step 5 is ticked.

**Non-Goals:**
- A new supplier, a new price source, or any change to how prices are captured (§5a stays).
- A pricing view in the Workspace or the inspector. The owner did not choose it on 2026-10-18.
- New design rules. They need a quoted clause from the owner (`TODO(user)` in `design_rules.yaml`).

## Decisions

1. **The table is built in code. The model copies it, not composes it.**
   - `summarise` gains a Markdown table block. Its columns are *Line*, *Quantity* and *Cost*. It has one row per sheet material ("oak-veneer-19: 2 sheets, 64 % use"), one per hardware line, one per band line, and rows for the cut service and the delivery, then a **Total** row.
   - The instructions tell the Researcher to put that table in its reply as given.
   - A table composed by the model was rejected. It invites re-rounding and invented lines, which the existing rule "never state a price a tool did not give you" forbids.
   - The textual bullets the tool returns today stay above the table, so the existing cut-charge question and the incomplete-pricing wording are unchanged.

2. **Unpriced lines stay in the table.** An unpriced line shows "unpriced" in the Cost column, and the reason stays in the existing "INCOMPLETE" list below the table. One place for every line keeps the table and the total visibly in agreement with each other.

3. **Euro format unchanged.** Amounts use the tool's existing `euros()` ("12,50 EUR"), so the pricing card on the Pieces page and the chat show the same strings.

4. **The approval hint names one place.**
   - `researcher.md` names the version's inspector when `workspace-opens-inspector` has landed, and today's wording otherwise.
   - The task checks which one is true at apply time. It does not hard-code both.

5. **Bounded verification.**
   - The first task is the pass, run with `pnpm dev` and the API on a throwaway database.
   - Each finding is recorded under the task as found / fixed / split.
   - A fix larger than about 15 minutes, or a second one, becomes a new change proposal (`TODO(user)` to prioritise). This keeps the change inside its 90 minutes.

6. **Closing the old change.**
   - The archived tasks file gets one note under 4.1, 4.3 and 7.1 naming `knowledge-source-onboarding` and `guideline-hardware-counts` as the changes that delivered them.
   - The open checkboxes are ticked with that note. Editing an archive is limited to this note.
   - CLAUDE.md §11 step 5 is ticked with this change's name.

## Risks / Trade-offs

- [The table makes long replies] → A piece has rarely more than about 15 lines. The table replaces the bullet list of sheets, it is not added to it.
- [The verification pass finds a broken flow] → Recorded and split rather than fixed in place, so the review batch's order is kept.
- [The live toom URL step depends on the site] → A refusal or a 403 is a valid outcome and is recorded as such, never worked around (§5a).

## Migration Plan

None. There is no schema or data change. Stored pricings are read as they are, and older rows without `banding` lines show none.

## Open Questions

- `TODO(user)`: Should a priced line link to its price-list entry? It was left out to keep the reply plain.
