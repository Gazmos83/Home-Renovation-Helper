## 1. The brief follows approval

- [x] 1.1 Add a function that, given a piece's brief and an approved version's overall height, returns the brief with `max_piece_height_mm` raised and `max_piece_height_from_version` set, or the brief unchanged. Verify with unit tests: taller raises, equal or lower leaves it, no limit leaves it, and no other field changes.
- [x] 1.2 Call it from the approval route in the approval's transaction, reading the version's document and `overall`; log and carry on if it fails. Verify with API tests: approving a taller version raises the stored limit, approving a lower one does not, re-approving and unapproving change nothing, and a forced failure still approves.
- [x] 1.3 Verify that a review reads the raised limit: `revision_review` prints "max_piece_height_mm: 2238" and the version after approval. Verify with a test on the review prompt text.

## 2. Stale height items

- [x] 2.1 Add a function that dismisses the open items of a piece version whose expected text names `max_piece_height_mm` with a figure below a given limit, and returns how many. Verify with unit tests: 2200 against 2238 is dismissed, an equal or higher figure and an item without the key stay open, another version's items stay open, and the text is unchanged.
- [x] 2.2 Call it from the approval route after the limit is raised, with the brief's current limit, on every new approval and in the same guarded block. Verify with API tests: items dismissed on approval, dismissed on a second approval after the limit was already raised, other items open, and a forced failure still approves.

## 3. Checks

- [x] 3.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (one process, a private test database) and record the results here. Result 2026-10-13: ruff clean; pytest -m "not slow" 2450 passed, 39 skipped, 0 failed, run alone on a private database, with the unrelated kitchen seed test deselected (it fails without these changes too).
- [x] 3.2 Owner check on the listening wall: ask for a review of the approved version and confirm it no longer expects 2200 mm. Owner check 2026-10-13: passed on the listening wall. A review no longer expects 2200 mm.
