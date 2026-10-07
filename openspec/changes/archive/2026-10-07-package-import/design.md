## Context

See proposal.md for the motivation. The current state this builds on:

- **Design format.** `CustomBuildSpec` (`app/blender/schemas.py`, `extra="forbid"`, strict) is the predecessor's `build` section field for field: materials, envelope, modules, extra parts, hardware, assembly notes and part overrides. `describe_validation_error` already joins every problem into one line. `validated_custom_build` (`app/agent/tools/shared.py`) records unknown fields as generator-extension requests.
- **Creating a piece.**
  - `create_piece` (`plugins/create_piece/tool.py`) checks the package id and that it is free, validates the document, applies `piece_outcome` (design rules), and previews.
  - On `yes` it creates `v1` through `service.create_version`, records the piece (with the thread's brief) and version 1, binds the thread, and starts the build.
  - The build is a headless Workbench screenshot; no render tier is involved.
- **Uploads.**
  - `uploads.sniff` accepts PNG and JPEG by signature. Files live at `<upload_root>/<thread>/<id>.<ext>`.
  - `ck_uploads_kind` allows `png` and `jpeg`.
  - `foreman.with_images` expands upload ids into image blocks, or into a note for slots that are not image-capable.
  - `_check_uploads` (`app/api/chat.py`) enforces thread ownership and `turn_max_images`.
- **Routing.** In the Foreman's router, a thread with no piece and no brief goes to Intake. The Designer is reached once a brief exists.
- **Untrusted text.** Retrieved passages and plugin results are wrapped by `prompts.wrap_passage`. `neutralise` strips the delimiter from owner-authored strings. Free text inside a design document (names, notes) comes from another chat and is untrusted.
- **Version files.** A version folder holds `input.json` (the validated, normalised document), the build files, and renders when made. `GET /packages/{id}/versions/{n}/files/{name}` serves single files.
- **Predecessor template.** `import-template.json` carries a 12-line `guide`: 11 lines for the build and one for the survey.

## Goals / Non-Goals

**Goals:**
- One path in, from a chat attachment through a confirmed preview to a recorded piece. Everything after that is the normal piece flow.
- A document's contents never pass through the model on the way in. The model handles only the upload id, a summary and refusals.
- An export that re-imports to the identical design.

**Non-Goals:**
- A room survey; rooms stay with Intake (owner decision).
- The predecessor's module-CSV conversion, its material review on import, and CAD attachments.
- Importing into a conversation that already has a piece, or importing as a new version of an existing piece. Revisions stay with `revise_package`.
- A Pieces-page import button. The owner chose the chat attachment.
- Bundling renders that do not exist yet. A bundle never starts a build or a render.

## Decisions

1. **One parser for both forms, in `app/design_import.py`.**
   - `parse_import(document)` returns the build, or a refusal.
   - A dict with `kind == "custom_build"` is the build.
   - A dict with `kind == "package_import"`:
     - first, a `survey` key gets the fixed refusal ("survey: rooms are not imported; Intake records a room from its measurements or a plan");
     - then it is validated by `ImportDocument`, which has `extra="forbid"`, strict typing, `kind`, `schema_version` 1, `units` "mm", an optional `guide` (≤ 40 × ≤ 500 characters), and `build: dict`.
   - The build then goes through `validated_custom_build`, so an unknown field inside it is refused by name and recorded as a generator-extension request (CLAUDE.md §1).
   - An unknown field on the wrapper itself is refused by name without a request, because it is not a design field.
   - *Alternative:* accept only the bare document. Rejected: the `guide` needs a home that the design schema refuses, and the predecessor's files use the wrapper.

2. **A design file is a third upload kind.**
   - `uploads.classify` keeps the image signatures first.
   - Otherwise it reads the whole stream under `upload_max_design_bytes` (default 256 KiB), decodes UTF-8 strictly and `json.loads` it. It accepts only a dict whose `kind` is `custom_build` or `package_import` → `design`, and refuses everything else with 415.
   - Stored as `<id>.json` and served `application/json` with `nosniff`.
   - Migration `0011_design_uploads` widens `ck_uploads_kind` to `('png', 'jpeg', 'design')`.
   - **Overlap with `studio-chat-polish`.** It adds a `text` kind through the same function. The design test runs before the text test, so a design `.json` is never stored as a note. Whichever change lands second also adds its kind to the constraint.
   - *Alternative:* sniff by file extension. Rejected by the plan-uploads rule that types come from bytes.

3. **A design file is named, never sent.**
   - `with_images` (renamed `with_attachments` if `studio-chat-polish` has landed) skips design ids when building image blocks. It appends, for every slot, `(The owner attached the design file '<neutralised name>' as upload <id>; import it with import_design.)`.
   - `_check_uploads` refuses a second design id in one turn (422 `too_many_designs`). `turn_max_images` keeps counting images only.
   - *Alternative:* inline the JSON so the model can talk about it. Rejected: up to 256 KiB per call, an injection surface, and the model could alter it when passing it on. After the import, the stored design is reached as for any piece.

4. **The router sends a design turn to the Designer.**
   - `load_house` sets `design_attached` when the newest owner message carries an upload of kind `design`.
   - The router's first rule becomes: pending confirmation → its specialist; else `design_attached` → `designer`; else the existing rules. This precedes the "no piece and no brief → Intake" rule.
   - *Alternative:* let the model choose. Rejected: CLAUDE.md routes by code rules wherever a fact decides.

5. **`import_design` reuses `create_piece`.**
   - It lives in a new plugin `plugins/design_import/` (Designer, enabled by default, not toggleable, like `create_piece`).
   - Its arguments are `upload_id: UUID` and `package_id: str`.
   - It loads the upload by id and refuses it unless the upload's thread is `ctx.thread_id` and its kind is `design`. The model never supplies a path or the document.
   - It refuses when the thread already has a package, read from the thread row, not from a model argument.
   - It runs `parse_import`, then the same checks and preview as `create_piece`. To share them, `create_piece`'s check, preview-summary and create-and-record steps are extracted into functions in the same module. This is a pure extraction: `create_piece`'s behaviour and tests are unchanged.
   - The create step gains a `changes` argument, so the import records `imported from <original name>`.
   - The confirmation subject is `import_design`; `DECLINED["import_design"]` covers `no`.
   - The brief recorded on the piece is the thread's brief when one was confirmed, otherwise empty.
   - *Alternative:* teach `create_piece` an `upload_id` argument. Rejected: it would change a non-toggleable tool's schema and its spec'd preview for a different source.

6. **Untrusted document text.**
   - In every tool result the model reads, the design's name and any refusal text quoting document values are wrapped with `wrap_passage`, using the source label `design file <name>`.
   - Numbers are shown as they are.
   - The owner's confirmation card shows the summary unwrapped.

7. **Export.**
   - `export_document(input)` returns `{"kind": "package_import", "schema_version": 1, "units": "mm", "build": <input.json>}`.
   - `input.json` is already the schema's normalised dump, so re-parsing and dumping yields the same dict; a round-trip test pins this.
   - Two owner-gated routes on the package router:
     - `GET /packages/{id}/versions/{n}/design` answers JSON with `Content-Disposition: attachment; filename="<id>-v<n>.json"`.
     - `GET /packages/{id}/versions/{n}/bundle` answers `application/zip` with `filename="<id>-v<n>.zip"`. It returns 409 `not_built` unless `status.json` says `succeeded`.
   - The zip is written with `zipfile` (deflate) into a `SpooledTemporaryFile` and streamed. Its members are fixed names: `<id>-v<n>.json`, `cutlist.csv`, `hardware.csv`, `model.glb`, `screenshot.png`, and `still.png` when present. `model.blend`, `status.json`, `spec.json` and any pricing are excluded. No member name comes from input.
   - *Alternative:* include `model.blend`. Rejected: the owner listed the files; `.blend` is large and app-internal.

8. **Template.**
   - `backend/fixtures/packages/templates/import-template.json` holds a `guide` ported from the predecessor's 11 build lines, edited for this schema and for a chat model. It drops the survey line and adds:
     - that the document is returned as JSON alone, with no prose or code fences;
     - that a room survey is not part of it;
     - that unknown fields are refused by name.
   - Its `build` is a copy of `custom-build.json`; a test asserts the two are equal.
   - The template is served by `GET /design-import/template` on a new owner-gated router. `/packages/import-template` is not used, because `import-template` is also a valid package id.

9. **Frontend.**
   - The `api.ts` URLs for the template and both exports are used as plain `<a href download>` links, so the browser sends the session cookie and saves the file.
   - The Pieces page shows the template link with its one-line how-to, and per version a "Download design" link. "Download bundle" appears only when the version info says `succeeded`.
   - In `Conversation.tsx`, the picker accepts `application/json,.json`, and a design upload (`kind === "design"`) shows as a chip with its `original_name`.

## Risks / Trade-offs

- [Another chat's JSON often fails validation] → The refusal lists every problem with its path in one line, and the Designer's instruction says to give that line to the owner to paste back into the other chat. Unknown fields are recorded once per field name, as today.
- [Prompt injection through names and notes in the document] → The document never enters a prompt (decision 3). Values quoted back are wrapped (decision 6). The schema bounds every string's length.
- [Overlap with `studio-chat-polish`] → Both modify the same plan-uploads requirement, the kind constraint and the composer. Task 0.1 checks which landed first, refreshes this delta's MODIFIED text if needed, and widens the constraint to every kind present.
- [A large `model.glb` makes the bundle slow] → It is streamed from a spooled file. The build caps model complexity already. Nothing is held per request beyond the spool.
- [The owner imports into the wrong conversation] → Refused when a piece is bound. A fresh conversation is one click.

## Migration Plan

- `0011_design_uploads` replaces `ck_uploads_kind` with one admitting `design`.
- Downgrade deletes `uploads` rows of kind `design` (their files stay on disk), then restores the two-kind constraint.
- No other table changes. Rollback: revert the code and downgrade one revision.

## Open Questions

None. Survey, export contents and the entry point were decided by the owner on 2026-10-07.
