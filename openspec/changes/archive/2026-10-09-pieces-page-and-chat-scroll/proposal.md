## Why

The owner's App Check 2 (`docs/App Check_2 09-10-2026.md`) lists three points about the Pieces page, and the owner added a fourth about the conversation view (2026-10-09):

- A piece's versions are a row of buttons. At up to 15 versions that row wraps and crowds the card.
- "Download design", "Download bundle" and "Inspect version N" are one line of look-alike links, so the action that opens the model is lost among the downloads.
- A piece card has no picture. A piece cannot be recognised without opening a version.
- The conversation's messages grow the whole page, and the view opens at the first message. The owner has to scroll to the end of a long conversation every time.

## What Changes

- **Version dropdown.** The Pieces page shows a piece's versions in one dropdown instead of a row of buttons, newest first. Each entry reads "Version N", followed by its state when it has one: "(approved)", "(failed)" or "(building)". The page still opens on the newest version, and choosing an entry shows that version as the buttons did.
- **Inspect apart from downloads.** "Inspect version N" becomes a framed button, placed with "Approve version N". The downloads move to a line of their own, "Downloads: Design (JSON) · Bundle (ZIP)". The bundle is still offered only for a built version, and Inspect only for a built version.
- **Picture on each piece card.** The top of each piece card shows the build screenshot of the approved version. If no version is approved, or the approved version has no screenshot, it shows the newest version that has one. A caption names the version, e.g. "Version 14 (approved)". The picture does not follow the dropdown. A piece with no screenshot shows no picture and no error. Only the build screenshot is used, never a render.
- **Chat scrolls in its own box and opens at the last message.**
  - The message list takes the window height left under the header and title, with its own scroll bar. The composer, or a pending confirmation or question form, stays visible below it.
  - Opening a conversation shows the last message.
  - A new message, reply, notice or waiting bubble scrolls the list down only when the owner is already at the bottom.
  - Sending a message always scrolls to the bottom.

Ladder step and agents: this changes Studio UI only. It is not a ladder step, it touches no agent, and it adds no spec field or route. The **render guard is not affected**: nothing renders, and the picture is the existing build screenshot. The **bpy allow-list is not affected**: no live script.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `studio-ui`:
  - the Pieces page lists versions in a dropdown;
  - Inspect is a button set apart from the downloads;
  - each piece card shows a picture;
  - the conversation's messages scroll in their own box and open at the last message.

## Impact

- Frontend only:
  - `frontend/src/routes/Pieces.tsx` (version dropdown, `Downloads`, `Approval` with the Inspect button, a new piece picture);
  - `frontend/src/routes/Conversation.tsx` (message box height and scroll);
  - their Vitest files `Pieces.test.tsx` and `Conversation.test.tsx`.
- No backend change. The picture uses the existing version route (`files` lists `screenshot.png`) and the existing file route (`versionFile`).
- No migration and no dependency.
