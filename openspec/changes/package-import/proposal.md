## Why

The owner designs furniture in another AI chat as well as with the Foreman. The predecessor app had an import document and template for this (`package_import`, `import-template.json`). This app keeps only the design format (`custom_build`). The only way in is the bare `POST /packages` route. A package made there is not recorded in the house file, so since `piece-first-workflow` it cannot be approved, priced or placed in a room. The owner wants an imported design to start as a piece they can see built and talk through with the Foreman. They also want to take a version back out, both as a design and as a shop bundle (owner decisions 2026-10-07).

## What Changes

- **An import template for another AI chat.** A downloadable `import-template.json` holds three things:
  - a `guide`: the field rules, written for whoever fills the template in, whether a person or a chat model;
  - the `custom-build` starter as its `build`;
  - nothing else.

  The app reads nothing from the `guide`.
- **Two accepted forms.**
  - A bare `custom_build` document.
  - The import wrapper: kind `package_import`, schema version 1, units `mm`, an optional `guide`, and a `build`.

  Either form is validated by the existing custom-build schema; an unknown field is refused by name and recorded as a generator-extension request, as for a design written here. Design only: a `survey` section, the predecessor's on-site room measurements, is refused by name, with a reason saying that rooms are recorded by Intake (owner decision 2026-10-07).
- **Import as a chat attachment.**
  - The owner attaches the `.json` file in a conversation. A design file is a new upload kind, recognised from its bytes: a UTF-8 JSON object whose `kind` is `custom_build` or `package_import`. It has its own size limit.
  - A turn carrying a design file goes to the Designer.
  - The Designer's new `import_design` tool reads the file by its upload id and previews the piece: name, overall size, modules, cut-list rows, hardware lines and any design-rule warnings. Only the upload id passes through the model, never the document.
  - On the owner's `yes`:
    - the piece and version 1 are recorded in the house file, with the change line "imported from <file name>";
    - the conversation is bound to the piece;
    - the headless build starts.

    The owner then sees the screenshot and talks changes through with the Foreman, as for any piece. Approval, pricing and room placement work unchanged.
  - A conversation that already has a piece refuses an import and asks for a new conversation.
- **Export from the Pieces page.** There are two downloads per version (owner decision):
  - **Download design:** the version's design as an import document (the wrapper without `guide`). It re-imports to the identical design, and it is the file to paste back into another AI chat.
  - **Download bundle:** a zip of that design file plus `cutlist.csv`, `hardware.csv`, `model.glb`, `screenshot.png` and, when rendered, `still.png`. It is offered only for a built version.
- **Studio.**
  - The Pieces page links the import template and says how to use it in another chat.
  - The conversation's file picker accepts `.json`.
  - An attached design shows as a named chip, not a thumbnail.
- **Ladder and agents.**
  - **Ladder step 1** only.
  - **Designer:** gains `import_design` and an instruction paragraph.
  - **Foreman:** gains a routing rule.
  - The Builder, Reviewer, Researcher, Intake and Lighting & materials are unchanged.
  - **The render guard is not affected:** an import starts a build (Workbench screenshot, no tier) and never a render. The bundle carries only renders that already exist.
  - **The bpy allow-list is not affected:** nothing new runs in Blender; the build uses the existing generator.

## Capabilities

### New Capabilities
- `design-import`: the import document and its two forms, the shipped template with its guide, importing an attached design as a new piece, and exporting a version as a design document and as a bundle.

### Modified Capabilities
- `plan-uploads`: a design file is a third accepted upload kind with its own size limit, stored and served like the others and never expanded into a model call.
- `design-agents`: the Foreman routes a turn that carries a design file to the Designer.
- `studio-ui`: the Pieces page offers the template and both exports; the conversation attaches a design file.

## Impact

- **Backend, new:**
  - `app/design_import.py`: wrapper model, template loading, export document, bundle.
  - `plugins/design_import/`: manifest and `import_design` (Designer, not toggleable).
  - `app/api/design_import.py`: the template route.
  - `backend/fixtures/packages/templates/import-template.json`.
- **Backend, changed:**
  - `app/agent/uploads.py`: `design` kind, `.json` storage, its own cap.
  - `app/api/uploads.py`: content type.
  - `app/config.py`: `upload_max_design_bytes`.
  - `app/db/models.py` and a migration widening `ck_uploads_kind`.
  - `app/agent/foreman.py`: routing rule, and the attachment expansion naming a design file instead of sending it.
  - `app/api/packages.py`: two export routes.
  - `app/agent/instructions/designer.md`.
- **Frontend:**
  - `src/lib/api.ts`.
  - `src/routes/Pieces.tsx`: template link, two downloads.
  - `src/routes/Conversation.tsx`: `.json` in the picker, design chip.
- **No new dependency.** The zip uses the standard library.
- **Depends on `piece-first-workflow` being applied.** The imported piece is recorded so that approval and pricing apply to it.
- **Overlaps `studio-chat-polish`.** Both modify the plan-uploads requirement "Plans and photos are uploaded to a thread" and the conversation's composer. Whichever archives second refreshes its delta against the first. A design file is recognised before the text-note test, so a `.json` design is never stored as a note.
