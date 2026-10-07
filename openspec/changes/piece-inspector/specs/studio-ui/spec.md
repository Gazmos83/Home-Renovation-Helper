## ADDED Requirements

### Requirement: A piece version can be inspected in 3D
The Studio SHALL have an owner-only page per piece version at `/pieces/<package-id>/versions/<n>`. For a built version it SHALL show the version's `model.glb` in a 3D view, with:
- **Camera:** free rotate and zoom with the mouse, and buttons for the Iso, Front, Side and Plan cameras.
- **Modes:** Workshop (lit), Blueprint (flat light with the parts' edges drawn) and Exploded. Exploded has a slider that moves each module away from the piece's centre, with its parts following. The direction comes from the module positions in the version's `spec.json`.
- **Layer switches:** one for each layer the version's `spec.json` names, plus `dimensions`. Switching a layer off hides exactly the meshes the layer map lists under it. A mesh the map does not name stays visible.
- **Overall dimensions:** W, H and D in mm from `spec.json` `overall`, drawn beside the model. Hidden in Exploded mode and when `dimensions` is off.
- **Scale:** a floor grid and a contact shadow.
- **Straight-on views:** `front.png`, `side.png` and `top.png`, when the version has them.

A Cut list tab SHALL show the version's parts (id, name, quantity, length, width, thickness, material, grain, banding, notes, module) and its hardware (id, item, quantity, notes), both read from `spec.json`. When the parts belong to more than one module, the tab SHALL offer a filter with "All" and one choice per module, in the order the parts first name them. Each module is labelled by its name from `spec.json` `module_names`, "Extra parts" for `extras`, and otherwise its id. Choosing a module SHALL show only that module's parts, with their count of rows and pieces. The parts table SHALL name each part's module by that same label. Hardware is not divided by module.

Every measurement on the page SHALL come from the version's own files. The 3D view SHALL be loaded only on this page.

A version that is not built SHALL show its build state instead of the 3D view. A version, or a file it lacks, SHALL be named in plain words rather than shown as an error code. The page SHALL NOT show a model name, prompt, token count or cost, and it SHALL pass a recorded browser check before it counts as done.

#### Scenario: Built version inspected
- **WHEN** the owner opens `/pieces/murphy-bed/versions/1`
- **THEN** the model is shown from the Iso camera with W 3000 mm, H 2900 mm and D 450 mm beside it, and the layer switches carcass, backs, shelves, fronts, extras and dimensions

#### Scenario: Front camera
- **WHEN** the owner presses Front
- **THEN** the view looks straight at the piece's front

#### Scenario: Exploded
- **WHEN** the owner chooses Exploded and moves the slider to its end
- **THEN** each module moves away from the centre along its own direction, and the dimension overlay is hidden

#### Scenario: Layer off
- **WHEN** the owner switches `fronts` off
- **THEN** every mesh the layer map lists under `fronts` is hidden and all others stay visible

#### Scenario: Cut list
- **WHEN** the owner opens the Cut list tab
- **THEN** every row of `spec.json` `parts` and `hardware` is listed with its figures

#### Scenario: Cut list filtered by module
- **WHEN** the owner opens the Cut list of `murphy-bed` version 2 and chooses "Left lower cabinet"
- **THEN** only the parts of module `left-base` are listed, with their row and piece counts, and choosing "All" lists every part again

#### Scenario: Version built before the views
- **WHEN** the owner inspects a version that has no `front.png`
- **THEN** the 3D view, the overlay and the cut list are shown and the straight-on views are left out

#### Scenario: Not built yet
- **WHEN** the owner opens a version whose build is running
- **THEN** the page says the version is building and shows no 3D view

### Requirement: The inspector is reachable from the Pieces page and the conversation
The Pieces page SHALL offer an "Inspect" link for every built version. A conversation's project panel SHALL offer an "Inspect" link for the bound piece's latest version once it is built. Both links SHALL open the inspector page for that version in the Studio.

#### Scenario: Inspect from the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers "Inspect" and version 3 does not

#### Scenario: Inspect from the conversation
- **WHEN** the bound piece's version 1 has just been built
- **THEN** the panel shows an "Inspect" link to `/pieces/<package-id>/versions/1`
