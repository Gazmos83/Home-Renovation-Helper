# restyle-variants Specification

## Purpose

Lets the owner see an approved piece in other colours and finishes, or an approved room in other styles, as draft pictures from one short request, without changing the spec's materials, cut list or prices. A look the owner likes becomes real only through the normal revision.

## Requirements

### Requirement: Looks and styles are named presets in configuration
The service SHALL read look presets (for pieces) and style presets (for rooms) from configuration and SHALL refuse to start when a preset has a duplicate id, an unknown key, a colour that is not `#rrggbb`, or a roughness or metallic value outside 0 to 1. A look preset SHALL state a colour, a roughness, a metallic value and optionally a wood-grain flag. A style preset SHALL state a wall, ceiling and floor colour and roughness, a world colour and strength, a colour map for stand-ins by name, and a fallback tint. The shipped presets SHALL include at least four room styles and six piece looks.

#### Scenario: Shipped presets load
- **WHEN** the service starts with the shipped configuration
- **THEN** at least four style presets and six look presets are available and the startup summary lists their ids

#### Scenario: Bad colour
- **WHEN** a look preset has the colour `walnut`
- **THEN** startup fails naming the preset and `colour`

### Requirement: A look applies per slot and never changes the spec
A piece restyle request SHALL name, for each variant, a look preset for each material slot it changes, keyed by the slot names of that version's stored spec. A slot name the spec does not hold SHALL be refused naming the slot and listing the slots that exist. Slots the request omits SHALL keep their own appearance, except that slots whose spec names the same material are one material and SHALL be named together with the same look, and are refused by name otherwise. The version's `spec.json`, `materials`, cut list, prices, `model.blend` and own render files SHALL be byte-identical after any restyle.

#### Scenario: Two slots restyled
- **WHEN** a restyle of `hall-bench` v2 gives `carcass` the look `walnut` and `fronts` the look `sage-green`
- **THEN** the variant shows those colours on those slots, and `v2/spec.json` and `v2/model.blend` are unchanged

#### Scenario: Unknown slot
- **WHEN** a restyle names the slot `legs` and the spec holds only `carcass` and `fronts`
- **THEN** it is refused naming `legs` and listing `carcass` and `fronts`, and nothing is rendered

#### Scenario: Unknown field refused
- **WHEN** a restyle document carries the field `thickness_mm`
- **THEN** it is refused naming `thickness_mm` and nothing is rendered

#### Scenario: Slots sharing a material
- **WHEN** the slots `carcass` and `shelves` name the same material and a variant gives them different looks, or names only one of them
- **THEN** it is refused naming both slots, and nothing is rendered

### Requirement: A style applies to a composition's surfaces
A room restyle request SHALL name a style preset and a composition version, which is rebuilt in memory from its stored document. The style SHALL change the walls, ceiling and floor, the world light, and the colour of each stand-in (by the colour map, else the fallback tint) as listed in that version's surface map. Placed pieces and library models SHALL keep their own appearance. The composition's items, sizes and placements SHALL NOT change.

#### Scenario: Room restyled
- **WHEN** the style `japandi` is applied to `Wohnen` v3 that holds one approved piece, one stand-in `sofa` and one library model
- **THEN** the walls, floor, ceiling and light follow the style, the sofa takes its mapped colour, and the piece and the library model look as built

#### Scenario: Composition not built
- **WHEN** a restyle is requested for a composition version whose build has not succeeded
- **THEN** it is refused stating the build has not succeeded, and nothing is rendered

### Requirement: A variant renders only through the guard, at draft or preview
A restyle request SHALL require a tier. Tiers `draft` and `preview` SHALL be accepted; `final` SHALL be refused saying a restyle is a concept picture and a final is rendered from a real revision. Raw frame, resolution or engine values SHALL be refused by name. The estimate for the whole batch (one still per variant) SHALL be stated once before any run. The batch SHALL render one still per variant, each under its own authorisation issued for that variant only and together with the batch estimate, one process at a time, and a variant that fails SHALL be reported by id without discarding the finished ones.

#### Scenario: Three variants at draft
- **WHEN** a `draft` restyle of three style presets is requested
- **THEN** one estimate for three stills is stated, then three 600 × 600 Eevee stills are published

#### Scenario: Final refused
- **WHEN** a restyle is requested at tier `final`
- **THEN** it is refused saying a restyle is a concept picture, and no process starts

#### Scenario: One variant fails
- **WHEN** the second of three variants fails to render
- **THEN** the first and third are published and the reply names the second as failed

### Requirement: Variants publish beside the version and are marked appearance only
Each variant SHALL be published atomically in `variants/<variant-id>/` of its version with `still.png` and `scene.json`. `scene.json` SHALL record source `restyle`, the preset ids and the slot mapping, the tier, and the note "appearance only, not a priced material". The version's own `still.png`, `frames/`, `viewer.html` and `scene.json` SHALL NOT change. A version SHALL hold at most 12 variants; a further request SHALL replace the oldest, and the reply SHALL say so.

#### Scenario: Variant folder
- **WHEN** a `draft` restyle with the look `walnut` completes
- **THEN** `variants/<id>/still.png` and `scene.json` exist, `scene.json` records source `restyle` and the note, and the version's own `still.png` is unchanged

#### Scenario: Thirteenth variant
- **WHEN** a version already holds 12 variants and another is requested
- **THEN** the oldest is replaced and the reply says which

### Requirement: Keeping a look goes through the normal revision
Choosing a variant SHALL NOT change any spec or approved version. Keeping a piece look SHALL hand the owner's request to the Designer in the conversation, asking which real material to use and whether it is priced before anything changes; the Designer's ordinary revision then pauses for the owner's confirmation, and a slot whose material is unpriced is marked pricing-incomplete, never guessed. A room style SHALL NOT be kept by this change: a composition carries no style field, so a room variant is a picture to look at, and saving a style on a composition is a separate change.

#### Scenario: Keep walnut
- **WHEN** the owner keeps the `walnut` variant of `hall-bench` v2
- **THEN** a request naming the slot and the look goes to the conversation, and no new version exists until the Designer's revision confirmation is answered `yes`

#### Scenario: Room variant
- **WHEN** a room variant is shown
- **THEN** it offers no "keep" action

### Requirement: The model supplies only validated data
Preset ids and slot mappings from a model SHALL be validated before the render script sees them. A look or style composed from free text SHALL be limited to the preset fields and refused by field name otherwise. The restyle render SHALL be a checked-in headless script, not a live script. The homeowner view of a variant SHALL show the picture, the preset names and the appearance note, and no model, prompt, token or cost.

#### Scenario: Free-text look
- **WHEN** the Designer composes a look "dark green, satin" as `#2f3b34`, roughness 0.35, metallic 0
- **THEN** it is validated and used for that request only

#### Scenario: Extra field
- **WHEN** a composed look carries `texture_path`
- **THEN** it is refused naming `texture_path`
