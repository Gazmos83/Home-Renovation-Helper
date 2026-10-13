## 1. Recognising the rows

- [x] 1.1 Add to `app/agent/decisions_note.py` a function that returns the rows recording an older version of a piece being saved, from the note, the piece's name and id and the approved number (design decision 1 and 2). Verify with unit tests: "Version 1 saved", "v2 was created", "Listening wall version 2 built" match; a row with change or reason wording, a row naming the approved or a newer version, a row about another piece and a row naming no version do not.
- [x] 1.2 Add a function that removes those rows through `delete_row` (highest line first) and returns the new text, or `None` when nothing matched or no row would be left. Verify with tests for several rows, an emptied heading dropping with its rows, and the all-rows case returning `None`.

## 2. On approval

- [x] 2.1 In `PUT /packages/{id}/versions/{n}/approval`, after the approval and in its transaction, apply the removal to the note of each `thread_pieces` row of the piece, writing through a path that keeps the owner-edited flag. A failure is logged and the approval stands. Verify with API tests: older rows gone in two bound conversations, versions and their folders untouched, no model call, re-approving changes nothing, and a forced failure still approves.
- [x] 2.2 Verify that the note an unbound conversation or another piece holds is not touched, and that an owner-marked note stays owner-marked.

## 3. Checks

- [x] 3.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (one process), and record the results here, naming any failure that also fails without this change. Result 2026-10-13: ruff clean; pytest 2428 passed, 39 skipped with the unrelated kitchen seed test deselected (it fails without this change too). One earlier run had 6 failures in test_engineering_retrieval.py, which passed alone and on the rerun.
- [ ] 3.2 Owner check: on the listening wall, approve a newer version and confirm the "version saved" rows are gone from Decisions so far while the old versions can still be opened.
