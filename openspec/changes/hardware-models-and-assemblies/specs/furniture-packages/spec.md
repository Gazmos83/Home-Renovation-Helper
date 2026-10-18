## ADDED Requirements

### Requirement: A build can carry an illustrative fold-down bed
A custom build SHALL accept at most one `fold_bed`, with:
- `module`: the id of the module that houses it;
- `mattress_mm`: `{width, length}`;
- `pose`: `closed` or `open`, default `closed`;
- optional `strut_key` and `leg_key`.

It SHALL be refused, naming the field, when the module does not exist, when the mattress does not fit the module's inner opening, or when the open platform would reach below the floor.

Derive SHALL lay out the `fold-bed-vertical` assembly from the module's inner box and the mattress size:
- every component that is a cut part SHALL be one cut-list row in module `fold-bed`;
- every hardware component SHALL be one hardware line, noted "Illustrative: replace with the selected mechanism's part before building".

The build's notes SHALL say that no load, spring force or anchoring has been designed. Every component SHALL be drawn as its own object named by its component id, in a `mechanism` layer, parented to the housing module.

#### Scenario: Components listed and drawn
- **WHEN** a build carries `fold_bed` on module `bed-cabinet` with a 1600 × 2000 mm mattress
- **THEN** the cut list holds the platform frame rows, and the hardware holds the pivot brackets, arms, struts, legs, wall rail and anchors, each noted as illustrative. Each one is a separate object in the `mechanism` layer.

#### Scenario: Mattress too big
- **WHEN** the mattress is wider than the module's inner opening
- **THEN** it is refused naming `fold_bed.mattress_mm.width` and the opening width

### Requirement: A piece with an assembly is exported in each pose
A build whose spec carries an assembly SHALL write `model.glb` in the stored pose and `model-open.glb` (or `model-closed.glb`, for whichever pose is not stored) in the other. It SHALL list `poses` and the stored `pose` in `spec.json`, and report each export's time in its status. Exporting the second pose SHALL add no more than 90 s to the build. A build without an assembly SHALL write only `model.glb`, as before.

#### Scenario: Both poses written
- **WHEN** a build with a closed `fold_bed` finishes
- **THEN** its folder holds `model.glb` (closed) and `model-open.glb`, and `spec.json` lists both poses

#### Scenario: Time limit
- **WHEN** murphy-bed with a `fold_bed` is built on the laptop
- **THEN** the second export adds no more than 90 s, as reported in its status
