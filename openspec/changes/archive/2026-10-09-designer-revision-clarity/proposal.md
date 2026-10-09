## Why

The owner reports that revisions in the conversation chat are misunderstood and instructions are not followed. The predecessor's project assistant did not have this problem. A comparison of the two setups (2026-10-09) found three differences on the revision path:

- The predecessor restated each change and asked whether the list was complete before calling `revise_package`. The Designer here calls the tool at once.
- The predecessor's context listed every package's modules with their size, shelves and fronts. The Designer here sees the active build as one line, so it guesses module ids and front contents. Because `fronts` and `hardware` are replaced as whole lists, it has to rewrite them without seeing them.
- The confirmation card shows a front or hardware change only as a count ("cabinet: fronts 1 → 1 entries"). It also accepts changes that change nothing ("cabinet: height 2238 → 2238"). The owner cannot spot a wrong change before saying yes.

The owner also wants the Designer and the Foreman on the DeepSeek V4 Flash family, which the predecessor used. The predecessor's `deepseek/deepseek-v4-flash-0731` is still in the gateway catalogue, but the owner's key no longer lists it (2026-10-09). The key lists `deepseek/deepseek-v4-flash` and the alias `~deepseek/deepseek-v4-flash-latest`. The owner decided (2026-10-09) to make both available and to route the Foreman and the Designer to the alias.

## What Changes

- **Restate before revising.** The Designer restates the change it understood as a list and asks whether anything else should change. It calls `revise_package` only after the owner says the list is complete. That one call carries every change asked for since the last created revision. When the owner adds a change, the Designer adds it and asks again. When the owner declines a revision with a reason, the Designer treats the reason as one more change, restates the whole list and asks again. It does not call the tool again in the same reply. This ports the predecessor's rule.
- **The Designer sees the piece it revises.** Each Designer turn carries a summary of the active build's latest version, built by code from that version's stored document:
  - per module: id, name, size, position, carcass slot, fixed and adjustable shelves, and each front with its type, count, opening or hinge side, height and hinge item;
  - hardware lines;
  - wall shelves, extra parts, material slots and part overrides, by id.

  Owner-authored names are neutralised. Only the active build is summarised. Other builds stay one line each.
- **Readable change lines.** A `fronts` or `hardware` change lists what was there and what replaces it, for example "cabinet: fronts 2 doors (hinge) → 1 door (hinge), 1 drawer 200 mm". It no longer shows a count.
- **No-op changes dropped.** A field whose new value equals the current one is dropped from the revision and gives no change line. A revision whose every change is a no-op is refused with "nothing would change", so no version is created and no card is shown. **This changes behaviour:** today such a revision creates a version.
- **Registry entries for the V4 Flash models on the owner's key.**
  - `deepseek/deepseek-v4-flash` is a pinned model.
  - `~deepseek/deepseek-v4-flash-latest` is an alias: the gateway redirects it to the newest V4 Flash model. This is a decided exception to pinning. The model behind the slug can change without a new probe, so the registry marks the entry as an alias.
  - Both are text-only. Their attributes come from the gateway catalogue, and each is probed before it lands.
  - Intake and the Reviewer stay barred from both by the image-slot rule.
  - `deepseek/deepseek-v4-flash-0731` is not added, because the owner's key does not list it.
- **Default routing.** `models.yaml` routes `foreman` and `designer` to `~deepseek/deepseek-v4-flash-latest`. There is still no backup slot.
  - The live `routing:foreman` and `routing:designer` overrides (both `deepseek/deepseek-v4.1-flash`, set 2026-10-08) still win over the file. The owner resets them, or switches the two slots, by hand in `/admin`. Code does not write routing.
  - CLAUDE.md §4 gets the new routing table and registry list.

Ladder step: none of this changes the spec schema or the generator. The schema, `revise_spec` and the Designer's context change at the application level, and pieces are still revised at step 1. Agents touched: the Designer (instruction, context, `revise_package` change lines, default model) and the Foreman (default model).

The render guard and the `bpy` allow-list are not affected.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `design-agents`:
  - the Designer restates and confirms a change list before calling `revise_package`, and a decline reason becomes one more change;
  - the Designer's context carries the active build's latest version summary;
  - change lines show front and hardware contents;
  - no-op changes are dropped, and an all-no-op revision is refused.
- `llm-gateway`: the registry gains `deepseek/deepseek-v4-flash` and the alias `~deepseek/deepseek-v4-flash-latest`, both text-only, each with its own probe date; the routing file sends the Foreman and the Designer to the alias.

## Impact

- `backend/app/agent/instructions/designer.md`: the revision rule.
- `backend/app/agent/foreman.py` (`load_house`, the Designer's notes) and `backend/app/agent/prompts.py`: a new `piece_note` built from the active build's latest `input.json`.
- `backend/app/agent/revise.py`: front and hardware descriptions, no-op detection.
- `backend/plugins/revise_package/tool.py`: refusal when no change remains.
- `backend/app/agent/models/registry.py`: two entries, an alias marker, and per-entry probe dates.
- `backend/config/models.yaml`: `foreman` and `designer`.
- `CLAUDE.md` §4: routing table and registry list.
- Tests:
  - `test_revise.py`, `test_revise_package.py`, `test_instructions.py`, `test_foreman.py`;
  - `test_model_registry.py`, because its "exactly five slugs" and single-date assertions change;
  - the routing tests that read the shipped `models.yaml`;
  - a new `test_piece_note.py`.
- Overlap: `revise.py`, `designer.md` and `test_revise.py` carry uncommitted edits from `cabinet-hardware-calculator`, which has every task ticked but is not archived. That change should be committed (and archived) before this one is applied, so the two diffs stay separate.
- Frontend: the developer panel's model list (`routes/admin/Models.tsx`, `lib/api.ts`) shows the alias mark. The confirmation card needs no change, because it already shows the backend's summary text.
- No migration, no new dependency.
