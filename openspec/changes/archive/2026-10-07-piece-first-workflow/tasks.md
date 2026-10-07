## 0. Preconditions

- [x] 0.1 Confirm `pricing-researcher` is archived (its `cut-list-pricing` spec in `openspec/specs/`). Verify `openspec list` no longer shows it

## 1. Room-less brief

- [x] 1.1 Make `room_name` optional in `RecordBriefArgs` (`backend/plugins/intake/tool.py`); `_resolve` keeps nothing without a name or geometry and refuses geometry without a name; preview prints "Room: not given yet"; `_brief` omits `room`. Verify `tests/test_record_brief.py` covers: brief without a room previews and on `yes` stores the brief and preferences and no room; geometry without a name refused; the existing room scenarios unchanged
- [x] 1.2 Pin routing: verify `tests/test_foreman.py` gains a test where a room-less brief in state routes "design it" to the Designer (no code change in `foreman.py` router)
- [x] 1.3 Rewrite the room lines of `app/agent/instructions/intake.md` (room optional, ask once, never insist). Verify `tests/test_instructions.py` passes
- [x] 1.4 `room_fit` unknown-room refusal names Intake and says "none recorded yet" when empty. Verify `tests/test_room_fit.py` covers both wordings

## 2. Starter template

- [x] 2.1 Add `backend/fixtures/packages/templates/custom-build.json` (decision 4). Verify `tests/test_custom_build_spec.py` gains a test that it validates, has one module with carcass, back, shelves and a two-door hinged front, and derives cut-list rows and hardware
- [x] 2.2 `_designer_note()` inlines `custom-build` first; update `designer.md` to start from it unless another template fits. Verify a `tests/test_foreman.py` test that the note lists `custom-build` before `fold-down-desk`, and `tests/test_instructions.py` passes
- [x] 2.3 Build the template headless once (no render). Verify with `uv run pytest --blender -m blender -k custom_build_template` (new test, marked `blender` and `slow`) that the build succeeds and publishes a screenshot

## 3. Approval store and routes

- [x] 3.1 Add `PieceVersion.approved_at` and migration `0010_version_approval` with the partial unique index. Verify `tests/test_version_approval_migration.py` (upgrade adds column and index; a second approved version of one piece is rejected by the database; downgrade removes both)
- [x] 3.2 `house_file.approve_version` / `unapprove_version`; `pieces()` and the house note carry `approved_version`; the Foreman's facts name it. Verify `tests/test_house_file.py` covers: approve moves the approval; idempotent approve and unapprove; revision creates an unapproved version; the house note prints `approved: v4` and `approved: none`
- [x] 3.3 `PUT` and `DELETE /packages/{id}/versions/{n}/approval`; `describe_version` reports `approved_at`. Verify `tests/test_packages_api.py` covers: approve a succeeded version; unapprove; 409 `not_built` while `running`; 409 `not_recorded` for a folder-only package; 404 unknown version; 401 without the cookie
- [x] 3.4 `ProgressOut.approved_version`. Verify `tests/test_chat_api.py` progress tests read it, and the no-internals test still passes
- [x] 3.5 `price_cut_list` refuses an unapproved version with `NotApproved` (reason names the Pieces page and the project panel); the Researcher tool returns the reason; `POST …/pricings` answers 409 `not_approved`; one line in `researcher.md` says to point the owner to approval. Verify `tests/test_pricing.py` covers refusal with no record written and an approved version priced; `tests/test_pricing_api.py` covers the 409; `tests/test_pricing_loop.py` covers the tool's refusal text; `tests/test_instructions.py` passes; existing pricing tests approve their fixture version first
- [x] 3.6 `describe_pricing` reports `version_approved`. Verify `tests/test_pricing_api.py` covers a pricing read after unapproval (unchanged totals, `version_approved: false`) and after approval moves to another version

## 4. Studio

- [x] 4.1 `api.ts`: `version`, `approveVersion`, `unapproveVersion`, `Progress.approved_version`. Verify `pnpm lint` and the type check in `pnpm build`
- [x] 4.2 Pieces page: approval badge and Approve/Unapprove for succeeded versions, refusal shown next to the version. Verify `Pieces.test.tsx` covers approve, unapprove and a 409 shown
- [x] 4.3 Project panel: "Approved: vN" and the control for the latest built version. Verify `Conversation.test.tsx` covers latest v5 with approved v4, and approve refreshing the panel without a reload

## 5. Verification

- [x] 5.1 Browser check against the running backend: start a conversation, confirm a brief with no room, have the Designer create a piece from `custom-build`, see the build's screenshot, ask the Researcher for a price and read the approve-first refusal, approve the version on the Pieces page, see it in the panel, price it, unapprove it; ask for `room_fit` and read the Intake hint. No render is started (no tier). Record the check in the commit message
  - Browser pass 2026-10-07: headless Chrome via playwright-core, with the API (port 8100) and Vite (port 5180) on a scratch database and scratch render and upload folders. Real routed models through OpenRouter.
    - Intake proposed the brief with "Room: not given yet"; `yes` recorded it.
    - The Designer created `tall-storage-cabinet` from `custom-build` (template `custom-build`, cabinet with 4 shelves and 2 hinged doors). The build succeeded in 4 s and the screenshot showed in the project panel.
    - "What will it cost?" got the Researcher's approve-first refusal, and no pricing record was written.
    - Approve on the Pieces page showed "Approved: version 1", which survived a reload, and the panel showed "Approved version 1".
    - The pricing then came back incomplete at 150,00 EUR, with the unpriced lines named.
    - Unapprove from the panel cleared both views; the one pricing record reads `version_approved: false`.
    - `room_fit` for `Wohnen` said no rooms are recorded yet and that Intake records the room.
    - No render was started.
  - Observation: the last reply called the piece "approved" after it was unapproved. The turn's facts came from the house file; the model echoed the owner's earlier "I've approved version 1". This is not a code defect.
- [x] 5.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, and `pnpm lint && pnpm test && pnpm build`. Verify all pass and record the counts in the commit message
  - 2026-10-07: ruff clean; `pytest -m "not slow"` 1442 passed, 29 skipped, 9 deselected; `pnpm lint` clean, `pnpm test` 59 passed, `pnpm build` ok. The one new `blender` test (`-k custom_build_template`) passed separately. Record these in the commit message.
