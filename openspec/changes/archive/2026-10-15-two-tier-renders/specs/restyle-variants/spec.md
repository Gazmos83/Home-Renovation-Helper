## RENAMED Requirements

- FROM: `### Requirement: A variant renders only through the guard, at draft or preview`
- TO: `### Requirement: A variant renders only through the guard, as a draft turntable`

## MODIFIED Requirements

### Requirement: A variant renders only through the guard, as a draft turntable
A restyle request SHALL require a tier. Tier `draft` SHALL be accepted. `final` SHALL be refused, saying a restyle is a concept picture and a final is rendered from a real revision. Any other tier, `preview` included, SHALL be refused as unknown. Raw frame, resolution or engine values SHALL be refused by name. Each variant SHALL be rendered as a draft turntable. The estimate for the whole batch (one draft turntable per variant) SHALL be stated once before any run. Each variant SHALL render under its own authorisation, issued for that variant only and together with the batch estimate, one process at a time. A variant that fails SHALL be reported by id without discarding the finished ones.

#### Scenario: Three variants at draft
- **WHEN** a `draft` restyle of three style presets is requested
- **THEN** one estimate for three draft turntables is stated, then three turntables of 12 frames at 800 × 800 on Eevee are published

#### Scenario: Preview refused
- **WHEN** a restyle is requested at tier `preview`
- **THEN** it is refused naming `preview` as an unknown tier, and no process starts

#### Scenario: Final refused
- **WHEN** a restyle is requested at tier `final`
- **THEN** it is refused saying a restyle is a concept picture, and no process starts

#### Scenario: One variant fails
- **WHEN** the second of three variants fails to render
- **THEN** the first and third are published and the reply names the second as failed

### Requirement: Variants publish beside the version and are marked appearance only
Each variant SHALL be published atomically in `variants/<variant-id>/` of its version with `frames/`, `viewer.html`, `scene.json`, and a `still.png` that is a copy of its first frame. `scene.json` SHALL record source `restyle`, the preset ids and the slot mapping, the tier, the frame count, and the note "appearance only, not a priced material". A variant's frames SHALL be served by index from the version's file routes, like the version's own frames, and a variant id that the version does not hold SHALL be refused as not found. The version's own `still.png`, `frames/`, `viewer.html` and `scene.json` SHALL NOT change. A version SHALL hold at most 12 variants; a further request SHALL replace the oldest, and the reply SHALL say so.

#### Scenario: Variant folder
- **WHEN** a `draft` restyle with the look `walnut` completes
- **THEN** `variants/<id>/frames/` holds exactly `frame_000.png` … `frame_011.png` at 800 × 800, `viewer.html` names 12 frames, `still.png` equals `frame_000.png`, `scene.json` records source `restyle` and the note, and the version's own `still.png` and `frames/` are unchanged

#### Scenario: Variant frame served
- **WHEN** the owner's session asks for frame 5 of the `walnut` variant of `hall-bench` v2
- **THEN** `variants/<id>/frames/frame_005.png` is returned, and an id the version does not hold is refused as not found

#### Scenario: Thirteenth variant
- **WHEN** a version already holds 12 variants and another is requested
- **THEN** the oldest is replaced and the reply says which

## ADDED Requirements

### Requirement: A piece variant is a rateable render
Each published restyle variant of a piece version SHALL be a render of that version that the owner can rate up or down with a comment, like the version's own renders. A variant of a composition SHALL be viewable but SHALL NOT be rateable. Rating a variant SHALL NOT change the spec, its materials, the cut list or prices.

#### Scenario: Variant listed with rating controls
- **WHEN** `hall-bench` v2 holds a published `walnut` variant
- **THEN** the version's renders include the variant with its label, tier `draft` and rating controls

#### Scenario: Rating changes nothing in the design
- **WHEN** the owner rates the `walnut` variant up
- **THEN** `spec.json`, the cut list and the version's materials are unchanged
