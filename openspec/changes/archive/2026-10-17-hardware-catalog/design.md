## Context

- **Hardware lines are merged by id.** `derive._Hardware.add` sums the quantities of lines that share an id. A free line `hinge-concealed-110` ×8 in an import is therefore added to the rule's 24. A free line with another id (`cabinet-hinges`) becomes a second line for the same hinges.
- **Rule-counted items** are the lines derive writes itself:
  - `hinge-concealed-110` (or the door's `hinge` key), `hinge-flap`, `flap-stay`, `push-latch`;
  - `shelf-pin` (or the module's `shelf_pin` key);
  - `drawer-runner-<length>`;
  - `confirmat-7x50`;
  - the handle keys from `handle_layout`;
  - wall-shelf bracket keys.

  Their counts come from data sheets, the design rules (`guideline-hardware-counts`) or the built-in fallbacks.
- **Positions already exist for some of them.** `derive.drilling(spec, inputs)` gives hinge cup borings, plate positions and shelf-pin holes, each as an exact value, a range or a rule in words ("A ranged value stays a range": never narrowed to a midpoint). `bracket_plan` gives the owner's positions exactly and the calculated ones as a range.
- **Handles are the precedent for drawn hardware.** One shared layout function (`handle_layout`) feeds validation, derive and the generator. Each handle is one `_prism` mesh in its own layer, with a `hardware_key` and no `part_id`. The inspector builds its layer switches from `spec.json` layers.
- **The import preview** is built in `plugins/design_import/tool.py` (`preview`, `version_preview`) from the validated document and derive's output. The owner answers yes or no.

## Goals / Non-Goals

**Goals:**
- Every hardware piece whose position the spec fixes exactly is drawn, realistically, as its own named object, in the model, the inspector and every render.
- An LLM-written hardware list cannot double-count what the rules count. Every correction is visible in the preview before yes.
- Adding a common hardware item takes one catalog entry, with no code.
- The cut list says which hardware the model does not show.
- A document with no hardware lines and no `hanging_rails` derives the same cut list and hardware as before. Its model gains only the `hardware` layer.

**Non-Goals:**
- Meshes from the model library, and multi-part mechanisms with poses. These belong to `hardware-models-and-assemblies`.
- Drilling holes drawn as geometry.
- Turning a knob or pull line into a `handle` automatically.
- Guessing a quantity, or a position inside a range.
- Rebuilding existing versions.

## Decisions

1. **Corrections happen on import, in code, on the document.** `import_corrections.correct(document, derived_hardware, catalog)` returns the corrected document and its correction lines. A model never makes them. The preview lists each one, for example "Removed `cabinet-hinges` ×8 (110 degree soft-close concealed cabinet hinges): hinges are counted by rule — `hinge-concealed-110` ×24". On yes, the corrected document is stored, so the spec stays the source of truth and nothing is overridden at derive time. Applied to `import_design` and `import_design_version` only.
   - Alternative rejected: dropping duplicates inside derive for every document. That would change how existing versions derive, and the owner would not see it.
   - `revise_package` and `create_piece` already work from the summary and the Designer's rules, so they are left as they are.

2. **Matching is by id first, then by catalog phrase.**
   - An equal id to a rule-counted line removes the free line.
   - Otherwise a line whose `item`, lower-cased, contains one of a catalog entry's `matches` phrases is that entry's kind. It is removed only when the kind is rule-counted *and* the derived hardware holds a line of that kind. A hinge line on a design with no doors is kept, with a warning that no door uses it.
   - Phrases are plain substrings. There is no fuzzy matching and no model.

3. **Catalog file shape** (`config/hardware.yaml`, strict Pydantic, `extra="forbid"`):

   ```yaml
   - key: hinge-concealed-110          # or pattern: drawer-runner-*
     shape: hinge_concealed            # closed set, see below
     size: {cup_diameter_mm: 35, cup_depth_mm: 12, arm_length_mm: 60, plate_length_mm: 50}
     finish: nickel
     rule_counted: true
     matches: ["concealed hinge", "cabinet hinge", "cup hinge"]
   ```

   - The closed shape set is `hinge_concealed`, `shelf_pin`, `drawer_runner`, `shelf_bracket`, `hanging_rail`, `rail_support`, `bar` and `knob`. Each shape has its own size model.
   - Finishes: `black`, `aluminium`, `steel`, `brass`, `nickel` and `chrome`.
   - Loaded once at startup. A malformed file or entry stops startup, naming `config/hardware.yaml` and the entry key, the same way design rules do.
   - The sizes are visual dimensions of the drawn shape, not engineering values, so no citation is required. **Assumption (TODO(user)):** the shipped sizes are typical catalogue sizes (35 mm cup, 5 mm pin, 30 × 15 mm oval rail), stated as such in a comment.

4. **One shared layout, `derive.hardware_layout(spec, inputs)`.** The catalog reaches it through the version's frozen hardware inputs (`hardware_catalog`), because `derive.py` is standard-library only and runs inside Blender; without them nothing is drawn and every `shown` is 0. It returns one record per drawn piece: line id, piece index, shape, catalog size, finish, the module, and its placement in build millimetres (origin, axes). Derive counts the records per line to set `shown`. The generator draws the same records, so the two cannot disagree.
   - **Hinges:** one record per hinge at each exact cup position from the drilling list (cup on the door's inner face, arm, plate on the side's inner face). A door whose positions are ranged or rule-only gets none.
   - **Shelf pins:** one per exact pin position under each adjustable shelf board.
   - **Drawer runners:** one pair per drawer, the runner length from `runner_length`, on the drawer box sides at the box's bottom edge. **Assumption (TODO(user)):** side-mounted runners at the box bottom. No runner data sheet states a mounting height yet.
   - **Brackets:** one per owner-stated `bracket_positions_mm` entry. Calculated brackets have ranged ends, so they are not drawn.
   - **Hanging rails and supports:** see decision 6.
   - **Handles:** stay in `handle_layout` and their own `handles` layer, unchanged.
   - **Free lines:** drawn only when they are a rail or rail support placed by `hanging_rails`. Every other free line gets `shown: 0`.

5. **Realism in the generator.** Each shape is built from `bpy.ops.mesh` primitives with a Bevel modifier, plus Smooth by Angle where curved. Materials are Principled BSDF, metallic 1.0, with a roughness per finish (chrome 0.08, nickel 0.2, steel 0.3, aluminium 0.35, brass 0.25, black 0.5 with metallic 0.3). Shader nodes are looked up by type. All hardware objects go in a new `hardware` layer, parented to their module's empty, with `hardware_key` set and no `part_id`. Pieces of the same line share one mesh datablock, which keeps the file and the GLB small.

6. **`hanging_rails` on a module.** Each entry has:
   - `bay` (1-based, default 1);
   - `z`: the rail centre in mm above the bottom panel's top, required, never defaulted;
   - optional `inset_y_mm`: from the front of the side panel, default half the inner depth;
   - optional `finish`, `key` (default `rail-oval-30x15`) and `support_key` (default `rail-support-oval`).

   Validation refuses, by field name:
   - a bay that does not exist;
   - a rail that crosses a shelf, or a bay whose bounding divider does not reach the rail;
   - a rail whose top is less than the hook clearance below the board above;
   - a rail on a folded module (not supported; refused rather than drawn wrongly).

   The hook clearance (40 mm), the rail's section height (30 mm) and the end allowance (1 mm per end) are constants in `derive.py`, not catalog values. Validation and the cut length must not depend on the catalog, which only a built version freezes; the catalog holds only the drawn shape.

   Derive adds one hardware line per rail key and cut length, id `<key>-<length>`, with the cut length in the item ("Wardrobe rail oval 30×15 mm, cut to 894 mm"), and two `rail_support` pieces per rail. More supports come only from the `rail_support_count_for_length` rule. Without the rule, the line notes "no centre-support rule". The rail is hardware, not a cut-list part.

7. **`shown` and the `*`.** Derive adds `shown` (whole number ≥ 0) to every hardware row. The Cut list tab:
   - marks a row with `*` after its item when `shown` is less than its quantity, or when the quantity is unknown and nothing is shown;
   - adds "(n of m shown)" when 0 < shown < qty;
   - shows the legend "* not shown in the model" under the hardware table whenever any row is marked.

   A version built before this change has no `shown`: no row is marked and no legend appears (the version's own files are the truth). CSV files are unchanged.

## Risks / Trade-offs

- **[Few hinges drawn when data sheets are incomplete]** Exact positions need complete data sheets. → The `*` makes that visible, and adding a data sheet fills it in.
- **[Phrase matching removes a line the owner wanted]** → The correction is listed in the preview, and a no keeps nothing. The owner can rename the item and import again.
- **[Object count]** 48 pins and 24 hinges add about 100 small objects. Shared meshes keep `model.glb` small. Build time is measured against murphy-bed v7 (about 3.5 s today), with a limit of 15 s.
- **[Overlap with `guideline-hardware-counts`]** → Applied after that change lands.

## Migration Plan

No data migration. Existing versions keep their files. A rebuild or a new version picks up the drawn hardware. Rollback is removing the catalog file and the layout call.

## Open Questions

- TODO(user): should `hardware.csv` also mark `*` (a `shown` column), or only the inspector?
- TODO(user): rail-support spacing. Add an owner note with the clause to cite, or keep end supports only.
