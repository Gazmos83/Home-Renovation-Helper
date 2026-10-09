## Why

The owner's App Check 2 (`docs/App Check_2 09-10-2026.md`) leaves four items after `shelf-spacing-and-dividers`:

- Revisions pile up (one piece has reached version 14), and no version can be removed.
- The Project panel and the inspector beside the chat put the version in the piece's title ("listening-wall, version 14").
- A finished build has no "Inspect version N" button in the chat. Only a finished render has one.
- The exploded view hides all dimensions, so a module's size cannot be read while the piece is apart.

## What Changes

- **Delete a version.** The Pieces page and the Project panel get a "Delete version N" control. It asks "Are you sure?" before anything happens. Deleting removes everything for that version:
  - the version folder (model, renders, cut list, drilling list);
  - its database rows: version record, reviews and their items, render runs and feedback, and pricings;
  - the Review button on its render notices.
  
  Some deletions are refused, and the message says why:
  - an approved version, until it is unapproved;
  - a version that a room composition places, naming the composition;
  - a version whose build or render is still running.
  
  Deleting a piece's only remaining version deletes the piece and unbinds its conversations, after its own "Are you sure?". Version numbers are never reused.
- **At most 15 versions per piece.**
  - When a revision would make a 16th version, the code refuses it before the confirmation. The Designer then tells the owner to delete a version first and where to do it.
  - From the 13th version on, the revision confirmation and the Project panel show a heads-up, "version 13 of 15".
  - The package API's "new version" route is refused the same way.
- **Titles without the version.** The Project panel's header line shows the piece name and id without "version N". The inspector heading beside the chat shows the piece name, because its version buttons already show which version is open. Lines that act on a version keep its number, such as "Approve version 14" and "Inspect version 14".
- **Build notice with an Inspect button.** When a build that a conversation started ends, a notice is posted in the chat like a render notice. A finished build shows an "Inspect version N" button that opens the inspector beside the chat. A failed build says in plain words that it did not finish.
- **Module sizes in the exploded view.** In Exploded mode each module shows a label with its name and its width × height × depth in mm. The figures come from `spec.json` `modules`, and each label moves with its module.

Ladder step and agents: this is a **step 1** change. It adds no new spec fields. It touches the **Designer** (`revise_package` and `create_piece` refuse past the limit) and the **Builder's** build path (the build notice), and adds Studio UI. The **render guard is not affected**: nothing new renders, and deleting refuses a version with a running render. The **bpy allow-list is not affected**: no live script.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `furniture-packages`:
  - a version can be deleted;
  - a piece holds at most 15 versions;
  - version numbers are never reused after a deletion.
- `house-file`: deleting a version removes its records, and deleting the last version removes the piece and unbinds its threads.
- `design-agents`: a revision or creation past the limit is refused by code before the confirmation, and the heads-up appears from version 13.
- `homeowner-chat`: a build started in a thread posts a notice when it ends.
- `studio-ui`:
  - a delete control with "Are you sure?" on the Pieces page and the Project panel;
  - the panel header and inspector heading without the version;
  - the build notice's Inspect button;
  - module labels in Exploded mode.

## Impact

- **Backend:**
  - `app/blender/storage.py`: the next version number never reuses a deleted one, and a version folder can be removed.
  - `app/packages/service.py`: refuses past the limit.
  - `app/agent/house_file.py`: deletes a version or piece and its records.
  - `app/api/packages.py`: a new `DELETE /packages/{id}/versions/{n}` route.
  - `app/agent/progress.py`: adds the version count and limit.
  - `app/agent/notices.py`: adds build notices.
  - `ToolDeps.start_build` callers: `create_piece`, `revise_package` and `blender_build` post a build notice when the build ends.
  - An Alembic migration: `thread_notices` gets a `kind` column (`render` or `build`), and `tier` becomes nullable.
- **Frontend:**
  - `routes/Pieces.tsx` and the `ProjectPanel` in `routes/Conversation.tsx`;
  - `components/chat/Notice.tsx`;
  - `components/inspector/InspectorCanvas.tsx`, plus a new module-label overlay;
  - `lib/api.ts`.
- **Tests:** backend unit and API tests for delete, limit and notices; Vitest for the views; one browser check of the changed pages.
