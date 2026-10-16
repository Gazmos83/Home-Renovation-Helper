## Why

A design file attached before the conversation has a room is never imported. The Foreman asks "Which room is this for?", the owner's answer goes to Intake, and Intake has no import tool, so the turn ends with "I can't run that import". The owner then has to attach the same file again. It happened on 2026-10-16 with `kommode-harmony.json` in the conversation "Vintage Dresser Renovation Ideas": the room `Wohnen` was confirmed and the file was not imported.

## What Changes

- When an Intake turn confirms the conversation's first room or apartment, the conversation has no piece, and an owner message in it carries a design file, the same turn goes on to the Designer. The Designer imports the newest such file with `import_design`, and the owner sees the usual import preview and answers yes or no.
- This is the one turn that may run two specialists: Intake first, then the Designer. The hand-off is decided by code, not by a model.
- Intake no longer says anything about importing an attached design file; the app hands the file over itself.
- The rule "a design file sent before the room was confirmed is not imported then; the owner attaches it again" is replaced.
- The hand-off happens only on the turn the room is confirmed, so a "no" to the preview is not asked again. Attaching the file again still works as before.

Ladder: none (no spec, generator or Blender change). Agents touched: the Foreman's graph (routing after Intake), Intake (instruction text) and the Designer (one code-composed note). The render guard and the `bpy` allow-list are not affected: an import queues its build exactly as today.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: the routing requirement lets a turn that confirms the room hand an earlier design file to the Designer, replacing "the owner attaches it again".

## Impact

- `backend/app/agent/foreman.py`: a conditional edge after the `intake` node instead of `intake → END`; working out the pending design upload; the Designer's note naming it.
- `backend/app/agent/instructions/intake.md`: one line on attached design files.
- `backend/tests/`: routing tests for the hand-off and its refusals.
- `openspec/specs/design-agents/spec.md`: the routing requirement.
- No migration, API or frontend change.
