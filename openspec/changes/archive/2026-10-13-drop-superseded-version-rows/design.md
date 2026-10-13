## Context

The note is free text written by a model (compression) or by the owner; its rows have no structure that says "this records a save". Approval happens in one place, `PUT /packages/{id}/versions/{n}/approval`, which calls `house_file.approve_version`. A build's note lives on its `thread_pieces` row, one per conversation bound to the piece. The row rules (`decisions_note.rows`, `delete_row`) and the shared save (`store_note`) already exist.

## Goals / Non-Goals

**Goals:** drop "older version saved" rows on approval, deterministically, without a model call; leave versions alone.

**Non-Goals:** deleting versions (kept manual, see `version-cleanup-and-inspection`); changing what the compressor writes; cleaning up on unapproval or on a new unapproved version.

## Decisions

1. **Code, not the model, recognises the rows.** A row qualifies only when all hold: it names an older version of this piece (`version N` or `v N`, N lower than the approved number); it mentions saving, creating or building, in plain words; and it holds no other decision, meaning it is short and carries no change or reason wording ("moved", "changed", "because", "instead", "from … to"). Anything uncertain is kept: a wrongly kept row costs a line, a wrongly removed one loses a decision.
2. **The piece's own rows only.** A row is matched when it names this piece's name or id, or when the note is that build's own note and the row names no other piece. A row naming another piece is kept.
3. **Reuse the row rules and the save.** Rows are found with `decisions_note.rows` and removed with `delete_row` from the highest line down, then saved with the shared save so neutralising and the 8000-character rule still apply. If no row is left, nothing is saved.
4. **Owner mark unchanged.** The note's owner-edited flag is kept as it was, since the owner did not edit it; the text is still written through a path that does not set it.
5. **Where it runs.** In the approval route, after `approve_version` and in the same transaction, for every `thread_pieces` row of the piece. A failure here must not fail the approval: it is logged and approval stands.

## Risks / Trade-offs

- A free-text heuristic can miss odd phrasings (they stay, harmless) or, rarely, match one that held a decision; decision 1 leans to keeping. The tests pin the wording cases.
- A row an owner wrote on purpose ("Version 2 saved as a fallback") can be matched; it carries no change wording only if it is that bare. Accepted; the owner can add it again.

## Open Questions

None. Assumed: "older" means a lower number than the approved version, wherever the latest version is.
