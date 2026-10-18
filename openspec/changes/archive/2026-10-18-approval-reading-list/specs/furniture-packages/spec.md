## ADDED Requirements

### Requirement: A module can state how it is mounted
A module SHALL accept an optional `mounting`, either `floor` or `wall`. Any other value SHALL be refused, naming the field and the allowed values. Leaving it out SHALL mean "not stated".

`mounting` SHALL NOT change the cut list, hardware, drilling list, built model or renders. A document with no `mounting` SHALL derive the same outputs as before.

`revise_package` SHALL be able to set a module's `mounting` or clear it, and its change line SHALL state the mounting before and after.

#### Scenario: Wall cabinet marked
- **WHEN** a document gives module `upper-left` `mounting: "wall"`
- **THEN** it is accepted, and its cut list and hardware equal those of the same document without `mounting`

#### Scenario: Unknown mounting
- **WHEN** a module gives `mounting: "ceiling"`
- **THEN** the document is refused naming `modules.0.mounting` and the values `floor` and `wall`

#### Scenario: Revision sets mounting
- **WHEN** the Designer revises `upper-left` with `mounting: "wall"` and the owner confirms
- **THEN** the new version's module carries `mounting: "wall"`, and the change line reads "upper-left mounting: not stated → wall"
