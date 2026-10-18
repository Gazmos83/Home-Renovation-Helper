## Context

- After `hardware-catalog`, `derive.hardware_layout` gives every drawn hardware piece with its catalog shape, size, finish and placement. The generator builds each piece from primitives in the `hardware` layer.
- The model library stores owner uploads (GLB, glTF zip, OBJ zip) with a stated real size. A headless check marks each one `ready` or `refused`. The room-composition generator already imports `ready` models; the piece generator imports nothing.
- The inspector loads `model.glb` in the browser (`PieceModel.tsx`). murphy-bed v7 builds in about 3.5 s, so a second export costs seconds, not minutes.
- The murphy-bed design is an LLM's. Its mechanism is free hardware lines with no geometry and no real product behind it.

## Goals / Non-Goals

**Goals:**
- The owner's own library models replace catalog shapes key by key, at real size.
- A fold-down bed's mechanism is shown component by component. Each component is a named object and a cut-list row or hardware line a carpenter can identify and replace.
- Folded and unfolded positions in the inspector, adding no more than 90 s to the build.

**Non-Goals:**
- Manufacturer CAD downloads or any source outside the owner's library (owner's decision 2026-10-16).
- Engineering a mechanism (forces, spring rates, anchor loads). The assembly is illustrative and says so.
- Animation between poses, or poses for anything other than a `fold_bed`.
- Other assembly kinds (lift-up beds, pocket doors). They come later, as catalog entries.

## Decisions

1. **Assignment is data, not config.** A `hardware_models` table maps a hardware key to a model id, set and cleared from the model library page. Config files are checked in, while model ids live in the database. The build freezes the assignment with its hardware inputs, so a later reassignment does not change a built version.

2. **Placement at real size, anchored by shape.** Each catalog shape defines a mounting face and axes. For example, a knob's back face lies on the front face with its axis along −Y, and a hinge plate's back lies on the side's inner face. The model's stated size is its box. The box is centred on the catalog piece's box and its mounting face aligned. Models must be authored with +Z up and the mounting face towards +Y (behind the item); the assignment page says so. A size outside the tolerance (default 25 %, `config/hardware.yaml` top level) is refused when the assignment is made, naming both sizes.
   - Alternative rejected: scaling the model to the catalog size. That would draw an item at a size it does not have.

3. **Import once, instance many.** The generator imports each assigned file once into a hidden collection, then links object copies (sharing the mesh) at each record. The objects keep the `<line id>#<n>` names and `hardware_key`, so `shown`, the layer map and the `*` are unchanged.

4. **Assemblies in the catalog.** An `assembly` entry lists its components. Each component has an id, a catalog shape or a `part` (cut part with material slot and sizes), its parent component, a pivot (axis and point), and the angle it takes in each pose. `fold_bed` is the one assembly the schema exposes: `module`, `mattress_mm` `{width, length}`, `pose` (`closed` | `open`, default `closed`), and optional `strut_key` and `leg_key`. Derive lays out the components from the module's inner box and the mattress size with fixed proportions in code. Components that are cut parts join the cut list (module `fold-bed`). Hardware components join the hardware with the note "Illustrative: replace with the selected mechanism's part before building". The build-level note says no load or anchoring has been designed.
   - **Assumption (TODO(user)):** a vertical (head-up) fold with the pivot at the module's bottom front, struts on both sides.

5. **Poses by export, not animation.** After the main export, the generator sets each component's pose angle and exports `model-open.glb` again. It does not rebuild. `spec.json` gains `poses: ["closed", "open"]` and the stored `pose`. The build reports the time for each export. A test fails if the second export adds more than 90 s on murphy-bed.
   - Alternative rejected: a glTF animation. It is smaller to store, but the inspector's layer and exploded logic would have to follow moving objects.

6. **Renders name a pose.** The render tools take an optional `pose`, which is refused unless it is in `spec.json` `poses`. The render opens `model.blend` and applies the pose in memory, the way restyle applies its override. Nothing is saved. Each render is still one guard ticket with its own estimate. A `final` still needs the typed "yes".

7. **§8 extension.** The sentence on checked-in headless generators extends from room composition to "a built package's `model.glb` or a model-library file that passed the upload checks and is assigned to a hardware key". Live scripts are unchanged.

## Risks / Trade-offs

- **[Badly authored model sits wrong]** → The authoring convention is stated on the assignment page, the size tolerance is checked, and the owner can unassign.
- **[An illustrative mechanism is taken as a design]** → Every component line and the build note say "illustrative", and the import and the Designer say a product must be selected. Engineering reports never cite it.
- **[Triangle-heavy models slow the build]** → The model library's triangle limit applies, and instancing shares meshes.

## Migration Plan

One Alembic migration (`hardware_models`). Existing versions are untouched. Rollback drops the table and the assembly entries; builds fall back to catalog shapes.

## Open Questions

- TODO(user): fold direction (head-up vertical vs side-tilt horizontal) as the default for `fold_bed`.
- TODO(user): the 25 % size tolerance.
