## 1. Geometry

- [x] 1.1 Add `segment_distance` and `polygon_distance` to `app/blender/room_contract.py`. Verify with unit tests: parallel, crossing, touching and corner-to-corner cases, and 0 for intersecting shapes.
- [x] 1.2 Add `compositions.gaps_of(document, item)` and `GapRefused`: wall gaps for every wall, item gaps (plan, or vertical clearance when stacked), ceiling and underside, whole millimetres. Skip hidden items and LED strips as neighbours; refuse unknown, ambiguous, plan-less and apartment-scope cases with a reason. Verify with the spec scenarios: the Wohnen bed gives 700 / 1300 / 0 mm and 1800 mm to the ceiling; the hung shelf gives 750 mm vertical; two "Chair" items are refused with both ids.

## 2. Tool

- [x] 2.1 Add `measure_gaps` to `plugins/room_version_dimensions/` (tool and manifest), scoped like `read_room_version_dimensions`. Verify with `db_session` tests: a stored composition version is measured; another room is refused; an apartment is refused; an unknown version answers it cannot be measured; nothing is written.
- [x] 2.2 Bind `measure_gaps` in the `designer.md` and `researcher.md` headers and add the one-sentence instruction. Verify that `load_instructions` accepts both files and that the tool appears in both specialists' bound tools.

## 3. Saved-place line

- [x] 3.1 Extend `placement_note` with the end walls and their gaps from `gaps_of`, keeping today's line when the room or size cannot be read. Verify that the Murphy-bed setup gives "left end 700 mm from wall 3, right end 1300 mm from wall 1", that the hung-sideboard scenario still passes, and that a missing room keeps the old line.

## 4. Benchmark

- [x] 4.1 Add a benchmark case: a seeded Wohnen composition version with a bed, a wardrobe and a hung shelf; ask for the gap to a wall, to the wardrobe and to the ceiling; check that `measure_gaps` was called and each figure stated. Keep the Murphy-bed case.
- [x] 4.2 Run `uv run pytest --benchmark tests/test_benchmark_agents.py` once (`TODO(user)`: a few cents) and record the outcome. 2026-10-19: the first run routed the room-version question to the Builder, which guessed (1500 / 500 / 200 mm); after the `foreman.md` routing line, two runs passed 3/3.

## 5. Checks

- [x] 5.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (alone, on the isolated test database), and verify both are clean apart from failures that already exist.
