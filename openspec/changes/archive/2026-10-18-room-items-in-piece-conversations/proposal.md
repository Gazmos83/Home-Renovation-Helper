## Why

The end-to-end review of 2026-10-15 found that a new piece conversation in an approved room does not know what is already in it: "pieces or models added to a room were not recognized". The code confirms the gap:
- the room's composition (its placed pieces, stand-ins and library models) reaches only the Designer and the Builder (`foreman.py:1155-1156`), so Intake, which answers a new piece's first turns, and the Foreman's routing never see it;
- the items listed are those of the composition's **latest** version (`house_file.compositions`, `house_file.py:1061-1080`), not the approved one, so a newer unapproved draft hides the approved layout, and the note never says which items belong to which version.

The room's walls and ceilings already reach Intake and the Designer from the approved composition version (`house_note`).

## What Changes

- **The approved layout is listed.** For the conversation's confirmed room or apartment, the composition note lists the items of the **approved** version: each piece with its version, each library model with its name and stated size, each stand-in, and where each one stands. When a newer version exists that is not approved, its items are listed separately and labelled as a draft that is not approved. With no approved version, the latest version's items are listed, labelled not approved, as today.
- **More agents see it.** The composition note reaches Intake and the Foreman as well as the Designer and the Builder, once the conversation's room or apartment is confirmed. A conversation with no confirmed room still sees no composition.
- **Unchanged:** compositions of other rooms stay out; a piece version that is no longer approved is still marked; `room_fit` and `compose_room` keep using the approved room plan.

Ladder: none of the three steps; context only. Agents touched: the **Foreman**, **Intake**, the **Designer** and the **Builder** (what their prompt carries). The **render guard** and the **bpy allow-list** are **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `house-file`: "Compositions are indexed and reach the turn" lists the approved version's items, labels a newer unapproved draft, and reaches the Foreman and Intake.

## Impact

- `backend/app/agent/house_file.py`: `compositions()` also reads the approved version's `input.json` and returns its items (`approved_items`) beside the latest version's.
- `backend/app/agent/prompts.py`: `composition_note` lists the approved items first, then a newer draft's items labelled "draft, not approved".
- `backend/app/agent/foreman.py`: the composition note is added to Intake's notes and to the Foreman's routing prompt.
- Tests: `tests/test_prompts.py` (note wording), `tests/test_house_file.py` (approved items), `tests/test_foreman.py` (Intake and the Foreman receive the note).
- Frontend: no change.
- Relation: `composition-ceiling-layer` (in progress, uncommitted) also edits `composition_note` (the "(ceiling layer)" label); this change lands after it.
