## Why

Only handles are drawn today. Hinges, shelf pins, drawer runners, brackets, clothes rails and every hand-written hardware line exist only in `hardware.csv`, so the model, the inspector and every render show furniture without its hardware. The owner's pieces come increasingly from LLM-filled import templates, and those hardware lists are unreliable. `murphy-bed` v7 lists hinges twice (`cabinet-hinges` ×8 beside the rule's `hinge-concealed-110` ×24) and shelf pins twice (`shelf-pins` ×48 beside the `shelf-pin` rule). Its brass knobs are free lines that could have been modelled handles. `amesbury-wardrobe` v5 has rail supports but no rail at all. A free line whose id equals a rule's id is silently *added* to the rule's count (`derive._Hardware.add`). The owner asked on 2026-10-16 for hardware to be visible in the model, the inspector and the renders, for it to look as real as possible, and for the cut list to mark what the model does not show.

## What Changes

- **Import keeps `qty` required** (owner's decision 2026-10-16). It **corrects the hardware list against the rules in force**, and every correction is listed in the import preview before the owner's yes:
  - A hand-written line whose id equals a rule-counted line (hinges, shelf pins, runners, confirmat screws, flap stays, push latches, handles, brackets) is removed, and the rule's count stands.
  - A hand-written line whose item text matches a hardware-catalog entry of a rule-counted kind that the design already derives is removed as a duplicate. An example is "110 degree soft-close concealed cabinet hinges" when the doors already derive `hinge-concealed-110`.
  - A line that reads as a knob, pull or handle while the fronts carry no `handle` is kept, with a warning saying how to write it as a modelled `handle`. It is never converted automatically, because which fronts it belongs to is not stated.
  - A line matching nothing is kept as written and listed as "not shown in the model".
  - The stored version holds the corrected document. **Behaviour change (explicit):** an imported document can now have hardware lines removed. Today every line is kept.
- **A hardware catalog**, `config/hardware.yaml`. Each entry is an item key, or a key pattern such as `drawer-runner-*`, with a shape from a closed set (`hinge_concealed`, `shelf_pin`, `drawer_runner`, `shelf_bracket`, `hanging_rail`, `rail_support`, plus the existing `bar` and `knob`). An entry also gives the shape's sizes, a finish, and the phrases that identify it in a free line. A malformed entry stops startup, naming the file and the entry. A new item later is one YAML entry.
- **Drawn hardware.** A new `derive.hardware_layout(spec, inputs)` gives every placeable hardware piece, and the generator draws exactly those pieces in a new `hardware` layer. Each piece is a separate object named `<line id>#<n>`, parented to its module, carrying `hardware_key`. Pieces are drawn only where the position is known exactly:
  - **Hinges** (cup, arm and mounting plate) and **shelf pins** at their exact drilling-list positions. A ranged or rule-in-words position is never narrowed, so it is not drawn.
  - **Drawer runner pairs** along each drawer box.
  - **Brackets** at the owner's stated `bracket_positions_mm`.
  - **Hanging rails and their supports.**
  - Confirmat screws are never drawn (they are inside the boards).
  - Materials are physically based metals per finish, and edges are bevelled, so the result reads as real in Eevee and Cycles.
- **A hanging rail** a module can carry: `hanging_rails`, giving the rail centre height in the bay, the bay, a finish and item keys. The rail is cut to the bay's inner width, with two end supports. A centre-support count comes from a new count check, `rail_support_count_for_length`. No rule ships for it until the owner adds a cited note (TODO(user)); without one, only the two end supports are listed and the note says so.
- **The cut list marks what the model does not show.** Each `spec.json` hardware row gains `shown`, the number of pieces drawn. In the inspector's Cut list tab, a row with fewer pieces shown than its quantity gets a `*` after its item, with "(n of m shown)" when some are drawn. A legend under the table reads "* not shown in the model".
- **The import template's guide** describes `hanging_rails`. It says not to list hardware the rules count (hinges, shelf pins, runners, connectors), to write knobs and pulls as `handle`, and that `qty` is required.

Ladder step 2 (generator extension): the schema, the derive rules and the headless generator grow. Agents touched:
- **Designer:** import preview corrections, `hanging_rails` in create, revise and the template, and the context summary.
- **Builder:** the headless build draws hardware.
- **Researcher:** prices the corrected list.

The **render guard is not affected**: no new render path, tiers unchanged. The **bpy allow-list is not affected**. Hardware meshes are made by the checked-in headless generator with `bpy.ops.mesh` primitives, modifiers and `bpy.data`, as handles are today, with no file import.

## Capabilities

### New Capabilities

- `hardware-catalog`: the catalog file, its shapes, its loading and refusals, and how items are matched and drawn.

### Modified Capabilities

- `furniture-packages`: hardware is drawn (the sentence "No hole, pin, hinge cup or plate SHALL be drawn" changes: holes stay undrawn). Adds the `hardware` layer, `hanging_rails`, and `shown` on hardware rows.
- `design-import`: hardware corrections in both import previews, `qty` stays required, and the template guide.
- `design-guidelines`: the `rail_support_count_for_length` count check.
- `studio-ui`: the `*` marker and legend in the Cut list tab.

## Impact

- **Depends on `guideline-hardware-counts`** (uncommitted, 10/11 tasks), which changes `_hinge_count`, `_pin_line` and the hinge drilling entries this change draws from. It is applied only after that change is committed and archived (owner's decision 2026-10-16).
- **Backend:**
  - `app/blender/schemas.py`: `HangingRailIn`, and `hanging_rails` on modules and in `ModuleChanges`;
  - `app/blender/custom_build/derive.py`: `hardware_layout`, rail rows and lines, `shown`;
  - `app/blender/generators/build_custom_build.py`: draws the `hardware` layer;
  - a new `app/blender/hardware_catalog.py` and `config/hardware.yaml`;
  - `app/guidelines/checks.py` and `hardware_inputs.py`: the rail-support count check;
  - `plugins/design_import/tool.py` with a new `app/blender/import_corrections.py`;
  - `app/agent/revise.py` and `prompts.py`: rail wording;
  - `app/agent/instructions/designer.md`;
  - `fixtures/packages/templates/import-template.json`.
- **Frontend:** `src/components/inspector/CutListTables.tsx` and `src/lib/api.ts` (`SpecHardware.shown`). The inspector's layer switch for `hardware` appears from `spec.json` layers with no code.
- **Tests:** schema, derive, catalog loading, import corrections, template, the `--blender` build suite, Vitest for the marker, and a recorded browser check of the Cut list tab.
- **Unchanged:** `hardware.csv` and `cutlist.csv` columns (TODO(user): mark `*` there too?), pricing rules, room compositions (they import `model.glb`, so the hardware comes along), and existing versions (rebuilt only on request).
