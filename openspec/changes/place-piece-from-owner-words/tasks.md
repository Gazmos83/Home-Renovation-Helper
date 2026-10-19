## 0. Order

- [x] 0.1 Confirm that `view-piece-in-room` and `rooms-only-renders` are archived (`openspec list` shows neither) before starting; otherwise stop and ask the owner.

## 1. Stated placement values (`ask_placement`)

- [x] 1.1 Add `wall`, `distance_mm`, `from_wall` and `gap_mm` to `AskPlacementArgs`, keeping only numbers found in `ctx.last_message`. Verify with unit tests in `tests/test_ask_placement.py`: a number in the message is kept, and an invented one is dropped and asked.
- [x] 1.2 Convert `from_wall` (next wall = left end, previous wall = right end, any other wall refused with a plain note). Verify with tests: "wall 2 0 mm from wall 3" gives 0 from the left; "300 mm from wall 1" on a 5700 mm wall with a 1200 mm piece gives 4200; "from wall 4" asks the distance.
- [x] 1.3 Make `preview` return `None` when all values are kept and otherwise only the missing questions, each with an internal key. Make `run` merge answers by key. Verify with tests for the no-pause, wall-only and hung-gap-only cases. The existing question-text tests stay green.

## 2. Room proposal from the saved place

- [x] 2.1 Add `with_saved_place` to `compose_room` and the item builder in `app/compositions.py` (latest room composition, minus the bound piece, plus its stored placement). Verify with tests: the bound piece is added, an existing entry is moved, a missing placement is refused without a pause, and passing `items` together with the flag is refused.
- [x] 2.2 Add the `approve_version` plugin (manifest, Designer, not toggleable; gated confirmation "Approve version N of <name>?"; `house_file.approve_version` on yes; an already approved version is refused). Make `compose_room`'s approval refusal on the `with_saved_place` path point to it. Verify with tool tests for yes, no and already approved.

- [ ] 2.3 Show wall placements in the room proposal's summary and table as the owner numbers walls (from 1) with the distance from the left end. Verify with `tests/test_compose_room.py`: the scenario "Wall placement in the owner's terms", and existing summary assertions updated to the new wording.

## 3. Routing and instructions

- [x] 3.1 In `backend/app/agent/foreman.py`, route every `views_in_room` turn to the Designer, remove `after_designer`'s Builder hand-off and the Builder's in-room note, and reword the Designer note (no place → `ask_placement` with stated values; saved place → `compose_room` with `with_saved_place`). Rewrite `tests/test_view_in_room.py` to the new flow; it passes.
- [x] 3.2 Update `instructions/designer.md` (pass stated values and `from_wall`; a placement turn ends with the room proposal; never mention renders) and `builder.md` if it references the in-room still. Verify with `tests/test_instructions.py` assertions.

- [x] 3.3 Route a hang request with no engineering term to the Designer as a view-in-room turn (`engineering_chat.hang_request`, shared `HANG` used by `ask_placement`), and accept a decimal `mount_height_mm` in the composition contract. Verify with `tests/test_view_in_room.py` ("Can you hang it now?" with the model choosing Intake, with no flag, the help flag or the engineering flag), `tests/test_placement_request.py` and `tests/test_composition_contract.py` (1800.0 under a 2600 mm ceiling).

## 4. Benchmark

- [x] 4.1 Add the deterministic end-to-end test `tests/test_place_from_owner_words.py` (fake models scripted for the Foreman and the Designer) for "Please place the sideboard along wall 2 0 mm from wall 3." It covers the approved case (no question set, placement stored at wall 2 / 0 mm, `compose_room` pause, no `render_turntable`, no "render" in the reply) and the unapproved case (`approve_version` pause first, then `compose_room` after yes). Verify that it passes in the normal suite.
- [x] 4.2 Add `--benchmark` to `backend/conftest.py`, the `benchmark` marker to `pyproject.toml`, and `tests/test_benchmark_agents.py` with the live placement case (real routed models, seeded `Wohnen` and an approved built sideboard, builds stubbed, no confirmation resumed, step-naming failure messages). Verify that `uv run pytest -m "not slow"` skips it, and that `uv run pytest tests/test_benchmark_agents.py --benchmark` passes once on the owner's key. Report its result and cost to the owner. No tier: this case never renders. (First live run failed at 'question set': the model passed `hung: true`. Fixed by the owner-words-or-spec rule, design 6a; the second run passed.)

## 5. Checks

- [x] 5.1 Run `uv run ruff check .`, and run `uv run pytest -m "not slow"` on a throwaway `TEST_DATABASE_URL` with the RunPod and offload test files skipped. Report the results. (2026-10-19: 3140 passed; the 2 expected failures were updated; 4 remaining failures are in other uncommitted work: pricing wording x3, engineering migration head x1.)
- [ ] 5.2 Browser pass in the "Sideboard (copy)" conversation, **no render tier**. Send "Please place the sideboard along wall 2 0 mm from wall 3." Expect no questions, the approve confirmation (v1 is unapproved), then the room proposal, and after `yes` the new Wohnen version in the room inspector. No render is offered. Also (folded in from `rooms-only-renders` 3.2): ask the Builder to render a piece and see the plain refusal offering the room; the piece pane and the Pieces page show no renders or looks.
