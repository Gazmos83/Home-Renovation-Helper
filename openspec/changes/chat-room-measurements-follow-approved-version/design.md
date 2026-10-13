## Context

- The chat room block comes from `foreman.py` (scope rooms via `house_file.describe_room`) into `prompts.house_note`, which prints `_size` (bounding box) and ceiling height.
- Inspector figures come from `compositions.room_dimensions(document)` over a version's `input.json`; `composition_note` prints items only.
- Checked 2026-10-12: the house-file Wohnen corners and approved version 2's `resolved.rooms[0].corners` are identical; the mismatch is the bounding box (6200 × 6064) versus wall lengths, not stale data. A conversation note or earlier reply can still carry old figures.

## Goals / Non-Goals

**Goals:** the chat quotes the inspector's numbers; approval takes effect next turn; the bot can look a version up to correct a figure; placement tools (`room_fit`, `compose_room`) use the same version's corners and openings so a door refusal matches the inspector.
**Non-Goals:** editing a room's dimensions from chat; writing composition figures back to the house file; changing generators, the inspector UI or the spec schema.

## Decisions

**Read at turn time, no sync step.** The block is rebuilt each turn from the approved version's `input.json`, so "update on approval" needs no event or write. *Alternative:* copy dimensions into the house file on approval. Rejected: it would write a second source of truth for the same numbers.

**Reuse `room_dimensions`.** `house_note` gains an optional per-room dimensions argument; `foreman.py` fills it using `approved_composition_version_of` (else the latest version) and `room_dimensions`. Wall lines read "wall 1: 6200 mm". Bounding box is dropped from the line when dimensions exist, and labelled "bounding box" otherwise. Apartment scopes use the same function (walls and per-room ceilings).

**Lookup as a read-only tool.** A small tool (Researcher/Designer-readable, validated args: version number only; room taken from the thread scope, never from the model) returns the same dimensions for a version in the confirmed room. *Alternative:* note only. Rejected: the owner asked for the bot to confirm against a named version, which may not be the approved one.

**Prompt wording.** One added sentence in the house preamble: measurements in this block supersede earlier quotes and the conversation note.

**Placement reads the same version.** Owner test 3.3 (2026-10-13): quoting wall 2 was correct, but `room_fit` refused a listening-wall placement citing a house-file door on wall 2 (850–1850 mm) that the approved plan does not use for that check. `placement_room` returns the approved (else latest) version's resolved room as a house-file-shaped dict (`corners_mm`, openings, height); `room_fit` and compose `_rooms_in_scope` prefer it, falling back to the house-file room when there is no composition plan. *Alternative:* sync openings into the house file on approval. Rejected: second source of truth.

## Risks / Trade-offs

- [Document unreadable or without a room plan] → fall back to house-file figures, labelled as such.
- [Prompt grows by a few lines per room] → negligible against the token budget; apartments list one line per wall only for the confirmed scope.
- [Owner edits the house-file room after approving] → the block shows the approved version's figures, labelled with its version, so a later difference is visible rather than silent; placement follows the composition plan until a new version is composed from an updated house file.
