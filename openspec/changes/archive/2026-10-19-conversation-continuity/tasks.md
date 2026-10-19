## 1. Question-card answers count as the owner's words

- [x] 1.1 Tag question-form answers on the `ToolMessage`. Done by the existing code-written `additional_kwargs["answers"]` record (`_answered_rows`: answer rows or the declined text) that the tool node already stores for every `ask_owner`/`ask_placement` form; no new tag needed. Verified by `test_an_answered_form_is_kept_as_the_owners_words` in `test_foreman.py`.
- [x] 1.2 Extend `measurements.owner_texts_since_version` to include `owner_words` entries in order, never the question text. Verify in `test_measurements.py`: "1350 mm" from a form answer passes; "450 mm" found only in a question's text is refused.
- [x] 1.3 Add the owner's sentence (capped at 200 characters, neutralised) to the not-found and not-covered refusals. Verify in `test_measurements.py` that the "Measurement left out" refusal quotes "80 cm wide and 40 cm deep".
- [x] 1.4 In `instructions/designer.md`, say that form answers can be quoted, and that a height on a wall uses target `none` or the placement height. Verify with `test_instructions.py`.

## 2. The engineering reply no longer swallows ordinary requests

- [x] 2.1 Split `_ENGINEERING` in `app/engineering/chat.py` into hardware and load patterns. Add the span and sag terms, keep `engineering_intent` as their union, and add `revision_engineering`. Verify in `test_engineering_chat.py`:
  - "add a wall hanger to the sideboard" is not a revision engineering turn;
  - "add a wall hanger that holds 30 kg" is;
  - "What's the allowable shelf span for particle boards?" is engineering by code;
  - every existing case is unchanged.
- [x] 2.2 Use `revision_engineering` in the Foreman when the message asks to revise the bound piece, and store `engineering_by_code` in state. Verify in `test_foreman.py` that "Yes, please add a wall hanger to the sideboard" with a bound piece routes to the Designer as a non-engineering turn.
- [x] 2.3 Add the single ordinary retry in the specialist `agent` node for a model-only flag whose answer renders to `SHORT_STATUS`. Verify in `test_foreman.py` with a fake model:
  - the space question gets the ordinary answer;
  - "Is the shelf safe for 40 kg?" still gets only `SHORT_STATUS`;
  - the retry happens at most once.

## 3. A no to the room question is a decline

- [x] 3.1 Extend `room_answer` to read a reply after `ROOM_QUESTION` with `ROOM_NO_WORDS`, so `load_house` saves the decline. Verify in `test_foreman.py` that "No room for now, design it without one." after "Which room is this for?" sets `room_declined`, and that the next turn "Yes, go on with the design." gets neither room question. "Wohnen" after the question still confirms the room.

## 4. A wall-hung piece keeps its height (generator extension)

- [x] 4.1 Add optional `mount_height_mm` to a piece's wall placement in `composition_contract.py`. Allow it only on `piece` with a wall placement, refuse it above the ceiling, resolve it to `base_mm`, and use height ranges in the clash test when either item is hung. Verify in `test_composition_contract.py` with the four room-composition scenarios (kommode below accepted, tall stand-in clash, above ceiling, stand-in refused) and the door scenario.
- [x] 4.2 Add optional `mount_height_mm` to `room_contract` placement with the ceiling check, and lift the package by it in `build_room_scene.py`. Verify with a room-contract unit test, and with one `--blender` test (`test_room_generator_blender.py`) that renders a `draft` room still of a hung fixture piece; `scene.json` records `mount_height_mm` and the measured `package_lowest_mm` (300 mm).
- [x] 4.3 Store the height in the placement JSON. Give `room_fit` an optional `mount_height_mm` (checked against the owner's words, as a `none` measurement) and `ask_placement` an optional `hung` with a code-written height question. Verify in `test_room_fit.py` and `test_ask_placement.py`: a hung placement is saved with its height; a height not in the owner's words is refused.
- [x] 4.4 Make `compose_room` accept and pass `mount_height_mm` on a piece's wall placement. Verify in `test_compose_room.py`, and with one `--blender` composition build (`test_composition_blender.py`) whose hung piece's world z equals the height. Headless build only, no render.
- [x] 4.5 Format the saved placement line in `load_house` and add it to the Designer's and Builder's notes. Verify in `test_foreman.py` that the Builder's system text for the hung sideboard fixture states wall 2, 0 mm and 1700 mm.
- [x] 4.6 In `instructions/designer.md` and `instructions/builder.md`, cover a hung piece: use `hung` or `mount_height_mm`, and never ask for a figure the placement line states. Verify with `test_instructions.py`.

## 5. Whole check

- [x] 5.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` on a throwaway `TEST_DATABASE_URL`, skipping the offload and pod test files. Run the `--blender` tests from 4.2 and 4.4. Record the results here.
  - 2026-10-18: `ruff check .` clean. `pytest -m "not slow"` (offload/pod files skipped) on `hra_test_continuity`: 3080 passed, 55 skipped, 4 failed. The 4 failures are outside this change and come from other uncommitted work in the tree: `test_pricing.py` (2) and `test_pricing_api.py` (1) expect the old "approve it first on the Pieces page" wording that the modified `app/pricing/pricing.py` changed; `test_engineering_registry.py::test_migration_is_separate_from_legacy_chunks` expects head `0029_thread_room_declined`, the tree has `0031_blueprints`.
  - `--blender`: `test_composition_blender.py -k "hung or every_item"` 2 passed; `test_room_generator_blender.py -k "hung or 800_square"` 2 passed (draft still).
- [x] 5.2 Browser pass in the Studio: replay the sideboard flow in a new conversation:
  - "No room for now";
  - a form answer for the width;
  - "add a wall hanger";
  - hang it above the kommode at the ceiling;
  - a `draft` room still through the guard.

  Confirm no question repeats and the still shows the hung sideboard.
