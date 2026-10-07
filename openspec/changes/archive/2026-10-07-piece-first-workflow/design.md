## Context

See proposal.md for the why. Current state the approach builds on:

- `record_brief` (`backend/plugins/intake/tool.py`) has `room_name: str` required, and `_resolve` refuses a name that is not stored unless corners and a ceiling height come with it. The brief dict always carries `room`.
- The Foreman's code rule (`foreman.py`, router) already lets the Designer work once **any** brief is in state: `if not buildable and not state.get("brief") ... chosen = "intake"`. A room-less brief therefore unlocks the Designer with no routing change.
- `create_piece` looks the room up by `brief["room"]` and records `room_id=None` when there is none. `room_fit` refuses an unknown room naming the known ones ("its rooms are: none" when empty).
- `_designer_note()` inlines the `fold-down-desk` and `blank-build` templates into every Designer prompt. `blank-build` has no modules; its test asserts it derives nothing.
- `PieceVersion` (`piece_versions`) holds `package_id`, `version`, `revised_from`, `changes`, `created_at`. Latest migration: `0009_remote_render_jobs`.
- `describe_version` (`app/api/packages.py`) is filesystem-only. The Pieces page lists `/packages` and fetches renders per version. The project panel reads `GET /chat/threads/{id}/progress` (`ProgressOut`).

## Goals / Non-Goals

**Goals:**
- A brief with no room, with the room demanded only where a room is used.
- A starter template whose first build shows a cabinet.
- Approval as an owner act, stored once, read everywhere a version is shown.

**Non-Goals:**
- Placing approved pieces in a room render, stand-ins, imported models (`room-composition`).
- Routing room-measurement corrections to Intake after a brief exists (`foreman-routing-fixes`); this change relies on it for adding a room later.
- Gating reviews on approval.
- A Listening Wall generator or any new spec field.

## Decisions

1. **Room optional in `record_brief`, not a second tool.** `room_name` becomes `str | None`. With no name and no geometry, `_resolve` returns "keep nothing" with no refusal. Geometry without a name is refused ("a room needs a name"). The preview prints `Room: not given yet`; `_brief` omits `room`. *Alternative:* a separate `record_piece_brief` tool. Rejected: two tools for one confirmation would split Intake's instruction and the `brief` subject, and the existing room path stays byte-for-byte the same.
2. **No routing code change.** The router already treats any brief as enough for the Designer; a test pins that a room-less brief routes "design it" to the Designer. Intake's instruction changes from "when you have the room … call `record_brief`" to "the room is optional; ask once whether the owner wants to name it now, never insist".
3. **`room_fit` refusal names the way forward.** The unknown-room text gains "Intake records a room from its measurements or a plan", and "none recorded yet" when the house file is empty. No other behaviour of `room_fit` changes.
4. **`custom-build.json`.** One module `cabinet`, `x/y/z = 0`, 800 × 1800 × 400 mm, `carcass`/`back` slots as in the other templates, 4 shelves, one `door` front with `count: 2` and `opening: hinge`, two wall hangers; `template: "custom-build"`. An assembly note says the sizes are placeholders the brief replaces. `_designer_note()` inlines it first: `("custom-build", "fold-down-desk", "blank-build")`. *Alternative:* replace `blank-build`. Rejected: tests and the spec's "blank" use rely on it, and it is still the right start for a piece built up module by module. Cost: about 300 more tokens on each Designer prompt, inside the existing context budget.
5. **Approval on the version row, one per piece by index.** Add `piece_versions.approved_at TIMESTAMPTZ NULL` and a partial unique index on `(package_id) WHERE approved_at IS NOT NULL`. `house_file.approve_version` clears the piece's other approval and sets this one in one transaction; `unapprove_version` clears it. *Alternative:* `pieces.approved_version`. Rejected: the spec reads approval as a property of a version ("when it was approved"), and the version row is where revisions already live; the partial index gives the same at-most-one guarantee.
6. **Owner-gated routes on the package router.** `PUT /packages/{id}/versions/{n}/approval` and `DELETE` on the same path, both answering the version description. 404 for an unknown package or version (existing `existing_version`), 409 `not_built` when `status.json` is not `succeeded`, 409 `not_recorded` when the house file has no version row. `describe_version` gains `approved_at` (string or null) read from the house file by the routes that call it. *Alternative:* a gated `approve_version` agent tool with the yes/no card. Rejected: approval is the owner's acceptance of the build; keeping it off the model removes any path where a model proposes its own acceptance, and the button is one click either way. The Designer's instruction says to point the owner at the Approve control when asked.
7. **Approval in context and progress.** `house_file.pieces()` gains `approved_version`; the house note prints `approved: v4` or `approved: none`; the Foreman's facts line adds the same for the bound piece. `ProgressOut` gains `approved_version: int | None`. The progress step list is unchanged (an approval step belongs with `room-composition`, which consumes it).
8. **Frontend.** `api.ts` gains `approveVersion`, `unapproveVersion` and `version(id, n)`. The Pieces page's `Version` reads `version(id, n)` for status and approval and shows an "Approved" badge and an Approve/Unapprove button (only when `succeeded`). The project panel shows "Approved: v4" and the same control for the latest built version. Both invalidate `["pieces"]`, the version query and `["progress", threadId]` on success.
9. **Pricing refuses an unapproved version (owner decision 2026-10-07).** The check sits in `app/pricing/pricing.py` `price_cut_list`, before any packing, so the Researcher's tool and the owner's `POST …/pricings` share one rule: it raises a new `NotApproved` refusal (the tool returns its text; the route answers 409 `not_approved`). The reason names the Pieces page and the project panel. `describe_pricing` gains `version_approved: bool`, read from the version row at read time; nothing is written to the immutable pricing record. *Alternative:* a MODIFIED `cut-list-pricing` requirement. Rejected: that capability exists only in the unarchived `pricing-researcher` delta, so a MODIFIED header here would fail to archive; the gate is an ADDED requirement under `furniture-packages`, next to approval itself. `pricing-researcher` must be archived before this change for the code it builds on, which tasks 0.1 checks. *Alternative:* store approval on the pricing record. Rejected: the record is immutable and approval can change after it.

## Risks / Trade-offs

- [A room-less brief lets the Designer size a piece with no wall to check] → The Designer still uses only the owner's numbers; `room_fit` refuses until a room exists; `room-composition` requires a room to place it.
- [The owner approves, then revises, and expects the new version to be approved] → The panel shows "latest v5, approved v4" side by side; the spec states approval never carries over.
- [Folder-only packages (created through the package routes) cannot be approved] → 409 `not_recorded` with a reason; such packages have no brief either and are outside the conversation flow.
- [The owner asks for a price of a piece still being revised] → The Researcher says to approve the version first; approval is one click and can be undone.
- [Unapproving a version that a later room render placed] → Out of scope here; `room-composition` decides what a placed, unapproved version shows.

## Migration Plan

`0010_version_approval`: add the nullable column and the partial unique index; every existing version reads unapproved. Downgrade drops the index and the column. No data backfill. Rollback of the code alone is safe: the column is ignored.

## Open Questions

None. Pricing of unapproved versions was decided by the owner on 2026-10-07: refused.
