## Context

See proposal.md for the motivation. In the module frame the front is y = 0; `shelf_y0("back", inner_d, depth)` gives `inner_d − depth`, negative for a deeper shelf. `CustomBuildSpec` refuses a module whose bounds (`_module_aabb`, from `derive.module_bounds`, which already includes protruding shelves) start below 0 or end past the envelope depth, so only a larger module `y` clears it. Modules and wall shelves carry `y`; extra parts carry no position. `revise_spec` applies the changes and returns change lines; `revise_package.preview` shows those lines behind `interrupt()`, and `run` creates the version. The decisions note is written through `decisions_note.append_row` and `store_note`, as `edit_decisions` does.

## Goals / Non-Goals

**Goals:**
- A front-protruding shelf is accepted with no extra owner request, shown in the confirmation, and recorded.
- Backs stay flush: the build moves as a unit.

**Non-Goals:**
- No new schema field and no change to `shelf_depth_align` semantics.
- No automatic fix for any other envelope or overlap refusal.
- No change for builds where nothing protrudes, and none for shelves protruding at the back (`"front"` align), which grow depth only and already fit.

## Decisions

1. **Fit inside `revise_spec`, after the module changes and before validation.** The shortfall is `max(0, −min(module.y + bounds.y0))` over modules whose bounds come from `module_bounds` on the changed document. Alternative: fit in the schema validator. Rejected: validation must not rewrite a document, and a hand-posted spec with the same fault should still be refused by name.
2. **Move the whole build by the shortfall** (every module and wall shelf `y`), and grow `envelope.depth` by the same amount when an envelope exists. Chosen by the owner (2026-10-13) over moving one module, because moving one breaks flushness against neighbours. The envelope grows by the shortfall, not to a recomputed bound, so an envelope the owner set larger stays larger by the same margin.
3. **Fit lines are produced by the fit, not by the model.** They are appended to the change lines the confirmation already shows, so no new confirmation exists. The requested-measurement check runs on the owner's stated changes first and is not asked about fitted values.
4. **The decisions row is written in `run`, after the version is created**, with `decisions_note.append_row` and `store_note` for the thread and package, so declined, refused and failed revisions write nothing. A failed row write is logged and does not undo the version. One row per revision, topic from the shelf and module ids.
5. **The Designer is told, not trusted.** `designer.md` states that the app fits the position and envelope; the model never sets the fitted `y`.

6. **Folded modules: the protruding part is outside the folds.** `_check_shelf_depths` compares each stated depth with the folded inner depth for any align. For `"back"` align the excess is the part in front of the carcass, which no fold touches, so only the part inside the carcass is held to the folds; the cut width is the narrowest inner width over `[0, inner_d]` (the span `min_inner_width` already takes). `"front"` align keeps the old refusal, because its excess would pass through the back. Alternative: leave the rule and have the Designer clear the fold, which is what happened in Listening wall v18. Rejected: it changes the piece without a request.
7. **The fold guard rides on `requested`.** A `side_folds` change needs a `requested` entry (module, field `side_folds`, value 0 for a clear) whose quote the code finds verbatim in the owner's messages since the last version and which contains a fold word (fold, bend, angle, slant, angled, Knick, Winkel, schräg). The words are a deliberately small list in `measurements.py`; a missing word costs the owner one more sentence, never a silent fold change. Alternative: a prompt rule only. Rejected: the rule exists already and the model broke it; project rules put restrictions in code.

## Risks / Trade-offs

- [Moving every module also moves modules far from the shelf, which changes their stated `y`] → the confirmation lists each moved module, and the shift is the smallest that clears y = 0.
- [The width of a protruding board in a fold that runs along depth may extend into the part in front of the carcass] → the width is taken over the inside part only; task 6.2 checks derive and the generator on a fold along depth as well as along height.
- [A fold word the list lacks refuses a legitimate fold request] → the refusal names the field and asks for the owner's wording; the list is one constant to extend.
- [A later revision removing the deep shelf leaves the build shifted back] → documented in the row; the owner can ask for it to be moved forward, a plain `y` and envelope change. No automatic undo.
- [The note's owner-edited marking on append may stop automatic note refreshes] → reuse the same save `edit_decisions` uses and keep that behaviour; check in task 3.2 and report if it differs.
- [Room placement (`room_fit`) may place the piece by its envelope] → the envelope growth is the same one a hand edit would make; verified with a `room_fit` test in 4.2.

## Open Questions

None.
