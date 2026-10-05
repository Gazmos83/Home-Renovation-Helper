# apartment-shell Specification

## Purpose
Defines an apartment in the house file — rooms placed in one plan frame — how Intake proposes it from a plan, and how the Builder generates its shell headless and renders it through the guard.

## Requirements

### Requirement: An apartment groups rooms in one plan frame
The house file SHALL hold apartments by unique name, each with a default ceiling height and wall thickness. A room MAY belong to one apartment; its corners are then in the apartment's plan frame in millimetres, with +x and +y as on the plan. Rooms of one apartment SHALL NOT overlap in area; an edge shared by two rooms is a shared wall. A room belonging to no apartment keeps its own frame.

#### Scenario: Two rooms sharing a wall
- **WHEN** an apartment holds a living room from x 0 to 5200 and a bedroom from x 5200 to 8400 at the same y range
- **THEN** both rooms are stored and the edge at x = 5200 is a shared wall

#### Scenario: Overlapping rooms
- **WHEN** two rooms of one apartment overlap in area
- **THEN** the apartment is refused naming both rooms

### Requirement: Intake proposes a whole apartment from a plan
`record_plan` SHALL take an apartment name, its default heights and every room's outline and openings, validate each room by the room rules and the apartment by the overlap rule, and pause for the owner's `yes` with a summary listing each room's size and area, the openings, and every plausibility warning: a door outside 700–1000 mm wide, a window sill outside 700–1100 mm, a ceiling outside 2300–3200 mm, or a room area more than 5% from a printed area the call states. On `yes` the apartment and its rooms are written; on `no` nothing is written and the reason returns to Intake. A failing room or overlap SHALL be refused naming it with no pause.

#### Scenario: Plan confirmed
- **WHEN** Intake proposes a two-room apartment from a blueprint and the owner answers `yes`
- **THEN** the apartment and both rooms are in the house file and the next turn's context names them

#### Scenario: Area does not match the plan
- **WHEN** a room's outline gives 30.1 m² and the call states the plan prints 32.3 m²
- **THEN** the preview carries a warning naming the room and both areas

### Requirement: The shell is generated headless from the apartment
A shell build SHALL validate the apartment's rooms, then generate in headless Blender floors and ceilings following each room's outline (concave included), walls of the stated thickness with each shared wall built once, and every opening cut through its wall, and publish into `docs/renders/shells/<apartment>/v<N>/` the files `model.blend`, `model.glb`, `shell.json` (the normalised input and the wall list) and a Workbench `screenshot.png`, which is not a render and needs no tier. Each build makes a new version; earlier versions are untouched. `build_shell` (Builder) SHALL start a build, wait for it within the Blender timeout and report the screenshot route.

#### Scenario: Shared wall built once
- **WHEN** the two-room apartment is built
- **THEN** `shell.json` lists one wall for the edge at x = 5200 and the door on it cuts that one wall

#### Scenario: L-shaped room
- **WHEN** an apartment contains an L-shaped room with six corners
- **THEN** its floor and ceiling follow the L and no floor lies outside it

### Requirement: A shell renders only through the guard
A still or turntable of a shell version SHALL go through the render guard exactly like a furniture version: a required tier, raw frame, resolution and engine values refused by name, the estimate stated before the run, and a `final` only after the owner's `yes`. Its files SHALL be served by exact name under the shell version's route.

#### Scenario: Draft shell turntable
- **WHEN** the owner asks for a draft turntable of the apartment shell
- **THEN** a `draft` turntable is rendered into the shell version's `frames/` with its `viewer.html`, and the reply states the estimate first
