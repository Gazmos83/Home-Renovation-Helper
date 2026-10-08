## ADDED Requirements

### Requirement: Hinge cup borings are charged with the cut service
Pricing a version SHALL read its hinge cup boring count from the version's drilling list. In `per_cut` mode, it SHALL add one cut-service line: the count times the home store's captured hinge-boring (`topfband_bohrung`) price. In `shared` mode, the line SHALL show the count with no fee. Shelf-pin holes SHALL be listed with their count and no fee, since toom offers no service for them; when the hole heights are a rule in words, they SHALL be listed with no count, and this SHALL NOT mark the pricing incomplete. A version with no hinges SHALL have no hinge-boring line.

#### Scenario: Borings charged per cut
- **WHEN** a version with 8 hinges is priced in `per_cut` mode and the home store's hinge-boring service has a captured price
- **THEN** the pricing holds a hinge-boring line of 8 times that price, and the total includes it

#### Scenario: Borings in shared mode
- **WHEN** the same version is priced in `shared` mode
- **THEN** the pricing lists 8 hinge cup borings with no fee

## MODIFIED Requirements

### Requirement: Missing prices make a pricing incomplete, never guessed
A part, hardware line or band whose material has no price-list entry, a hardware line with no quantity, a part too large for any sheet, a cut whose service cannot be determined, or, in `per_cut` mode, hinge cup borings with no captured hinge-boring price SHALL be listed by name, counted, and SHALL mark the pricing incomplete; no price SHALL be invented for it.

#### Scenario: Unknown hardware
- **WHEN** a hardware line has no entry
- **THEN** the pricing is incomplete and lists that line as unpriced by its id

#### Scenario: Hardware line without a quantity
- **WHEN** a shelf-pin line has no quantity because its data sheet lacks the pins per shelf
- **THEN** the pricing is incomplete and lists that line as unpriced, saying its quantity could not be resolved

#### Scenario: No hinge-boring price
- **WHEN** a version with hinges is priced in `per_cut` mode and the home store has no captured hinge-boring price
- **THEN** the pricing is incomplete and lists the hinge borings as unpriced
