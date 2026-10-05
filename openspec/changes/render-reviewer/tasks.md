## 1. Evidence and schema

- [ ] 1.1 Migration `0005_reviews` and models; verify upgrade/downgrade and no autogenerate drift
- [ ] 1.2 Write `app/agent/review.py` (evidence selection, labelled images, spec facts, brief, rule warnings; `Review`/`Item` schema); verify `tests/test_review_evidence.py` with fixture folders covers a 12-frame `draft` turntable giving frames 0, 3, 6, 9 (tier `draft`), a still-only version, a room still added, a screenshot-only version, and an unbuilt version refused

## 2. Reviewer agent

- [ ] 2.1 Add `tools/revision_review.py` (structured call on the reviewer slot, usage recorded, records the review) and `reviewer.md`; verify `tests/test_revision_review.py` (fake model) covers image blocks reaching the reviewer model, a valid list recorded, an empty list recorded as no discrepancies, an invalid answer recording nothing, and an `image` index out of range refused by validation
- [ ] 2.2 Add `reviewer` to `SPECIALISTS`, `LOOP_SLOTS`, the Foreman's decision and the `review_ready` rule; verify `tests/test_foreman.py` covers routing to the Reviewer with a render, never without one, and the Reviewer binding only `revision_review`
- [ ] 2.3 Add open review items to the Designer's house note; verify `tests/test_prompts.py` and a loop test: review → "fix it" → Designer proposes `revise_package` → `yes` → version 2

## 3. Routes and verification

- [ ] 3.1 Add `app/api/reviews.py` (read, resolve, dismiss); verify `tests/test_reviews_api.py` covers listing, resolving removing the item from the Designer's context, 401 without the cookie, and no model slug in any response
- [ ] 3.2 README: asking for a review and closing items; tick CLAUDE.md §11 step 6
- [ ] 3.3 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, `uv run pytest --blender -m blender` (no render added; every render at `draft`); verify all pass and record the counts in the commit message
