## ADDED Requirements

### Requirement: A thread's progress names its room and the room's 3D view
The thread progress read SHALL report the conversation's confirmed room or apartment, or nothing when the conversation has confirmed neither. When one is confirmed the read SHALL give its name and its scope (`room` or `apartment`), and whether its composition's latest version has a 3D model. When it has one, the read SHALL give the composition's slug and name the model and the surface map by their composition routes. When a composition exists the read SHALL also list its newest five versions, newest first, each with its number, build status, and, when that version has `model.glb`, its model, surface map and dimensions by their composition routes. The read SHALL report only this conversation's own room or apartment, never one confirmed in another conversation or the room a piece is assigned to, and SHALL contain no file-system path.

#### Scenario: No room confirmed
- **WHEN** the owner reads the progress of a thread that has confirmed no room or apartment
- **THEN** the progress reports no room

#### Scenario: Room without a composition
- **WHEN** the thread has confirmed room `Hall` and `Hall` has no composition
- **THEN** the progress names `Hall` with scope `room` and reports no 3D model

#### Scenario: Room with a 3D view
- **WHEN** the thread has confirmed room `Hall` and composition `Hall`'s latest version has `model.glb` and its surface map
- **THEN** the progress names `Hall`, gives the composition's slug, and names the model and the surface map by their composition routes

#### Scenario: Latest version without a model
- **WHEN** composition `Hall`'s latest version was built before models were published and has no `model.glb`
- **THEN** the progress names `Hall` and reports no 3D model

#### Scenario: Apartment scope
- **WHEN** the thread has confirmed apartment `Flat` and composition `Flat` has a 3D model
- **THEN** the progress names `Flat` with scope `apartment` and gives its composition's slug and routes

#### Scenario: Another conversation's room
- **WHEN** the thread has confirmed no room, another thread has confirmed `Hall`, and the thread's piece is assigned to `Hall`
- **THEN** the progress reports no room

#### Scenario: Newest five versions
- **WHEN** the thread has confirmed `Hall` and composition `Hall` has versions 1 to 6, of which version 2 has no `model.glb`
- **THEN** the progress lists versions 6, 5, 4, 3 and 2, each of 6 to 3 with its model, surface map and dimensions routes, and version 2 with none
