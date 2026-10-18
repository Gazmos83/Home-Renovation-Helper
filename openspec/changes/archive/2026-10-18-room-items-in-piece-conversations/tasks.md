## 1. House file

- [x] 1.1 In `backend/app/agent/house_file.py`, make `compositions()` return `approved_items` from the approved version's `input.json`, and make `placed_items` copy `width_mm`, `depth_mm`, `height_mm` for model and stand-in items. Write house-file tests: approved items differ from a newer draft's; no approval gives no `approved_items`; an unreadable file gives an empty list (run deferred, see 3.1).

## 2. Prompts and routing

- [x] 2.1 In `backend/app/agent/prompts.py`, regroup `composition_note`: approved items first, a newer draft labelled "draft, not approved", or the latest labelled "not approved" when nothing is approved; model and stand-in sizes shown. Write prompt tests for the three layouts and for neutralised names.
- [x] 2.2 In `backend/app/agent/foreman.py`, add `composition_note` to Intake's notes and to the Foreman's routing prompt. Write foreman tests for "A new piece conversation sees the approved layout" and "No room, no composition".

## 3. Checks

- [x] 3.1 Run `uv run ruff check .` in `backend/`. pytest deferred to the batch check after the last change of the 2026-10-18 review batch (skip RunPod/offload tests, throwaway TEST_DATABASE_URL).
- [x] 3.2 Browser pass, with **no render tier**: in a new conversation, confirm `Wohnen` (approved composition with pieces and library models) and ask "what is already in this room?"; the reply names the approved items and their places. Then ask the Designer for a sideboard next to an existing item and check it names that item.
