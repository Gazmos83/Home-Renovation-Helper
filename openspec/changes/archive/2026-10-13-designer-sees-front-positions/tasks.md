## 1. The summary

- [x] 1.1 In `prompts.py`, derive each front entry's span, top/bottom/between and covered shelves with `front_layout` and `shelf_centres`, and append it to the module's `fronts:` text in `piece_note` only; leave `describe_fronts` unchanged and fall back to the old text on a derive failure. Verify with `test_piece_note.py`: the v17 case (door at top, covers no shelf), a bottom door covering shelves, two entries, no fronts, and a failure case.
- [x] 1.2 Update `PIECE_PREAMBLE` so positions are described as what is built, preferred over the brief and earlier messages, and the version is named. Verify with a test on the note text.
- [x] 1.3 Add the matching one-line rule to `designer.md`. Verify with `test_instructions.py`.

## 2. Checks

- [x] 2.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (one process) and record the results here. Result 2026-10-13: ruff clean; pytest -m "not slow" 2442 passed, 39 skipped, 0 failed, run alone on a private database (home_renovation_test_claude2), with the unrelated kitchen seed test deselected (it fails without these changes too).
- [x] 2.2 Owner check on the listening wall: ask to extend the depth of the second shelf from the bottom on version 17 and see the Designer go by the door's real position. Owner check 2026-10-13: passed on the listening wall. The Designer went by the door's real position.
