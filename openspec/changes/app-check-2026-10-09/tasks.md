## 0. Before applying

- [x] 0.1 Check that `git status` shows no uncommitted edits under `backend/app/agent/`, `backend/plugins/` or `frontend/src/` from earlier changes. Report any to the owner before section 1 starts.

## 1. Stored rooms are never reused silently (house-file, apartment-shell)

- [x] 1.1 In `backend/app/agent/house_file.py`, make `upsert_room` keep the room's apartment when `apartment_id` is not passed, and make `run_brief` (`plugins/intake/tool.py`) rely on that. Verify with a test: correcting `Küche`'s height through `record_brief` keeps it in `Wohnung`.
- [x] 1.2 Extract the measured-room delete's cleanup (unassign pieces, clear conversations, remove the room composition, its records and its folders) into a helper the room delete route keeps using unchanged. Verify that the existing room delete tests pass unchanged.
- [x] 1.3 Give `upsert_apartment` a replace mode (design decision 2): it computes the changed, new and removed rooms, checks overlap among the read's rooms only, and deletes removed rooms through the 1.2 helper. Verify with house-file tests: `Bad` is removed and `towel-rack` becomes unassigned; overlap ignores removed rooms; a removed room with a running composition build refuses and changes nothing.
- [x] 1.4 In `record_plan`'s preview, when the apartment exists, show "replaces stored `<name>`", each room's stored and read size, the new rooms, and the removed rooms with their pieces and composition. Make `run_plan` use replace mode. Verify with `test_intake*` tests covering the spec's "Plan read again", "Removed room deleted on yes" and "Re-read while a composition builds" scenarios.
- [x] 1.5 Reword `intake.md`: "Read the house file first. Never ask for what it already says" applies to the conversation's confirmed room only. Add: a stored room or apartment is offered through `confirm_room` with its measurements, never assumed. Verify with `test_instructions.py` checking both rules.
- [x] 1.6 Verify with a Foreman test: a new conversation after the original one is deleted, with stored `Wohnung` and the same blueprint attached, raises no number from `Wohnung` before a confirmation, and its house note names no stored room.

## 2. Room-first design (design-agents)

- [x] 2.1 Add `composes_room: bool` to the Foreman's `Decision` and to `foreman.md`. Change `compose_ready` as in design decision 3. Verify with `test_foreman.py`, using a stubbed decision: "Compose without naming the room" goes to the Designer; "Piece wish still goes to Intake" goes to Intake; with no confirmed room, `composes_room` still gives the room question.
- [x] 2.2 Add the room-first path to `intake.md`: confirm the room, ask what it should hold, never ask for a piece's purpose, size or budget, never `record_brief` a room-only wish, and hand off to composing. Verify with `test_instructions.py`.

## 3. Revision context (design-agents)

- [x] 3.1 Add the Designer's template note only when the conversation has no active build. Verify with `test_foreman.py`: a revision turn's Designer prompt contains no `Template custom-build`, and a new-piece turn's does.
- [x] 3.2 Add the envelope line to `piece_note`. Verify with `test_piece_note.py`: "envelope 2206 × 2238 × 400 mm" appears first.

## 4. Composition model and surface map (room-composition)

- [x] 4.1 Read the object naming in `build_shell.py` and `_composition.py` for apartments, and note it here. If apartment walls are not per-room identifiable, rename them `<room>:Wall_<i>_<n>` in the generator. Verify with the `--blender` shell build test.
  - Note: a single room's walls are `Wall_<edge index>_<n>` (plus `_lintel_`/`_sill_`), with `Floor` and `Ceiling`. An apartment's walls are `Wall_<wall id>_<n>`, with ids `wall-1…` numbered across the apartment, and floors and ceilings are `Floor_<room>`/`Ceiling_<room>`. The shell context maps each wall id to its rooms, so no rename was needed: `apartment_wall_labels` numbers each room's walls from it, and a shared wall is labelled by the first room it names. The shell generator is unchanged, and the `--blender` shell build tests pass.
- [x] 4.2 In `build_composition.py`, export `model.glb` after `model.blend`, as the piece build does, and write `surfaces` to `report.json` (design decision 6). Extend `verify_composition` so every mesh is mapped exactly once. Verify with `uv run pytest -m blender` composition tests: a four-walled `Hall`, empty and with a stand-in, gives wall 1–4, floor, ceiling and items, and the GLB has every mapped mesh. No render runs.
- [x] 4.3 In `app/api/compositions.py`, return `model` and `surfaces` URLs for the latest version when the files exist, and none for an older version without them. Verify with `test_compositions_api.py`.

## 5. Measurement check (design-agents)

- [x] 5.1 Write `backend/app/agent/measurements.py` with `lengths()` and `check()` (design decision 5). Verify with a new `tests/test_measurements.py`: "80 cm", "0,8 m", "800mm", "5 cm wider", "2 cm less deep", text with no unit, and every scenario of the spec requirement "A revision carries the owner's measurements and code checks them", including the `none` entry.
- [x] 5.2 Pass the owner's messages since the last created revision into the tool context from the specialist loop (code-composed). Verify with `test_foreman.py`: a thread with a created v2 passes only the messages after it.
- [x] 5.3 Add `requested` to `RevisePackageSchema` and run `check()` in `revise_package` before the preview. A refusal raises no confirmation. Update `designer.md` to fill `requested` with every length the owner gave. Verify with `test_revise_package.py` (absolute, invented value, relative, left out, foreign quote) and `test_instructions.py`.

## 6. Stop and edit (homeowner-chat)

- [x] 6.1 Add the per-thread stop registry, the check in `run_events`, and `POST /threads/{id}/turns/stop` (design decision 8). Verify with `test_chat_api.py`, using a stub graph: stop before any tool gives `stopped` and a history without the message; stop after a build tool reports the build; stop with nothing running gives 409; no session gives 401.
- [x] 6.2 Add `POST /threads/{id}/turns/latest`, a streamed rewind plus a new turn. Verify with `test_chat_api.py`: "Message corrected", "Version already created" (the response names `bench` v3, which still exists), an older message gives 409, a pending confirmation gives 409, and uploads carry over.

## 7. Studio (studio-ui)

- [x] 7.1 Pricing on the Pieces page: add `pricings`/`createPricing` to `lib/api.ts`, reading `result`'s line fields from `app/pricing/pricing.py`, and a Pricing dropdown per approved version in `routes/Pieces.tsx`. Verify with `Pieces.test.tsx` covering the four spec scenarios and that no GPU cost appears.
- [x] 7.2 Inspector version switcher and follow-newest (design decision 9) in `InspectorView`, `PieceInspector.tsx` and the split view in `Conversation.tsx`. Verify with Vitest: choosing v1 updates the URL; a polled v4 switches the view and the `inspect` parameter, and shows the building state, then the model.
- [x] 7.3 Chat Stop and Edit in `Composer.tsx` and `Conversation.tsx`, with `AbortController` on the stream and the edit warning. Verify with Vitest: Stop calls the stop route and frees the composer; only the latest owner message offers Edit; Edit sends to the latest-turn route; Cancel sends nothing.
- [x] 7.4 Room 3D view on the Rooms page (design decision 7), reusing `InspectorCanvas`/`PieceModel` with the surface map, lazy-loaded, ceiling off by default, "All walls" switch, still shown for versions without `model.glb`. Verify with `Rooms.test.tsx` covering the three new spec scenarios.

## 8. Browser passes and close-out

- [x] 8.1 Browser pass on a scratch database and spare ports, leaving the owner's servers alone. Check:
  - Rooms 3D, with walls switched off and the ceiling default, on a composition rebuilt headless (no render, no tier);
  - the inspector switcher, and following a new version after a confirmed revision;
  - chat Stop and Edit;
  - Pieces pricing, on an approved version with a complete pricing and an incomplete one.

  Record the pass here.

  Browser pass 2026-10-09. Headless Chrome through Python Playwright, run with `uv run --with playwright` so `uv.lock` is unchanged. Scratch database `home_renovation_appcheck_ui`, with render and upload roots in the session scratchpad. Backend on 8100, Vite on 5180 (`API_PROXY`). The owner's 8000 and 5173 servers were untouched. Live models through the gateway for the chat steps.
  - **Data:**
    - `hall-bench` v1 was built from the custom-build template through `POST /packages`.
    - Room `Hall` (4000 × 3000 mm, one door) holds the bench.
    - Composition `Hall` v1 (the bench plus a sofa stand-in) was built headless by `build_composition.py`: no render, no tier.
    - The owner's dev database has no captured home store, so the store and the price entries are the fixtures `tests/test_pricing.py` uses. This is test data, not toom data.
  - **Rooms 3D:**
    - The card offered "Open the 3D view of Hall". The report was fetched only once it was opened.
    - Switches: All walls, wall 1–4, floor, ceiling, items. The ceiling starts off.
    - The first pass showed the inspector's low Iso, which cannot see into the room. The room view now has a higher Iso (`ROOM_ISO`). From it the bench and sofa are seen from above.
    - Wall 3 off hid only that wall, and All walls hid all four.
    - Blueprint and Plan work.
    - At phone width (375 px) the controls wrap with no horizontal scroll.
  - **Inspector:**
    - On the page, the switcher lists "Version 1, built, approved".
    - In the split view, the owner wrote "Make the cabinet 5 cm wider". The Designer restated the list and asked if it was complete; the owner said yes.
    - The card showed "cabinet: width 800 → 850", so the measurement check passed. After yes the view switched to v2 with "Showing version 2, the newest", the `inspect` parameter read `hall-bench/2`, and v2's model appeared (W 850).
    - Timing, measured from a version created by `PUT /packages/hall-bench/spec`:
      - With the Cut list tab open, the view followed in 2.1 s.
      - With a model drawn in the 3D view, it took 8.4 s. The backend log shows a 7.7 s gap between two 3 s polls while headless software WebGL (SwiftShader) blocked the page.
      - Still to check on a GPU browser (see 8.3).
    - A hand-chosen v1 stayed in place for 7 s while nothing newer appeared.
  - **Chat:**
    - Stop during a running turn ended it with "Stopped. This message and its replies were removed.". The words came back to the composer, and after a reload the thread was empty.
    - Exactly one Edit was offered, on the latest message. It put the text in the composer with the warning.
    - "Send edit" replaced the message: the new question got its own answer (1800 mm tall), the old one was gone, and this held after a reload.
    - The backend log has no rewind warning.
  - **Pieces pricing (`hall-bench` v1, approved):**
    - The dropdown showed an incomplete pricing (168,40 €, "Pricing incomplete", naming "Concealed hinge 110°" and "all edges" / "front edge").
    - After the hinge and band entries were added, "Price this version" created a complete 249,40 € pricing, listed first and selected, with sheets, cuts and hardware.
    - Choosing the older pricing showed it again.
    - Unapproved v5 says it must be approved first and offers no action.
    - No GPU, token or model text appears.
    - At 375 px the pricing select overflowed the card by 44 px. Fixed with `min-w-0`/`max-w-full`; now no horizontal scroll.
- [x] 8.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, the `--blender` composition tests, `pnpm lint`, `pnpm test` and `pnpm build`. Verify all pass, and report any failure with its output.
  - Results 2026-10-09:
    - `ruff check .`: clean.
    - `pytest -m "not slow"`: 1968 passed, 31 skipped.
    - `--blender` `test_composition_blender.py` and `test_shell_generator_blender.py`: 12 passed. The two existing draft-still tests render at tier `draft`.
    - `pnpm lint`: clean.
    - `pnpm test`: 166 passed.
    - `pnpm build`: built. Its warning about chunks over 500 kB comes from the lazy three.js chunk (`InspectorCanvas`, about 1 MB), which was already split out before this change.
- [x] 8.3 Tell the owner that existing compositions need composing again to get the 3D view. List any finding left open.
  - Told the owner in the closing summary. Open findings:
    - **Inspector follow timing:** with a model drawn in headless software WebGL, the view followed after 8.4 s, not within 5 s. Without a canvas it took 2.1 s. Check on a real browser with a GPU.
    - **Pricing in the owner's database:** it has no captured home store, so `POST …/pricings` answers 404 `unknown_store` until the store is captured (`python -m app.ingestion --store`, roadmap step 5).
    - **An interrupted edit:** if an edit is stopped or fails after its rewind, the replaced message is gone. The composer gives the words back as a new message, not as an edit.
