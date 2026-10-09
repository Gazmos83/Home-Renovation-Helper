## 0. Before applying

- [x] 0.1 Ask the owner to commit, and archive if wanted, `cabinet-hardware-calculator`. Its uncommitted edits in `revise.py`, `designer.md` and the tests must not mix with this change. Verify that `git status` shows no modification under `backend/app/agent/revise.py` or `backend/app/agent/instructions/designer.md` before section 2 starts.

## 1. V4 Flash entries and routing

- [x] 1.1 Read `deepseek/deepseek-v4-flash` and `~deepseek/deepseek-v4-flash-latest` from the OpenRouter models endpoint: context length, maximum completion tokens, `temperature` in supported parameters, and input modalities. Verify that both are listed and text-only, with the values in design decision 5. Report any difference to the owner before going on.
- [x] 1.2 Run `probe_slug` for each slug with a text request through the gateway (the `--live` path). Verify that both answer and record the dates. A guardrail block on either one stops this section and is reported to the owner as a configuration error naming the slug.
- [x] 1.3 In `backend/app/agent/models/registry.py`, add both entries with the values from 1.1 and their probe dates from 1.2 as their own `validated_on`. Add `alias: bool = False` to `ModelEntry` and set it on the `~…-latest` entry (design decision 5a). The five existing entries keep `_VALIDATED`. Update the module's comments. Verify with `tests/test_model_registry.py`, updated to seven expected ids, per-entry dates, both new slugs text-only, and only the `~…-latest` entry marked as an alias.
- [x] 1.4 In `backend/app/api/admin_models.py`:
  - in `set_routing`, refuse a text-only slug on an image slot before the probe, with code `text_only_model` and a message naming the slot and the model;
  - in `list_models`, return `alias` for each registry entry.

  Verify with `tests/test_admin_models_api.py`:
  - Intake → `deepseek/deepseek-v4-flash` is refused naming "text-only", and the probe is not called;
  - Designer → `~deepseek/deepseek-v4-flash-latest` is accepted and probed with text;
  - the list marks only the alias.
- [x] 1.5 Show the alias mark in the developer panel's model list (`frontend/src/routes/admin/Models.tsx`, and the type in `lib/api.ts`). Verify with `Models.test.tsx`: the alias row reads "alias — follows the newest V4 Flash" and the pinned row does not. Record a browser pass here.

  Browser pass 2026-10-09. Headless Chrome via Python Playwright, scratch DB `home_renovation_drc_ui`, backend on 8100 and Vite on 5180 (`API_PROXY`); the owner's 8000 and 5173 servers were untouched. Startup ran the live probe with the Foreman and Designer routed to `~deepseek/deepseek-v4-flash-latest` from the file. On Models and routing, both slots show `~deepseek/deepseek-v4-flash-latest (alias — follows the newest V4 Flash)`, `deepseek/deepseek-v4-flash` is listed with no mark, and both have budget cards.
- [x] 1.6 In `backend/config/models.yaml`, route `foreman` and `designer` to `~deepseek/deepseek-v4-flash-latest`. Update the tests that read the shipped file's Designer or Foreman slug (`test_admin_models_api.py` `DESIGNER_DEFAULT`, `test_chat_budget.py` `DESIGNER_SLUG`, and any other found with `grep`). Verify that the routing and startup tests pass, and that a startup with the probe enabled probes the alias with text.
- [x] 1.7 Update CLAUDE.md §4:
  - the routing table: Foreman and Designer use `~deepseek/deepseek-v4-flash-latest`, with the reason "the predecessor's model family; alias by the owner's decision of 2026-10-09";
  - the registry paragraph: seven slugs, the alias exception, and that `deepseek-v4-flash-0731` is not listed on the owner's key.

  Verify by reading the section back.
- [x] 1.8 Tell the owner that the live `routing:foreman` and `routing:designer` overrides (`deepseek/deepseek-v4.1-flash`) still win over the file. Resetting them in `/admin` puts both slots on the alias. Do not write or delete an override from code.

## 2. Change lines and no-ops

- [x] 2.1 Add `describe_fronts` and `describe_hardware` to `backend/app/agent/revise.py` (design decision 3). Use them in `_apply_module_change` for `fronts` and `hardware`, giving "before → after". Verify with `tests/test_revise.py`: two hinged doors replaced by one door and a 200 mm drawer give "cabinet: fronts 2 doors (hinge) → 1 door (hinge), 1 drawer 200 mm"; a non-default hinge item is named; an empty list gives "none"; a hardware quantity change gives the id, item, "×2 → ×4"; and no line contains "entries".
- [x] 2.2 Skip no-op values in `revise_spec` (design decision 4) for module fields, `hinge`, wall-shelf fields, name, envelope and materials. Verify with `tests/test_revise.py`: height 2238 → 2238 plus shelves 6 → 3 gives only the shelves line; a hinge already set on every hinged door gives no line; adds, removes and part overrides still give lines.
- [x] 2.3 In `backend/plugins/revise_package/tool.py` `_revised`, refuse when `revise_spec` returns no line, with "nothing would change: every requested value equals version N". Verify with `tests/test_revise_package.py`: an all-no-op change raises no confirmation and creates no version, and the shelves scenario still creates version 2 with "cabinet: shelves 2 → 3".

## 3. The Designer sees the piece

- [x] 3.1 Add `piece_note(package_id, version, document)` to `backend/app/agent/prompts.py` (design decision 2), using `describe_fronts` and `describe_hardware` and `neutralise` on every owner-authored string. Give a "could not be read" line when the document is `None`. Verify with a new `tests/test_piece_note.py` covering module size, position, shelves, fronts and hardware, wall shelves with and without bracket positions, extra parts, materials, part overrides, a module name containing the delimiter shown neutralised, and the unreadable case.
- [x] 3.2 In `backend/app/agent/foreman.py` `load_house`, read the bound build's latest `input.json` and put `piece_note` into the turn state. Add the note to the Designer's notes only, after `house_note` and before `designer_note`. Verify with `tests/test_foreman.py`:
  - the Designer's system prompt names `cabinet`, "3 shelves" and "1 door (hinge)";
  - Intake's and the Foreman's prompts do not;
  - a second build in the conversation appears only as its one line;
  - with no active build, no summary is given;
  - the guard text is still last.

## 4. Restate before revising

- [x] 4.1 Replace the revision rule in `backend/app/agent/instructions/designer.md`.
  - Keep: `revise_package` with only the fields that change, modules named by id, never resending the whole document, and open review items used as changes when the owner asks to fix them.
  - Add:
    - restate the understood changes as a list and ask whether anything else should change;
    - call the tool only once the owner says the list is complete, carrying every change since the last created revision;
    - when the owner adds a change, add it and ask again;
    - when the owner declines with a reason, treat the reason as one more change, restate the whole list and ask again, without calling `revise_package` in that reply;
    - read module ids, fronts and hardware from the piece summary, and when changing `fronts` or `hardware`, write the whole new list starting from the summary's.

  Verify with `tests/test_instructions.py`: the instruction file loads and contains the restate, complete-list and decline rules.
- [x] 4.2 Add a scripted-model case to `tests/test_design_loop.py`:
  - the owner asks for a width change, and the Designer answers with a restatement and no tool call;
  - the owner adds shelves and says that is all, and one `revise_package` call carries both and one confirmation lists both;
  - a "no" with a reason gives a reply with no new confirmation.

  Verify that the test passes. It checks the graph plumbing with a scripted model, not the live model's compliance.

## 5. Check and hand over

- [x] 5.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/` (one process). Verify that both are clean.
- [x] 5.2 Browser pass, no render: in one conversation on an existing piece, ask for a front change and confirm that:
  - the Designer restates it and asks before any card appears;
  - the card shows the fronts before and after in words;
  - a no-op request is refused in words.

  Record the result here.

  Browser pass 2026-10-09, same scratch setup as 1.5, live models through the gateway, piece `hall-cabinet` v1 (2 hinged doors, 4 shelves) in a conversation with Hall confirmed.
  - "Replace the two doors of the cabinet with one door and a 200 mm drawer." The Designer restated "cabinet (Cabinet): replace the 2 hinged doors with 1 hinged door and 1 drawer, 200 mm high" and asked whether the list was complete. No card appeared.
  - "That's all." The card read "cabinet: fronts 2 doors (hinge) → 1 drawer 200 mm, 1 door (hinge)".
  - Declined with the reason "not now, I am only checking the card". The Designer said nothing was saved, restated the list and asked again, with no new card.
  - "Forget the fronts. Set the cabinet to 4 shelves." then "Yes, that's the complete list." The Designer read from the piece summary that v1 already has 4 shelves and said in words that nothing would change and no version would be built. No card appeared, and only v1 exists. It did not call `revise_package`, so the tool's "nothing would change" refusal was covered by `test_revise_package.py`, not by this pass.
- [x] 5.3 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`. Verify that all are clean.
