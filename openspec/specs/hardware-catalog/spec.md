# hardware-catalog Specification

## Purpose

Defines the checked-in hardware catalog: how each hardware item looks when drawn, how its key is resolved, and how a hand-written hardware line is recognised.

## Requirements

### Requirement: A checked-in catalog describes how hardware looks
The service SHALL load `config/hardware.yaml` at startup. Each entry SHALL give:
- `key` (a hardware key) or `pattern` (a key with one trailing `*`);
- `shape`, from the closed set `hinge_concealed`, `shelf_pin`, `drawer_runner`, `shelf_bracket`, `hanging_rail`, `rail_support`, `bar` and `knob`;
- `size`, with the fields that shape takes, in mm;
- `finish`, from `black`, `aluminium`, `steel`, `brass`, `nickel` and `chrome`;
- `rule_counted`: whether the app's rules count this item;
- `matches`: the phrases that identify the item in a hand-written line.

An exact `key` SHALL win over a `pattern`, and of two patterns the longer prefix SHALL win. A malformed file, an unknown shape or finish, a size field the shape does not take, or two entries with the same key or pattern SHALL stop startup, naming `config/hardware.yaml` and the entry. The sizes describe the drawn shape only and SHALL NOT be used as drilling or engineering values. Adding an entry SHALL need no code change.

The shipped catalog SHALL hold an entry for every key the rules derive by default: `hinge-concealed-110`, `hinge-flap`, `flap-stay`, `push-latch`, `shelf-pin`, `drawer-runner-*`, `confirmat-7x50`, `rail-oval-30x15` and `rail-support-oval`. It SHALL also hold the handle patterns.

#### Scenario: Catalog loads
- **WHEN** the service starts with the shipped catalog
- **THEN** every default rule key resolves to an entry, and `drawer-runner-450` resolves to the `drawer-runner-*` pattern

#### Scenario: Unknown shape stops startup
- **WHEN** an entry names shape `gas_strut`
- **THEN** startup fails naming `config/hardware.yaml`, the entry and `gas_strut`

#### Scenario: Wrong size field
- **WHEN** a `shelf_pin` entry gives `cup_diameter_mm`
- **THEN** startup fails naming the entry and `cup_diameter_mm`

### Requirement: Drawn hardware looks real
Each drawn hardware piece SHALL be built by the headless generator from its catalog shape and size, with bevelled edges, and smoothed where curved. Its material SHALL be a physically based metal for its finish: Principled BSDF looked up by node type, with a metallic value and a roughness per finish fixed in code. The same pieces SHALL appear in `model.blend`, `model.glb`, the screenshots, the inspector and every render tier. No file SHALL be imported to draw them.

#### Scenario: Finish material
- **WHEN** a version with a chrome rail and nickel hinges is built
- **THEN** the rail uses material `Hardware chrome` and the hinges `Hardware nickel`, both metallic

#### Scenario: Same in every view
- **WHEN** a draft turntable of that version is rendered
- **THEN** the rail and hinges appear in its frames as in the inspector
