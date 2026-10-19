## ADDED Requirements

### Requirement: A lamp item may carry a light
A `stand-in` or `model` item in a composition document MAY carry `light`, an object with exactly these keys:
- `type`: `"point"` or `"spot"`;
- `lumens`: a whole number from 10 to 10 000;
- `kelvin`: a whole number from 1800 to 6500.

A missing key, an unknown key or a value outside these sets or ranges SHALL be refused naming the item and the key, and nothing is built. A `piece` SHALL NOT carry `light`; it is refused as an unknown field. A floor-layer item SHALL NOT carry `light`; it is refused naming the item and `light`. A composition SHALL hold at most the configured number of item lights (16 by default); more SHALL be refused naming the limit. The normalised document SHALL keep `light` as given.

The light SHALL be centred on the item's footprint. On a ceiling-layer item it SHALL be 50 mm above the item's lowest point. On a standing item it SHALL be 50 mm below the item's top. A `spot` light SHALL point straight down.

#### Scenario: Pendant with a warm light
- **WHEN** the ceiling-layer model `pendant` of 500 × 500 × 1100 mm in a room with a 2500 mm ceiling carries `light: {type: "point", lumens: 800, kelvin: 2700}`
- **THEN** it is accepted, its normalised form keeps the light, and the light is placed at the pendant's footprint centre, 1450 mm above the floor

#### Scenario: Standing floor lamp
- **WHEN** a standing stand-in `floor-lamp` of 400 × 400 × 1600 mm carries `light: {type: "spot", lumens: 600, kelvin: 3000}`
- **THEN** it is accepted, and the light is at 1550 mm, pointing down

#### Scenario: Light on a piece
- **WHEN** a `piece` item carries `light`
- **THEN** it is refused naming `light` as an unknown field

#### Scenario: Light on a rug
- **WHEN** a floor-layer stand-in `rug` carries `light`
- **THEN** it is refused naming `rug` and `light`

#### Scenario: Unknown light type
- **WHEN** an item's light has `type: "area"`
- **THEN** it is refused naming the item and `type`, and nothing is built

#### Scenario: Brightness out of range
- **WHEN** an item's light has `lumens: 20000`
- **THEN** it is refused naming the item and `lumens`

#### Scenario: Too many lights
- **WHEN** a composition holds 17 items with a light and the limit is 16
- **THEN** it is refused naming the limit of 16 lights

### Requirement: Lamp lights are built, dim the room rig and are reported
The headless build of a composition, and every render, restyle variant and detail-pass copy rebuilt from it, SHALL add one light for each item that carries one, at the position stated above. Its colour SHALL follow its kelvin value: lower values warmer (more red), higher values cooler (more blue). Its power SHALL be its lumens times the configured watts per lumen. The item's own meshes SHALL NOT cast shadows, so a light inside a shade or a stand-in box reaches the room. The light SHALL be named after its item, so the detail pass can find it.

When a room holds at least one item with a light, that room's general lights SHALL be dimmed by the configured factor (0.5 by default). A room without item lights SHALL be lit exactly as before this change. In an apartment each room SHALL be dimmed on its own.

The build report SHALL list, for each item with a light, its type, lumens, kelvin, power in watts and position in millimetres, and SHALL state each room's rig factor. A composition document without any `light` SHALL build exactly as before this change.

#### Scenario: Draft of a room with a pendant light
- **WHEN** `Wohnen` is built with the lit ceiling-layer `pendant` (800 lm, 2700 K) and the configured factor is 0.05 W per lumen
- **THEN** the scene holds a 40 W warm point light named after `pendant` at 1450 mm, the pendant's meshes cast no shadow, `Wohnen`'s general lights are at half their usual power, and the build report lists the light and the rig factor 0.5

#### Scenario: Room without lamps unchanged
- **WHEN** `Hall` is built with no item lights
- **THEN** its general lights have the same power as before this change, and the build report states the rig factor 1.0

#### Scenario: Apartment dims only the lit room
- **WHEN** an apartment is built with one lit lamp in `Wohnen` and none in `Bad`
- **THEN** only `Wohnen`'s general lights are dimmed

#### Scenario: Render shows the lamp
- **WHEN** a `draft` turntable of a composition version with a lit lamp is rendered through the guard
- **THEN** the frames are rendered on Eevee with the lamp light present, and the guard's tier, estimate and approval rules apply unchanged
