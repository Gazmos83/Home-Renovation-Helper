## ADDED Requirements

### Requirement: The Designer's summary states where each front sits
The summary of the active build's latest version SHALL state, for each front entry of each module, its vertical span in millimetres above the module's bottom face, whether that is the top, the bottom or in between, and the shelves it covers, numbered from the bottom, or that it covers none. The positions SHALL be derived by the application from the stored document, the same way the build places fronts, and SHALL NOT be taken from the brief or the conversation. The summary's label SHALL tell the Designer that these positions describe what is built, that they take precedence over the brief and earlier messages, and to say which version they come from. A module whose positions cannot be derived SHALL be summarised as before, without positions.

#### Scenario: A door at the top covers no shelf
- **WHEN** module `cabinet` is 2238 mm high with 3 shelves 355 mm apart and one front entry of 2 doors 746 mm high
- **THEN** the Designer's context says the doors sit at the top, spanning 1492 to 2238 mm above the module's bottom, and cover no shelf

#### Scenario: Entries are placed top to bottom
- **WHEN** a module 1000 mm high with shelves at the 300, 500 and 700 mm levels lists a 400 mm door entry first and a 600 mm door entry second
- **THEN** the first entry is stated as at the top, spanning 600 to 1000 mm, and the second as at the bottom, spanning 0 to 600 mm, each with the shelves it covers numbered from the bottom

#### Scenario: Stated positions win over the brief
- **WHEN** the brief says the doors are on the bottom and the latest version's doors are at the top
- **THEN** the Designer's context carries the top position and the instruction to prefer it over the brief
