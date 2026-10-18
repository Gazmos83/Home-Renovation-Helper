## ADDED Requirements

### Requirement: The inspector switches between a piece's poses
When a version's `spec.json` lists more than one pose, the inspector SHALL show a Folded / Unfolded switch, starting on the stored pose. It SHALL load that pose's model file only when chosen, and keep the camera, the layer switches and the exploded setting. A version with one pose SHALL show no switch. The switch SHALL pass a recorded browser check before it counts as done.

#### Scenario: Unfolded
- **WHEN** the owner opens a closed fold-bed version and chooses Unfolded
- **THEN** `model-open.glb` is loaded and shown from the same camera, with the same layers on

#### Scenario: No switch
- **WHEN** a version has no assembly
- **THEN** no pose switch is shown

### Requirement: The model library assigns models to hardware keys
The model library page SHALL let the owner assign a `ready` model to a hardware key, chosen from the catalog keys, and clear it. It SHALL show the authoring convention and each model's assigned keys, and show a refusal in plain words beside the control. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Assign from the page
- **WHEN** the owner chooses `handle-knob-brass` for the `brass-knob` model
- **THEN** the model's row lists `handle-knob-brass`
