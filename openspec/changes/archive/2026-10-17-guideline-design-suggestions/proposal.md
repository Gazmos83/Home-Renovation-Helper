## Why

The owner has uploaded design style guides (the first is the Gotcha Covered Design Style Guide, ingested 2026-10-16) into the guideline corpus, but the Designer only calls `search_guidelines` when a rule or number matters. When it drafts a new piece, it never looks at style guidance or offers ideas from it, so the uploaded guides go unused unless the owner asks the right question.

## What Changes

- Before the first `create_piece` of a new piece, the Designer searches the guidelines for the confirmed brief's style, piece and room. It offers the owner two or three suggestions, each citing the publication or note and its section.
- Each suggestion says whether the piece's spec can hold it (a material, a front or handle, a layout within the confirmed sizes) or whether it is advice only (a fabric, a wall colour, an accessory). Advice-only suggestions are never written into the spec and never recorded as generator-extension requests.
- An offered suggestion goes into the document only after the owner accepts it. A number in a suggestion is a confirmed size only once the owner accepts it. The document then goes through the existing `create_piece` preview and `yes`, unchanged.
- When nothing matches, the Designer says it found no style guidance in the guidelines and does not offer advice from memory. When the owner declines suggestions or asks to go straight to the draft, the Designer drafts from the brief alone.
- Revisions, imports and rebuilds are unchanged: suggestions are offered only for a new piece.
- Instruction tests cover the new rule.

**Ladder step:** step 1 (spec change); no schema or generator change. **Agents:** Designer only; no new tool, no model change. **Render guard and bpy allow-list:** unaffected; nothing renders.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: the Designer offers cited guideline suggestions for a new piece before drafting it, and uses only the ones the owner accepts.

## Impact

- `backend/app/agent/instructions/designer.md`: one new rule; the existing `search_guidelines` rule is widened to include style guidance for a new piece.
- `backend/tests/test_instructions.py`: a test for the new rule.
- `backend/plugins/guidelines/tool.py`: a bug fix, added during apply. Any hit with a publication date crashed the tool, which made every uploaded guide unusable. A test covers a dated hit (`backend/tests/test_guideline_search.py`). This restores what "Guidelines are searched and cited" already requires, so no spec delta is needed.
- No API, database, frontend, plugin manifest or dependency change. The retrieved passages already arrive wrapped as untrusted content (`backend/plugins/guidelines/tool.py`).
