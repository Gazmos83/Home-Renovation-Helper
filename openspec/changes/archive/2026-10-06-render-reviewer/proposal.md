## Why

After a draft turntable the owner is the only one who checks the render against the brief, and the Builder that made it has the same blind spots as its own scripts. CLAUDE.md §3 adds a **Reviewer**: it looks at the render and the spec, compares them with the brief, and returns a discrepancy list — it has no write tool. It runs on a different model family from the Builder (`deepseek/deepseek-v4.1-flash`, image input) so it does not share the Builder's mistakes (DESIGN_NOTES). This is §11 step 6, plugin #7 `revision_review` in §5.

## What Changes

- **Reviewer** (new specialist on the `reviewer` slot, already an image slot): reached through the Foreman when the bound piece's latest version has a render or a screenshot and the owner asks for a check.
- **`revision_review`**: code assembles the evidence — the version's Workbench screenshot, a fixed spread of turntable frames (or the still), the room render when there is one, the spec's facts as numbers (overall size, modules with shelves and fronts, materials, cut-list counts), the confirmed brief, and the design-rule warnings from `pricing-researcher` — and asks the Reviewer's model for a structured discrepancy list: each item names the aspect (brief, proportion, material, placement, construction, render), what was expected and from where, what is observed and in which image, a severity (`minor` / `major`), and an optional suggested change in words. The Reviewer may not claim a measurement it cannot read from the spec's numbers.
- **Reviews are recorded** in the house file per package version and render, with the items and when; the Designer's context lists the open items of the latest review so "fix what the reviewer found" becomes a normal `revise_package` the owner confirms. The owner can mark an item resolved or dismissed.
- **No write path**: the Reviewer's header binds `revision_review` only; it cannot create or revise a piece, render, or change the house file except its own review record. A review never starts a render.
- **Routes**: read a version's reviews; mark an item resolved or dismissed (owner-gated).

**Ladder step and agent:** feeds ladder step 1 (a review becomes a revision the owner confirms); no step-2/3 change. Agents: Reviewer (new), Designer (reads open review items), Foreman (routes to the Reviewer). **Render guard:** not affected — the Reviewer only reads existing renders and never requests one. **bpy allow-list:** not affected.

## Capabilities

### New Capabilities
- `render-review`: the Reviewer's evidence, its structured discrepancy list, the review record, and the no-write boundary.

### Modified Capabilities
- `design-agents`: the Foreman may route to the Reviewer; the Reviewer runs on its slot.
- `house-file`: reviews are recorded per version, and the Designer's turn context lists the latest review's open items.

## Impact

- Code: `app/agent/tools/revision_review.py`, `app/agent/review.py` (evidence assembly, schema), `app/agent/instructions/reviewer.md`, `app/agent/foreman.py` (Reviewer specialist, routing rule), `app/agent/models/slots.py` (`reviewer` in the loop slots), `app/api/reviews.py`, migration `0005_reviews`.
- Tests: evidence selection per render kind, image blocks reaching the Reviewer's model (fake), structured output validation, the refusal when no render exists, the Reviewer binding no write tool, review items in the Designer's context, resolve/dismiss routes, and no model name in any response.
- Depends on `pricing-researcher` (design-rule warnings as evidence; the Researcher in the Foreman's set) and `apartment-intake` (image content blocks in the agent node).
