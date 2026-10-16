## Why

The owner said "remove the corner couch please" (2026-10-16, room `Wohnen`). The Designer called `compose_room` at once and the owner was never asked whether anything else should change. The owner expected the same behaviour as for a piece. For a piece, the Designer restates the change list and asks whether anything else should change before it calls `revise_package` (design-agents, "The Designer confirms the change list before revising"). No such rule exists for a room composition. Each `compose_room` call creates a version and starts a headless build, so making several changes one at a time costs a version and a build each. Wohnen went from v6 to v8 in two single-item calls.

## What Changes

- **Restate before recomposing.** When the owner asks to change a room or apartment that already has a composition (add, move or remove items), the Designer first restates the changes it understood as a list, one line per item added, moved or removed, naming the item by its id from the composition note. It then asks whether anything else should change.
- The Designer calls `compose_room` only after the owner says the list is complete. That one call carries every change asked for since the composition's latest version.
- When the owner answers with a further change, the Designer adds it to the list and asks again.
- When the owner declines the `compose_room` summary with a reason, the Designer treats the reason as one more change, restates the whole list and asks again. It does not call `compose_room` again in that reply.
- Not affected: the first composition of a room or apartment (no version yet) keeps today's flow. The existing yes/no summary on `compose_room` is unchanged; this step comes before it.

Ladder step: none. The composition schema, the generator and `compose_room` itself are not changed. This is an instruction change for the Designer.
Agents touched: the Designer only.
The render guard and the `bpy` allow-list are not affected.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `design-agents`: a new requirement that the Designer confirms the change list before recomposing a room or apartment that already has a composition.

## Impact

- `backend/app/agent/instructions/designer.md`: the `compose_room` rule gains the restate-and-ask step.
- `backend/tests/test_instructions.py`: a test that the instruction carries the rule.
- No API, schema, migration or frontend change.
