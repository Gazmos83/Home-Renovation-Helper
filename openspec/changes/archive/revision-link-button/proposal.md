## Why

When the owner confirms a revision, the chat says "Created hall-bench version 2 … The build has started." and nothing more. The only way into the new version is the build notice's "Inspect version N" button, which appears only after the build ends (about half a minute) and not at all when the build fails. The owner asked that a revision always come with a link to it in the output, as a button centered in the chat window.

## What Changes

1. **Revision notice.** When `revise_package` records a new version in a conversation, the service posts one `revision` notice to the thread, written by code, carrying the piece and the new version, for example "hall-bench version 2 is created." It posts at the moment the version exists, before its build ends, and whether or not the build later succeeds.
2. **Button.** The notice shows an "Open version N" button, centered in the chat window like the existing notices, that opens the inspector beside the chat for that version (the same action as "Inspect version N").
3. **Rebuilds and imports.** `rebuild_piece` and a design import over an existing piece also create a version through the same function, so they post the same notice. `create_piece` is unchanged (not a revision).
4. **Existing notices.** Build and render notices keep their text and buttons.

**Ladder step:** none (chat UI and notice only; no schema, generator or Blender change). **Agents:** Designer's tools post the notice; no model sees it. **Render guard / bpy allow-list:** not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: a thread's history carries a `revision` notice per revision or rebuild confirmed in it, with piece and version, rendered with a centered button.
