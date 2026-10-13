## Context

`house_file.latest_open_items(session, package_id)` returns the open items of the newest `Review` of the piece by `created_at`; `reviews` rows carry a `version`. `foreman.py` calls it for the bound build (unless the memory settings leave review items out) and `prompts.house_note` renders "Open review items: expected …; observed …" without a version. `approved_version_of` and the piece's latest version are already known where it is called.

## Decisions

1. **Scope by version, not by closing.** The reader takes a version argument and selects the newest review of that version; nothing is written. Older items are simply not shown, and stay available for audit and in the Reviews views.
2. **Current version = approved, else latest.** Matches how the room block and the owner's mental model work: the approved version is the one the owner stands behind.
3. **Label each item with its version** in the prompt line, so the model says which version a discrepancy is about.
4. **Memory setting honoured.** `include_review_items` still switches the block off entirely.

## Risks / Trade-offs

- An approved version that was never reviewed shows no review items even if the latest version has open ones; that is intended, since the owner chose the approved version.
- A fresh review of the approved version still builds its "expected" from the brief; changing that is a separate change.
