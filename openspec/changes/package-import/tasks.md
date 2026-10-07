## 0. Preconditions

- [x] 0.1 Confirm that `piece-first-workflow` is applied: migration `0010_version_approval` exists, and `house_file.approve_version` exists. If `studio-chat-polish` has already landed, refresh `specs/plan-uploads/spec.md` against the live text (keep its note kind) and include `text` in the widened constraint. Verify with `openspec validate package-import --strict`.

## 1. Import document and template

- [x] 1.1 Add `app/design_import.py` with:
  - `ImportDocument`: strict, `extra="forbid"`, an optional `guide` of at most 40 notes of at most 500 characters, and `build`;
  - `parse_import`: the survey refusal first, then the wrapper, then the build through `validated_custom_build`;
  - `export_document`.

  Verify that `tests/test_design_import.py` covers:
  - a bare document accepted;
  - a wrapper with a guide accepted, and nothing read from the guide;
  - `survey` refused naming it and Intake;
  - an unknown wrapper field refused by name with no extension request;
  - `modules[0].bevel_mm` refused by name and recorded as a request;
  - several errors reported together;
  - `export_document` → `parse_import` round-trip equality on `custom-build.json` and `fold-down-desk.json`.
- [x] 1.2 Add `backend/fixtures/packages/templates/import-template.json`. Its guide ports the predecessor's build lines, edited for this schema, and adds three rules: return JSON only, no survey, unknown fields are refused. Its build equals `custom-build.json`. Verify with a test that the template parses, derives the starter's rows and hardware, has a build equal to `custom-build.json`, and has a guide naming the material slots, modules, fronts, extra parts, hardware, part overrides, and "JSON".
- [x] 1.3 Add the `GET /design-import/template` router: owner-gated, JSON with a download file name. Wire it in `main.py`. Verify that `tests/test_design_import_api.py` covers the download and 401 without the cookie.

## 2. Design uploads

- [x] 2.1 Make the upload changes:
  - add the `upload_max_design_bytes` setting (default 256 KiB, positive), in `config.py` and `.env.example`;
  - add `uploads.classify` for the `design` kind;
  - store design files as `<id>.json`;
  - serve them `application/json` with `nosniff`.

  Verify that the upload tests cover:
  - a design accepted with kind `design`;
  - a JSON array refused with 415;
  - `kind: room_scene` refused with 415;
  - invalid UTF-8 refused with 415;
  - an oversized design refused with 413, leaving no partial file;
  - the served content type;
  - images unchanged.
- [x] 2.2 Add migration `0011_design_uploads` to widen `ck_uploads_kind`. On downgrade it deletes `design` rows first. Verify that `tests/test_design_uploads_migration.py` upgrades, inserts a `design` row, downgrades and upgrades again with no drift.
- [x] 2.3 `_check_uploads` refuses a second design in one turn (422 `too_many_designs`), and `turn_max_images` counts images only. The attachment expansion names a design file with its upload id and never sends it. Verify that:
  - `tests/test_chat_api.py` covers two designs refused;
  - a foreman test asserts that the Designer's model call holds the note with the neutralised file name and upload id, and none of the document's text.

## 3. Agents

- [x] 3.1 Extract `create_piece`'s check, summary and create-and-record steps into functions in its module, without changing behaviour; the create step takes `changes`. Verify that `tests/test_create_piece*.py` and `tests/test_foreman.py` pass unchanged.
- [x] 3.2 Add the `plugins/design_import/` manifest (Designer, enabled by default, not toggleable) and the `import_design` tool. It covers:
  - checking the upload's thread and kind;
  - refusing when a piece is already bound;
  - `parse_import`;
  - the preview with the document name wrapped as untrusted;
  - on `yes`, recording the piece, version 1 with `imported from <name>`, the binding and the build;
  - `DECLINED["import_design"]` covering `no`.

  Verify that `tests/test_import_design.py` covers:
  - confirmed: piece, version, change line, thread bound, build queued with no render tier;
  - declined: nothing created;
  - another thread's upload refused;
  - an image upload id refused;
  - a bound piece refused;
  - a taken package id refused;
  - an invalid document refused without a pause;
  - an imported piece approved through `house_file.approve_version`.

  Verify also that `tests/test_plugin_manifest.py` loads the manifest.
- [x] 3.3 In the Foreman, `load_house` computes `design_attached`, and the router sends it to the Designer after the pending rule. Add `import_design` to `designer.md`'s header, with a paragraph on importing, relaying refusals for the other chat, and pointing to a new conversation when a piece is bound. Verify that:
  - `tests/test_foreman.py` routes a design turn in an empty thread to the Designer, and a pending confirmation still resumes in its specialist;
  - `tests/test_instructions.py` passes.

## 4. Export

- [x] 4.1 Add `GET /packages/{id}/versions/{n}/design` and `GET /packages/{id}/versions/{n}/bundle`, which is streamed, uses fixed member names, and answers 409 `not_built`. Verify that `tests/test_packages_api.py` covers:
  - the design download, with the file name and its round-trip through `parse_import`;
  - the bundle's exact member list, with and without a still;
  - 409 while `running`;
  - 404 for an unknown version;
  - 401 without the cookie.

## 5. Studio

- [x] 5.1 Add the `api.ts` URL helpers. On the Pieces page, add the template link with its how-to line, "Download design" per version, and "Download bundle" for succeeded versions. Verify that `Pieces.test.tsx` covers the links' `href`s and `download` attributes, and that the bundle is absent for a running version.
- [x] 5.2 In the conversation, the picker accepts `.json`; a design upload shows as a named chip and is sent with the turn; a 415 refusal is shown. Verify that `Conversation.test.tsx` covers the chip, the sent `upload_ids`, and the refusal.

## 6. Verification

- [x] 6.1 Run a browser check against the running backend:
  - download the template;
  - in a new conversation, attach a design file with one invented field and read the refusal;
  - attach a corrected file, answer `yes`, and see the build's screenshot in the project panel;
  - download the design and the bundle from the Pieces page;
  - import the downloaded design in another conversation and confirm the same overall size.

  No render is started (no tier). Record the check in the commit message.
  - Browser pass 2026-10-07: headless Chrome via playwright-core, with the API (port 8100) and Vite (port 5180) on a scratch database and scratch render and upload folders. Real routed models through OpenRouter.
    - The template downloaded from the Pieces page (14 guide lines).
    - In a new conversation, `wall-unit-draft.json` (`modules[0].bevel_mm` added) showed as a named chip. The turn went to the Designer, which relayed the refusal quoted for the other chat. The field was recorded as a generator-extension request, and nothing was created.
    - `wall-unit.json` previewed "Hall wall unit … 1200 × 2000 × 350 mm, 1 module, 5 cut-list rows, 3 hardware lines". `yes` recorded `wall-unit/v1`, bound the conversation, and the build succeeded; the screenshot showed in the project panel.
    - The design download is `wall-unit-v1.json` (`package_import`, no guide). The bundle `wall-unit-v1.zip` holds exactly the design, `cutlist.csv`, `hardware.csv`, `model.glb` and `screenshot.png`; no still, because none was rendered.
    - The downloaded design, imported in a second conversation as `wall-unit-copy`, stored a design identical to `wall-unit/v1` and built.
    - No render was started.
- [x] 6.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, and `pnpm lint && pnpm test && pnpm build`. Verify that all pass, and record the counts in the commit message.
  - 2026-10-07: ruff clean; `pytest -m "not slow"` 1481 passed, 29 skipped, 9 deselected; `pnpm lint` clean, `pnpm test` 64 passed, `pnpm build` ok. Two existing tests that pin the Designer's bound tools now include `import_design`.
