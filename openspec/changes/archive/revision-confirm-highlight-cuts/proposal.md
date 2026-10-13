## Why

When confirming a revision, the card lists every derived cut-list and hardware line as well as the owner's change lines, which buries the decision. The owner needs a short confirmation of what they asked for, and a clear place later — the inspector Cut list — to spot which parts and hardware actually changed.

## What Changes

- **Revision confirmation is change lines only.** The `revise_package` confirmation keeps the owner's change lines (and the existing design-rule warnings, version-limit heads-up, and auto-fit lines). It no longer appends derived "Cut list:" / "Hardware:" effect lines. **BREAKING** for anyone relying on those lines in the confirmation text; the cut list and hardware stay inspectable after the build.
- **Inspector highlights new and changed cuts and hardware in red.** On a built version that was revised from another, the Cut list tab marks every cut-list row that is new or whose size/quantity changed, and every hardware line that is new or whose quantity changed, against the version it was revised from. Unchanged rows keep normal styling. Version 1 and a version with no readable prior document show no red rows.
- Ladder step: none (UI and confirmation text only). Agents: Designer confirmation surface; Studio inspector. Render guard and bpy allow-list: unaffected.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `furniture-packages`: replace the requirement that the revision preview lists hardware and cut-list changes with one that the confirmation lists only the change lines (plus existing warnings / heads-up / fit lines).
- `studio-ui`: the inspector Cut list tab highlights added and changed parts and hardware in red against the revised-from version.

## Impact

- Backend: `backend/plugins/revise_package/tool.py` preview summary; tests that assert Cut list / Hardware lines in the confirmation; possibly expose `revised_from` on the version read API for the inspector baseline.
- Frontend: `CutListTables` / `InspectorView`, types in `api.ts`, Cut list tests, and a recorded browser pass for the highlight.
- `derived_changes` can remain for tests and any non-confirmation use; it stops feeding the confirmation summary.
