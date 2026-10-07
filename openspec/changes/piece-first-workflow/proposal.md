## Why

The owner works piece first: see the furniture, learn its parts' names, revise it, approve it, and only then place it in a room render where lighting and placement matter. Today the room comes first. `record_brief` refuses a brief without a room (corners and ceiling height, or a stored room), so the listening-wall session spent about two hours on wall measurements before any furniture existed (App Check 06-10-2026). The first build also shows little: `blank-build.json` has no modules and builds nothing, and `fold-down-desk.json` is one specific piece. Nothing marks a version as the one the owner accepts, so the coming room render (`room-composition`) has nothing to choose from.

## What Changes

- **Room-less brief.** Intake may confirm a brief with the piece's purpose, rough size and heights, style and budget, and no room. The room stays optional at the brief and becomes required at placement: `room_fit` (and later the room render) refuses a missing room in plain words that say Intake records it. A brief with a room behaves as today.
- **Starter template.** A generic `custom-build.json` template ships next to `fold-down-desk.json` and `blank-build.json`. It has one visible cabinet module (carcass, back, shelves, a pair of doors), so the first build of any piece shows something. The Designer is offered it first and starts from it unless another template fits better. It is a `custom_build` document like the others, so revisions, cut list, room fit and pricing work on it unchanged. It is not listening-wall specific (owner decision).
- **Approve and unapprove a version.** The owner approves a built version of a piece from the Studio (the Pieces page and the conversation's project panel), and can unapprove it. At most one version per piece is approved. A revision creates a new, unapproved version; approval never carries over. Approval is recorded in the house file and shown wherever the piece is shown. It is an owner act on an owner-gated route: no model tool can approve or unapprove.
- **Pricing follows approval (owner decision 2026-10-07).** Only an approved version is priced: `price_cut_list` and the owner's pricing route refuse an unapproved version, saying to approve it first. A pricing made while a version was approved stays readable after unapproval and is marked as for a no-longer-approved version. Reviews stay ungated.
- Ladder and agents: **ladder step 1** only. Touches Intake (`record_brief` and its instruction), the Designer (template note and instruction), the Researcher (pricing refuses an unapproved version; instruction line), and the Foreman's house-file facts (approval state). The Builder, Reviewer and Lighting & materials specialists are unchanged. **The render guard and the bpy allow-list are not affected**; no render is started by anything in this change.
- Consumer: `room-composition` (next change) places only approved versions in a room render; this change only records and shows approval.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: Intake may confirm a brief without a room; the Designer starts from the shipped starter template; `room_fit` refuses a missing room pointing to Intake.
- `house-file`: version records carry approval; at most one approved version per piece; every turn's context names the approved version.
- `furniture-packages`: owner-gated routes approve and unapprove a built version; a version's description reports whether it is approved; only an approved version is priced, and a pricing of a later-unapproved version is marked.
- `studio-ui`: the Pieces page and the project panel show approval and let the owner approve or unapprove.

## Impact

- Backend: `plugins/intake/tool.py` (`RecordBriefArgs` room optional, preview and run without a room), `app/agent/instructions/intake.md` and `designer.md`, `app/agent/foreman.py` (`_designer_note` lists `custom-build` first; facts name the approved version), `app/agent/house_file.py` (approve, unapprove, approval in `pieces()` and the house note), `app/db/models.py` (`PieceVersion.approved_at`), Alembic `0010_version_approval`, `app/api/packages.py` (approval routes, `describe_version`), `app/agent/progress.py` and `app/api/chat.py` (`ProgressOut.approved_version`), `plugins/room_fit/tool.py` (refusal wording), `app/pricing/pricing.py` (`price_cut_list` approval check, `describe_pricing` reports `version_approved`), `app/api/pricing.py` (409 `not_approved`), `app/agent/instructions/researcher.md`.
- Fixtures: `backend/fixtures/packages/templates/custom-build.json`.
- Frontend: `src/lib/api.ts`, `src/routes/Pieces.tsx`, `src/routes/Conversation.tsx` (project panel).
- Tests: pytest for the brief, template, approval store, routes, migration and progress; Vitest for the Pieces page and the panel; a browser check of approve/unapprove.
- One migration, no new dependency, no change to `config/`.
- Related active changes: `photoreal-detail` and `pricing-researcher` modify `design-agents` requirements this change does not touch except `Room fit` (taken from `pricing-researcher`'s text); the pricing gate is an ADDED requirement under `furniture-packages` rather than a MODIFIED `cut-list-pricing` requirement, because `cut-list-pricing` exists only in the unarchived `pricing-researcher` change; `studio-conversation` adds the project panel this change extends; `feedback-capture` adds the Pieces page this change extends.
