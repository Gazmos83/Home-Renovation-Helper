## Context

The Designer reaches `compose_room` through the rule in `backend/app/agent/instructions/designer.md`: "call `compose_room` with the room's name … and every item". Each turn, the Designer's context carries the composition note (`prompts.composition_note`). The note gives each composition's latest version and its items, with ids and placements, so the Designer can name items by id when it restates a change. The `revise_package` restate rule (archived change `2026-10-09-designer-revision-clarity`) is enforced only in the instruction, and an instruction test checks its wording.

## Goals / Non-Goals

**Goals:**
- Use the same gather-then-call behaviour for changes to an existing composition as for piece revisions.

**Non-Goals:**
- Code enforcement (for example, refusing a `compose_room` call that was not preceded by a restated list). The piece rule is not enforced in code either, and a code gate would need conversation-state tracking that does not exist for either tool.
- Changing the `compose_room` summary, its add/move/remove diff, or the tool's arguments.
- The first composition of a scope, `create_piece`, `edit_decisions` or other confirmations.

## Decisions

- **Instruction text, not code.** Mirror the existing `revise_package` sentence structure in `designer.md`, so the two rules read alike and the model sees one pattern. Alternative: a Foreman-side gate that holds `compose_room` until the owner says "that's all". Rejected because it adds new state and a new pattern for a behaviour the piece rule already gets from the prompt alone (CLAUDE.md: no new abstractions unless needed).
- **Only when a composition version exists.** A first composition is one complete layout, and the yes/no summary already lists every item. Restating it first would add a round trip with nothing to gather. The trigger is observable from the composition note ("no version yet" against `vN`).
- **Restate by item id.** The ids come from the composition note, the same way module ids come from the piece summary. Lines read `corner-couch: remove`, `dining-table: move to …`, `sofa (stand-in): add on wall 2 at 500 mm`.
- **Test pins the wording.** Extend `backend/tests/test_instructions.py` with a test like `test_the_designer_restates_a_revision_and_asks_before_calling_the_tool`, asserting the key phrases for `compose_room`.

## Risks / Trade-offs

- [The model still calls `compose_room` at once, because the rule is prompt-only] → The same risk was accepted for `revise_package`. If it recurs, propose a code gate as a follow-up.
- [An extra round trip for a single-item change] → This is the behaviour the owner asked for. The owner can answer "that's all" right away.
