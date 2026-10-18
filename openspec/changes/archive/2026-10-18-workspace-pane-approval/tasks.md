## 1. Shared control

- [x] 1.1 Add `ApprovalRow` under `frontend/src/components/` (Approved badge / "Approve version N" / "Unapprove version N", disabled while pending, refusal via `FieldError`); verify with a Vitest unit test covering built-unapproved, approved and unbuilt states

## 2. Piece pane

- [x] 2.1 Render `ApprovalRow` in `PiecePane` for the shown version, reading `status`/`approved_at` from the `["version", packageId, version]` query and calling `api.approveVersion` / `api.unapproveVersion`; invalidate progress, version, piece-versions and pieces queries; verify with `Workspace.test.tsx` tests for approve, approve an older version from the dropdown, unapprove, no control while building, and a refusal shown next to the control
- [x] 2.2 Verify the stand-alone inspector page is unchanged (`PieceInspector.test.tsx` passes unmodified)

## 3. Room pane

- [x] 3.1 Render `ApprovalRow` in `RoomPane` for the chosen composition version, reading `status` from `room.versions` and approval from `room.approved_version`, calling `api.approveCompositionVersion` / `api.unapproveCompositionVersion`; invalidate progress and compositions queries; verify with `Workspace.test.tsx` tests for approve, unapprove and the unapproved-placed-piece refusal
- [x] 3.2 Verify approving from either pane sends no chat message (test asserts no POST to the thread's messages)

## 4. Checks

- [x] 4.1 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`; all pass
- [x] 4.2 Browser pass: in the Workspace, approve and unapprove a piece version and a room version from the panes, confirm the dropdowns, flyouts, Pieces and Rooms pages agree after each step, and record the result in this file (no render is triggered, so no tier applies)
  Browser pass 2026-10-17. Headless Chrome (playwright-core 1.64, chrome-headless-shell 1243). Scratch DB `home_renovation_check_approval`, cloned from the owner's database and dropped afterwards, with the render root copied into the scratchpad. Backend from a HEAD worktree on 8100: the working tree's backend did not import because of another change in progress, and this change touches no backend code. Offload, gateway probe and Langfuse were off. Vite from the working tree on 5180 (`API_PROXY`). The owner's 8000 and 5173 servers were not touched. No render.
  - Conversation "Murphy bed", Chat and piece, `?inspect=murphy-bed/8`: the pane showed "Approved version 8" and "Unapprove version 8". Unapprove was refused next to the control ("murphy-bed version 8 is placed in the approved room composition Wohnen version 11; unapprove Wohnen version 11 first"), and v8 stayed approved.
  - Chose version 7 in the pane's dropdown and approved it. The dropdown read "Version 7, built, approved" and "Version 8, built". The Piece flyout read "Approved version 7", with "Approve version 8". Approving v8 again from the pane restored it.
  - Chat and room: the pane showed `Wohnen` "Version 11" with "Approved version 11" and "Unapprove version 11". Unapproving changed the row to "Version 11 is not approved." and the option to "Version 11". Approving again restored "Version 11 (approved)", and the Room flyout read "Approved version 11", "Unapprove version 11".
  - Non-GET requests were only the login and the approval PUT/DELETE calls; no turn was sent.
  - Not checked live: the Pieces and Rooms pages after a change in the same page session. They share the invalidated `pieces` and `compositions` queries.
