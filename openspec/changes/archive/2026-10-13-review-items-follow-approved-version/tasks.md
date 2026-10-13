## 1. Scope the reader

- [x] 1.1 Give `house_file.latest_open_items` a version argument and select the newest review of that version; return the version with each item. Verify with unit tests: an older version's review is ignored, the approved version's review is used, the latest version's review is used when none is approved, and no review gives an empty list.
- [x] 1.2 In `foreman.py` pass the current version (approved, else latest), and in `prompts.py` name the version in each "Open review items" line. Verify with tests on the prompt text, and that approving another version changes the next turn's items.
- [x] 1.3 Verify that nothing is written: reviews and item statuses are unchanged after the reader runs, and `include_review_items` off still gives no block.

## 2. Checks

- [x] 2.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (one process, no other pytest on the shared database) and record the results here. Result 2026-10-13: ruff clean; pytest -m "not slow" 2442 passed, 39 skipped, 0 failed, run alone on a private database (home_renovation_test_claude2), with the unrelated kitchen seed test deselected (it fails without these changes too).
- [x] 2.2 Owner check on the listening wall: approve a version, ask about the piece's measurements, and confirm no figure from an older version's review is quoted as expected. Owner check 2026-10-13: passed on the listening wall. The piece's measurements were correct after approval.
