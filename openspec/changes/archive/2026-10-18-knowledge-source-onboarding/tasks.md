## 1. Backend

- [x] 1.1 Add a read-only route listing catalogue entries without a matching registered version; verify an already-registered entry is absent and an edited one is listed.
- [x] 1.2 Add `engineering_link_max_bytes` and an ingest-from-link route using the existing ingest and fetcher; verify missing rights, robots refusal, size cap, changed hash and redirect are refused and the browser upload limit is unchanged.
- [x] 1.3 Verify registration still refuses `approved_for_embedding` and any non-unverified status from catalogue data.

## 2. Frontend

- [x] 2.1 Add Register buttons for unregistered entries; verify the result is metadata-only and unverified.
- [x] 2.2 Add grant presets, prefilled reviewer and an editable draft evidence note; verify no preset is preselected, nothing is stored without Record approval and the sent grants match the preset.
- [x] 2.3 Add Ingest from official link with refusal reasons displayed; verify it is disabled without the required rights.
- [x] 2.4 Prefill the technical-review form; verify it still needs its own click and does not alter rights.
- [x] 2.5 Say why Record approval is disabled while the draft marker remains (asked for 2026-10-17); verify in `Knowledge.test.tsx` that the message is shown next to the button and described by it while `[STATE YOUR BASIS HERE]` is in the note, and goes once it is replaced.

## 3. Verification

- [x] 3.1 Automated checks pass (backend engineering tests, ruff, pnpm test, lint, build). Still open: browser-check the full flow on the USDA handbook, on the Engineering Knowledge view (`/admin/design-knowledge/engineering`), before it counts as done.
  Automated checks 2026-10-17 (passed): backend engineering and kitchen-engineering tests 117 passed (throwaway test database, dropped afterwards); `ruff check .` clean; `pnpm test` 504 passed in 52 files; `pnpm lint` clean; `pnpm build` succeeded. The browser check on the USDA handbook is still open.
  Browser check in progress 2026-10-17 (owner): steps 1–3 done on the Wood handbook (registered, Local use approval recorded). Step 4, Ingest from official link, first failed with "RulesUnavailable": `KnowledgeFetcher._get` rebuilt a gzip-decoded response with its `Content-Encoding` header, so robots.txt was decoded twice (`DecodingError`). Fixed by dropping `Content-Encoding`/`Content-Length` from the rebuilt response; regression test `test_compressed_rules_and_pages_are_read_once_decoded`. With the fix, research.fs.usda.gov's robots.txt (`User-agent: *` / `Disallow: /`, only named crawlers allowed) refuses the service, so the link action correctly refuses with "host robots rules refuse this service". The handbook goes through the confined local-file CLI instead.
  Local-file CLI 2026-10-17: `ingest-file … pdf/fpl-gtr-282.pdf` (104 MB, 546 pages) failed with "DependencyError": the handbook is AES-encrypted with an empty open password, and pypdf needs `cryptography` for AES. Added `cryptography` to the backend dependencies; regression test `test_aes_encrypted_pdf_without_open_password_is_read`. The PDF's permission flags say no copying or extraction (accessibility extraction allowed); the owner's rights evidence is the basis for ingesting it.
  Re-run with `cryptography` 2026-10-17: `{"state": "published", "blocks": 550, "reason": null}`; the version is published with 550 chunks, all embedded locally.
  Browser check completed 2026-10-18 (owner): step 5 technical review recorded with grants unchanged; step 6 "Preview eligible evidence" for "shelf" listed 5 handbook passages locally (pages 514, 515, 516, 429, 430). Quality notes for a follow-up, not part of this change: each block is one whole page, every block is kind "table", pypdf layout mode interleaves the two text columns line by line, and the top scores are low (about 0.35).
