## ADDED Requirements

### Requirement: An assigned library model replaces a catalog shape
Where a hardware key with an assigned model is drawn, the generator SHALL use that model instead of the catalog shape. The model is placed at its stated real size, with its box centred on the catalog piece's box and its mounting face on the shape's mounting face. Each assigned file SHALL be imported once per build and instanced at every position, keeping the `<line id>#<n>` names, the `hardware` layer and `hardware_key`. A version SHALL keep the assignment frozen with its hardware inputs, so it is built the same way on a rebuild. A key without an assignment, or whose model is no longer `ready`, SHALL be drawn from its catalog shape.

#### Scenario: Knob model used
- **WHEN** `handle-knob-brass` is assigned the owner's `brass-knob` model and a version with four knobs is built
- **THEN** the four knob objects are instances of that model at its stated size, named as before, and `shown` is unchanged

#### Scenario: Model removed
- **WHEN** the assigned model is deleted and the piece is rebuilt as a new version
- **THEN** the knobs are drawn from the catalog shape

### Requirement: The catalog describes assemblies
A catalog entry MAY be an `assembly` listing components. Each component SHALL have:
- an id;
- a catalog shape or a cut part (material slot and sizes);
- a parent component;
- a pivot axis and point;
- its angle in each pose.

An assembly SHALL be refused at startup, naming the entry and the component, when:
- a component names an unknown shape;
- a parent is missing or forms a cycle;
- a pose angle is outside the component's limits.

The shipped catalog SHALL hold the `fold-bed-vertical` assembly. Its components are two pivot brackets, two side arms, two lift struts, the platform frame, two folding legs, a wall rail and its anchors.

#### Scenario: Assembly loads
- **WHEN** the service starts with the shipped catalog
- **THEN** `fold-bed-vertical` lists its components with poses `closed` and `open`

#### Scenario: Cycle refused
- **WHEN** two components name each other as parent
- **THEN** startup fails naming the entry and both components
