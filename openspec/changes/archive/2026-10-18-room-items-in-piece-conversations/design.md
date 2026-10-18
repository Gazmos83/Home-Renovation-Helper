## Context

See proposal.md (Why). Current state:
- `foreman.py` context node (`:748-760`) builds `composed` from `house_file.compositions(session, render_root)`, filtered to the confirmed room names or apartment (`scope_room_names`, `scope_apartment_name`), and sets `composition_note(composed, ready_models)` (`:840`). Without a confirmed room the scope is empty, so nothing is listed.
- `house_file.compositions` (`house_file.py:1061`) reads only the latest version's `input.json` and passes it to `placed_items`, which already names pieces (`package_id vN`, approved or `no_longer_approved`) and models (`name`) and copies `room`, `placement`, `layer`.
- `prompts.composition_note` (`prompts.py:380`) prints each composition as one line: latest version, status, `approved: vN`, then the latest items.
- The specialist agent node adds `composition_note` only for `designer` and `builder` (`foreman.py:1155`). The Foreman prompt is `compose_agent_prompt(text, facts, house_note)` (`:1004`).
- Library model sizes are in `ready_models`; a placed model item in the document carries `model_id` and its own `width_mm`/`depth_mm`/`height_mm`.

## Goals / Non-Goals

**Goals:**
- Every agent of a conversation with a confirmed room knows what stands in it, from the approved layout.
- A draft never hides the approved layout, and is labelled.

**Non-Goals:**
- Showing compositions of other rooms, or before a room is confirmed.
- Changing `room_fit` or `compose_room` (already on the approved plan, `placement_room`).
- A new tool to read a composition: the note is enough for the first turns.

## Decisions

1. **Read the approved version too.** `compositions()` adds `approved_items` (from the approved version's `input.json`, through `placed_items`) when an approved version exists and differs from the latest; when they are the same, `approved_items` equals `items`. A missing or unreadable file gives an empty list, like today's latest read.
2. **Model sizes in the item.** `placed_items` copies `width_mm`, `depth_mm`, `height_mm` for `model` and `stand-in` items, so the note can give a model's size without a library lookup.
3. **Note layout.** Per composition:
   - `- room Wohnen: latest v3, succeeded; approved: v2`
   - `  approved v2 items: …` (the existing item labels plus size)
   - `  draft v3, not approved, items: …` only when v3 > v2
   - with no approval: `  v3 items (not approved): …`.
4. **Who gets it.** The agent node adds `composition_note` for `intake`, `designer` and `builder`; the Foreman's routing prompt adds it after `house_note`. The token cost is a few lines per item; the context budget node already counts it.
5. **Ordering with `composition-ceiling-layer`.** That change's "(ceiling layer)" label is kept in the item label; this change only regroups lines.

## Risks / Trade-offs

- [Longer prompts for Intake and the Foreman] → only the confirmed room's composition is listed; rooms rarely hold more than a dozen items.
- [Two lists confuse a cheap model] → the draft list is printed only when a newer unapproved version exists, and is labelled in words.
