## Why

The owner cannot duplicate a piece. On 2026-10-19 they attached `sideboardo.json` to keep a second sideboard next to `sideboard-1200`. The fixed reply from `delete-piece` refused it, because the name inside the file, "Sideboard", is the existing piece's name. Its "keep both" way asks the owner to edit the JSON by hand. Asking the Designer for a duplicate in chat does nothing either, because no tool can make one. The owner wants a copy in one step, both from the Pieces page and from chat.

## What Changes

- **Duplicate a piece.** A new piece is made from a chosen version of an existing piece. The default is the latest version. The owner gives the copy a name, prefilled as "<name> (copy)". Its id is derived from that name, can be edited, and must be free.
  - The chosen version's design and its frozen hardware inputs become version 1 of the new piece, with the change line "duplicated from `<package_id>` v`<n>`". Only the design's name changes.
  - The design is validated against the current schema first. A design the schema now refuses is refused by field name, and nothing is created.
  - The copy keeps the original's room and brief. Its headless build starts at once, as for any new version. It gets its own new conversation.
  - Approvals, reviews, verdicts, renders, pricings and saved places in rooms are not copied. The original is not touched.
- **Pieces page.** The piece dialog gains "Duplicate piece", asked in place like "Delete piece". The owner picks the version, name and id, confirms, and lands in the copy's new conversation. A new owner route is added: `POST /packages/{package_id}/duplicate`.
- **Chat.** The Designer gains a `duplicate_piece` tool. It is gated by the usual yes/no confirmation and shares the same service as the route. It works in any conversation. The conversation's own binding does not change, and the reply links the copy's new conversation.
- **"Keep both" becomes a real option.** When a design file matches an existing piece, the fixed reply's third way now says: reply "keep both" with a new name, and the file is imported as a new piece. On that reply the Foreman hands the earlier attachment to the Designer. The Designer calls `import_design` with a new optional `name`, which replaces the name inside the design. The owner no longer has to edit the file.

Ladder: step 1 only. A duplicate is a new spec version built headless, and the generator does not change. Agents touched: the **Designer** (new `duplicate_piece` tool, `import_design` gains `name`) and the **Foreman** (the fixed reply's wording and the "keep both" handoff, decided by code). The **render guard** and the **bpy allow-list** are **not affected**. A duplicate starts only a headless build, never a render, so it needs no guard ticket.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: a new requirement that a piece version can be duplicated into a new piece, covering what is copied, what is not, and when a duplicate is refused.
- `studio-ui`: a new requirement for "Duplicate piece" in the piece dialog.
- `design-agents`: a new requirement for the Designer's `duplicate_piece` tool.
- `design-import`: the matched-design reply's "keep both" way changes, and `import_design` takes an optional new name. This modifies the requirement added by `delete-piece`, which must be archived first.

## Impact

- Backend: new `app/packages/duplicate.py` service; `POST /packages/{package_id}/duplicate` in `app/api/packages.py`; new plugin `backend/plugins/duplicate_piece/` (manifest and tool, Designer); `plugins/design_import/tool.py` (`name` argument); `app/agent/foreman.py` (reply text, "keep both" detection and handoff note); `instructions/designer.md`.
- Frontend: new `DuplicatePiece` component beside `DeletePiece` in `routes/Pieces.tsx`; `lib/api.ts`.
- No migration: a copy is an ordinary `pieces` row, `piece_versions` row and `threads` row.
