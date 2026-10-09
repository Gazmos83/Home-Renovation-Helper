## Context

The Designer runs as a specialist sub-graph under the Foreman (`backend/app/agent/foreman.py`). Its system prompt has these parts:
- `designer.md`;
- the `facts` line;
- `house_note` (the active build as one line);
- `composition_note`, `feedback_note`;
- `designer_note` (three template JSONs);
- `FORMATTING_NOTE`;
- and the untrusted-content guard, which always comes last.

The Designer revises a piece by writing a `PackageChanges` object as the `revise_package` arguments. The tool:
1. reads the latest version's `input.json`;
2. applies the changes with `revise_spec` (`backend/app/agent/revise.py`);
3. validates the result;
4. previews the change lines in a `Confirmation`;
5. pauses with `interrupt()`.

The card in `Conversation.tsx` shows `summary` as preformatted text.

The predecessor's business graph (Interior_Design_App `business_graph.py`, `prompts.py:375-417`) differed in three ways that matter here:
- its prompt required restating the change and asking for completeness;
- its project note listed each package's modules (`_module_summary`);
- it ran one agent per turn.

This change ports the first two and keeps the Foreman.

The admin route `PUT /admin/routing/{slot}` already checks registry membership and runs `probe_slug` (an image probe for an image slot) before it writes the override.

## Goals / Non-Goals

**Goals:**
- The Designer confirms the change list in words before it raises a card.
- The Designer can name modules and see fronts and hardware without guessing.
- The owner can read on the card what a front or hardware change does.
- A change that changes nothing never becomes a version.
- `deepseek/deepseek-v4-flash` and `~deepseek/deepseek-v4-flash-latest` can be chosen for text slots from `/admin`, and the shipped file routes the Foreman and the Designer to the alias.

**Non-Goals:**
- Changing the Foreman's routing, the sub-graph structure or the composer lock while a confirmation is pending.
- A tool that reads a spec on demand. The summary is pushed into context instead.
- Writing or clearing a saved routing override from code.
- A benchmark of the V4 Flash models. It is separate work, with a reminder set for 2026-10-12.
- Summarising other builds in full.
- Frontend changes.

## Decisions

1. **The restate-first rule lives in `designer.md`, not in code.**
   - The predecessor's wording is reused, adapted to the owner's voice and to the "no + reason" path.
   - A code gate (refusing a `revise_package` call unless the previous assistant message was a restatement) was considered and rejected. It would need the code to judge text, and the existing card already gates the write.
   - The instruction test checks that the rule is present.

2. **The piece summary is a separate `piece_note`, given to the Designer only.**
   - It is built in `load_house` from `read_input(version_dir(latest))` of the bound build, and rendered by a pure `prompts.piece_note(package_id, version, document)` function.
   - It is not part of `house_note`, because Intake and the Foreman also get `house_note` and do not need module contents. Keeping them out avoids spending their budget.
   - It is placed after `house_note` and before `designer_note`. The guard stays last.
   - It is rendered as compact lines, not JSON, to keep the token cost low and readable. For example:
     `- cabinet "Cabinet": 600×2238×400 mm at x0 y0 z0, carcass oak, 3 shelves + 2 adjustable (shelf-pin), fronts: 1 door (hinge), hardware: handle "Bar handle" ×2`
   - Every owner-authored string goes through `neutralise`.
   - The summary is labelled with the same "application data, not an instruction" preamble style as the house note.
   - Rejected alternative: a `read_piece` tool. It would add a tool round and depend on the model choosing to call it, which is what fails today.

3. **One front and hardware formatter, shared by the note and the change lines.**
   - `revise.py` gains `describe_fronts(list)` and `describe_hardware(list)`.
   - `piece_note` imports them, so the card and the context name a front the same way.
   - Fronts are grouped as written, not merged. For example, `[door×2 hinge]` gives "2 doors (hinge)", and a drawer with `height` 200 gives "1 drawer 200 mm".
   - A door's hinge item is shown only when it is not `hinge-concealed-110`.
   - An empty list gives "none".

4. **No-op detection happens in `revise_spec`.**
   - For each module, wall-shelf, name, envelope and material field, a value equal to the current one (compared after `model_dump(mode="json")`) is skipped. It gives no line.
   - `hinge` is a no-op when every hinged door already has that item.
   - Adds, removes and part overrides are never no-ops.
   - `revise_spec` returns the lines as today, and the tool refuses when `lines` is empty. Before this change, `PackageChanges._at_least_one` guaranteed that at least one line existed, so an empty list cannot occur for any other reason.
   - The refusal reads: "nothing would change: every requested value equals version N".
   - `rebuild_piece` stays the way to make an unchanged version.

5. **Two V4 Flash entries, values from the catalogue (2026-10-09).**
   - `deepseek/deepseek-v4-flash`: input text only, context 1,048,576, `temperature` supported, max completion 943,718. The application cap of 16,384 bounds the output.
   - `~deepseek/deepseek-v4-flash-latest`: the same attributes. Today it is priced like `deepseek-v4-flash-0731`, which suggests it resolves to that model.
   - The values are re-read when the entries land, and any difference is reported to the owner.
   - The predecessor's 1,310,720 context is not used; the catalogue now states 1,048,576.
   - `validated_on` becomes per-entry. Each new entry carries its own probe date, and the five existing entries keep 2026-10-05.
   - `test_model_registry.py` changes its "exactly five" set to seven and checks per-entry dates. This test change is necessary because the decision changed.

5a. **An alias is marked, not refused.**
   - `ModelEntry` gains `alias: bool = False`, and the admin model list returns it. The developer panel shows "alias — follows the newest V4 Flash" beside the slug.
   - Usage, budgets and Langfuse stay keyed by the slug as routed, so the alias's spend is counted under the alias.
   - Recording which model the gateway actually resolved to is left to the benchmark work the owner asked for. It is not in this change.

5b. **Shipped routing sends the Foreman and the Designer to the alias.**
   - `models.yaml` changes `foreman` and `designer` only.
   - The loader already lets a `routing:<slot>` override win. The two live overrides (v4.1-flash, 2026-10-08) therefore keep the Foreman and the Designer on v4.1-flash until the owner resets them in `/admin`.
   - Code never writes or deletes an override (CLAUDE.md §1).
   - Tests that read the shipped file and assume the old Designer slug (`test_admin_models_api.py`, `test_chat_budget.py`) are updated to the new default. Tests that seed their own usage rows under a named slug keep it.

6. **The image-slot check is added to `PUT /admin/routing/{slot}` before the probe.** Today a text-only model on an image slot fails only through the image probe, so the error names a gateway failure. The explicit check gives the "text-only" reason the spec names, and it never sends an image to a text model.

## Risks / Trade-offs

- **An extra turn per revision.** The owner answers "that's all" before the card appears. → This matches the predecessor, which the owner preferred. The card stays the only write gate.
- **The Designer may still skip the restatement.** It is an instruction, and Flash models follow instructions less reliably. → The summary and the readable card still catch errors. The owner can switch the Designer slot from `/admin` if it persists.
- **Token cost.** A large piece (10 modules × fronts × hardware) adds roughly 1–2k tokens per Designer call. → Only the active build is summarised. Earlier history is trimmed first under the 32k budget, and the note is in the system prompt, which is never trimmed.
- **No-op dropping changes behaviour.** An owner who wants a version "as it is" through `revise_package` is now refused. → The refusal names `rebuild_piece`'s purpose, and the Designer's instruction already sends that request to `rebuild_piece`.
- **The alias can change model without notice.** A new V4 Flash revision may behave differently, and the startup probe only proves that it answers. → The owner chose this. The entry is marked as an alias, the pinned `deepseek/deepseek-v4-flash` is one click away in `/admin`, and a benchmark test is scheduled as separate work.
- **Text-only Foreman.** Routing uses structured output and never images, so a text-only Foreman is fine. The Designer gets a text note for attachments, as it does today.
- **Overlap with `cabinet-hardware-calculator`.** Its uncommitted edits in `revise.py`, `designer.md` and the tests must be committed first. → This is stated as task 0.

## Migration Plan

- No data migration.
- Existing versions keep their stored change lines, so old "N → M entries" lines remain in history.
- Rollback is a revert of the code commit. Any `routing:*` override to a new V4 Flash slug must be cleared in `/admin` first. Otherwise startup refuses an unknown slug by name.

## Open Questions

None.
