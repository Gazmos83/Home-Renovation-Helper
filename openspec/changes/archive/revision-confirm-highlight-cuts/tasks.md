## 1. Revision confirmation

- [x] 1.1 Stop appending `derived_changes` effect lines in `revise_package` `preview`. Verify: preview tests show change lines and no `Cut list:` / `Hardware:` lines; design-rule warnings and version-limit heads-up still appear when they apply.
- [x] 1.2 Update backend tests that expected Cut list / Hardware lines in the revision confirmation (e.g. divider / fix-shelf preview cases) to match change-lines-only. Verify: `uv run pytest` on the touched tests passes.

## 2. Version baseline for the inspector

- [x] 2.1 Expose `revised_from` on the version read response (`describe_version` / piece version list) from the house-file row. Verify: API tests show the field for a revised version and null for version 1 / unknown row.
- [x] 2.2 Add `revised_from` to the frontend `VersionInfo` type. Verify: TypeScript build / existing piece-inspector tests still type-check.

## 3. Inspector red highlight

- [x] 3.1 In `InspectorView` / `CutListTables`, load the revised-from version's `spec.json` when present and mark part rows (new or `l`/`w`/`t`/`qty` changed) and hardware rows (new or `qty` changed) in red. Verify: unit tests cover new divider red, changed confirmat red, unchanged rows normal, version 1 no red.
- [x] 3.2 Record a browser pass: open Cut list on a revised built version and confirm new/changed rows are red; open version 1 and confirm no red. Note date and steps under this task when done.
  Browser pass 2026-10-13: headless Chromium through Python Playwright (`uv run --no-project --with playwright`), scratch database `home_renovation_rch_ui` (dropped afterwards), seeded `highlight-bench` v1/v2 with differing `spec.json` (new divider, confirmat 24→28) and `revised_from=1` on v2, backend on 8100 and Vite on 5180 (`API_PROXY`); the owner's 8000 and 5173 were untouched. No build or render. Signed in via session cookie; Cut list on v2 showed `cabinet-divider` and confirmat rows with `data-changed` and `text-destructive`, unchanged `cabinet-side` without; Cut list on v1 had no changed rows.
