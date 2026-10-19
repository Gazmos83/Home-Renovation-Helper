## Why

Owner questions such as "How much space is between the Murphy bed and wall 3 in Wohnen v12?" are answered today by the model doing geometry in its head. Its answers have been inconsistent. On 2026-10-19 the agent benchmark caught the Designer giving 700 mm for wall 1 when the figure is 1300 mm: the saved-place line says "700 mm from its left end" but never says which wall that end meets. The owner asked for the figures to be computed in code (2026-10-19).

## What Changes

- **Gap calculator (code, no model).** One function reads a composition version's stored document and gives, for one item (a piece or a library model), whole-millimetre clear distances:
  - to every wall of its room, measured from its footprint;
  - to every other item in the same room, measured in plan, plus the vertical clearance when one hangs above the other;
  - to the ceiling (room height minus the item's top), and its underside height when it is hung.
- **New read-only tool `measure_gaps`** for the Designer and the Researcher, in the existing `room_version_dimensions` plugin. The model names a composition version and an item, by id or name. The room comes from the conversation, as `read_room_version_dimensions` does. The tool writes nothing.
- **Clearer saved-place line.** The bound piece's saved place in its room now names the wall at each end of the piece and the code-computed clear gap to it: "left end 700 mm from wall 3, right end 1300 mm from wall 1".
- **Instructions.** The Designer and Researcher quote a gap from `measure_gaps` or from the saved-place line, and never work one out themselves.
- **Benchmark.** The Murphy-bed case stays. A new case asks for gaps in a seeded composition version (to a wall, another item and the ceiling) and checks that `measure_gaps` was called and the figure stated.
- **Not changed:** placement, room fit, composition validation, rendering.

**Ladder step:** none (no Blender). **Agents:** Designer and Researcher gain one read-only tool; the saved-place note changes wording. **Render guard and bpy allow-list:** unaffected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `room-composition`: adds the requirement that an item's gaps in a composition version can be measured from the stored document.
- `design-agents`: the saved-placement note names the walls at both ends with their clear gaps; gap figures come from code, not from the model.

## Impact

- **Backend:** `app/compositions.py` (gap function next to `room_dimensions`), `app/blender/room_contract.py` (distance helpers), `plugins/room_version_dimensions/` (new tool and manifest entry), `app/agent/foreman.py` (`placement_note`), the Designer and Researcher instruction files.
- **Tests:** unit tests for the geometry and the tool; the benchmark gains one case.
- **No migration, no new dependency.**
