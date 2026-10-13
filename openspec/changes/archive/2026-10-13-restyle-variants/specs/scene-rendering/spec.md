## ADDED Requirements

### Requirement: A restyle still renders an in-memory override of the built model
A restyle still SHALL open the version's built `model.blend`, apply the look or style in memory, render one still at the tier's resolution and engine, and close without saving. It SHALL publish into `variants/<variant-id>/` of the version, and SHALL NOT replace or alter the version's own `still.png`, `frames/`, `viewer.html` or `model.blend`. It SHALL be refused with a stated reason when the version has not succeeded or its `model.blend` is missing.

#### Scenario: Built model untouched
- **WHEN** a draft restyle still completes
- **THEN** `model.blend` is byte-identical to before and the version's own `still.png` is unchanged

#### Scenario: Version not built
- **WHEN** a restyle is requested for a version whose build has not succeeded
- **THEN** it is refused stating the build has not succeeded
