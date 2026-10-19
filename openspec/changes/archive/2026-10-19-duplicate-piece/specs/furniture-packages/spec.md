## ADDED Requirements

### Requirement: A piece version can be duplicated into a new piece
The owner SHALL be able to make a new piece from one version of an existing piece. The request names:
- the source piece and version;
- the copy's name;
- the copy's id.

The id SHALL be a valid package id that no piece or version folder uses yet. The name SHALL be non-empty and SHALL NOT equal any existing piece's name, ignoring case.

The source version's design SHALL be validated against the current schema before anything is written. A field the schema refuses SHALL be refused by name, and nothing is created.

On success:
- **New piece:** version 1 of the new piece holds the source version's design with only its name replaced, and the source version's frozen hardware inputs unchanged.
- **Records:** the new piece is recorded with the source piece's room and brief, and version 1 carries the change line "duplicated from `<source id>` v`<n>`".
- **Build:** version 1's headless build starts. No render is started, and no render guard ticket is used.
- **Conversation:** a new conversation bound to the new piece is created, and its id is returned.

These SHALL NOT be copied: approvals, reviews, verdicts, render feedback, renders, pricings, detail passes and saved places in rooms. The source piece, its versions and its conversations SHALL be left unchanged.

A duplicate SHALL be refused, with the reason and with nothing changed, when any of these holds:
- the source version does not exist;
- the source version has no design;
- the id is taken;
- the name is empty or already a piece's name;
- builds are unavailable on this host.

#### Scenario: Duplicate the latest version
- **WHEN** the owner duplicates `sideboard-1200` v3 as "Sideboard (copy)" with id `sideboard-1200-copy`
- **THEN** `sideboard-1200-copy/v1/` holds v3's design named "Sideboard (copy)" and v3's hardware inputs
- **AND** the piece is recorded in `sideboard-1200`'s room with the change line "duplicated from `sideboard-1200` v3"
- **AND** its build is queued, a new conversation bound to it is returned, and `sideboard-1200` is unchanged

#### Scenario: Duplicate an earlier version
- **WHEN** the owner duplicates `sideboard-1200` v1 while v3 is the latest
- **THEN** the copy's v1 holds v1's design, not v3's

#### Scenario: Approval is not copied
- **WHEN** the source version is approved and priced
- **THEN** the copy's v1 is not approved and has no pricing

#### Scenario: Id taken
- **WHEN** the owner duplicates with id `sideboard-1200`
- **THEN** the duplicate is refused naming the id as already in use, and nothing is created

#### Scenario: Name already used
- **WHEN** the owner duplicates `sideboard-1200` as "sideboard"
- **THEN** the duplicate is refused saying a piece already has that name, and nothing is created

#### Scenario: Design no longer valid
- **WHEN** the source version's design carries a field the current schema does not define
- **THEN** the duplicate is refused naming the field, and nothing is created
