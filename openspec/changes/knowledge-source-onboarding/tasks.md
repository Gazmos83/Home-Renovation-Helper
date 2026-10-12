## 1. Backend

- [x] 1.1 Add a read-only route listing catalogue entries without a matching registered version; verify an already-registered entry is absent and an edited one is listed.
- [x] 1.2 Add `engineering_link_max_bytes` and an ingest-from-link route using the existing ingest and fetcher; verify missing rights, robots refusal, size cap, changed hash and redirect are refused and the browser upload limit is unchanged.
- [x] 1.3 Verify registration still refuses `approved_for_embedding` and any non-unverified status from catalogue data.

## 2. Frontend

- [x] 2.1 Add Register buttons for unregistered entries; verify the result is metadata-only and unverified.
- [x] 2.2 Add grant presets, prefilled reviewer and an editable draft evidence note; verify no preset is preselected, nothing is stored without Record approval and the sent grants match the preset.
- [x] 2.3 Add Ingest from official link with refusal reasons displayed; verify it is disabled without the required rights.
- [x] 2.4 Prefill the technical-review form; verify it still needs its own click and does not alter rights.

## 3. Verification

- [ ] 3.1 Automated checks pass (backend engineering tests, ruff, pnpm test, lint, build). Still open: browser-check the full flow on the USDA handbook before it counts as done.
