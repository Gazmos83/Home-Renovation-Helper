## Purpose

Defines the architectural guidance the agents use: a corpus of official building and workplace rules and the owner's own notes that the agents search and cite, and a checked-in table of hard numbers applied in code to placements and designs.

## ADDED Requirements

### Requirement: Official guidelines are ingested from their publications
The guideline corpus SHALL be built from a checked-in source list naming each publication (the Bauordnung Berlin, the Musterbauordnung, the BAuA technical rules for workplaces), its official URL, jurisdiction, version or date and licence note, fetched under the same robots and identity rules as retail pages, with PDF and HTML text extracted, chunked by section where the text marks sections, and embedded into the corpus under the category `guideline`. A source that refuses or cannot be read SHALL be reported and skipped, never fetched another way. DIN standards and copyrighted guides SHALL NOT be ingested.

#### Scenario: ASR ingested
- **WHEN** the guideline ingestion runs
- **THEN** the ASR passages are searchable with their rule number, section and publication date

### Requirement: The owner can add guideline notes by hand
The owner SHALL be able to create, edit and delete guideline notes, each with a title, text, an optional number with unit, and a required source citation (for example a book and page); notes SHALL be added to the corpus as `guideline` passages from the source `owner` and removed from it when deleted.

#### Scenario: Note from a book
- **WHEN** the owner adds a note "passage in front of a wardrobe: 900 mm" citing a page of their own book
- **THEN** `search_guidelines` can return it with that citation

### Requirement: Guidelines are searched and cited
`search_guidelines` SHALL return the matching guideline passages with their publication or note, section and date, wrapped as untrusted content, and SHALL say when nothing matched; an agent quoting a guideline SHALL name its source. The Designer and the Researcher SHALL have the tool.

#### Scenario: Ceiling height asked
- **WHEN** the owner asks the Designer what ceiling height a room needs in Berlin
- **THEN** the reply cites the Bauordnung Berlin passage it used, or says it found none

### Requirement: Hard design rules are applied in code
A checked-in design-rules table SHALL hold each rule's id, what it applies to (a placement in a room, or a piece), the measurement checked, its limit and unit, its severity (`warn` or `refuse`) and its source citation; a rule without a citation SHALL fail startup naming the rule. `room_fit` SHALL apply placement rules (for example the clear passage in front of a piece and a door's swing area) and the Designer's create and revise previews SHALL apply piece rules (for example a worktop height range or a shelf span for a board thickness). A `warn` breach SHALL appear in the result and the confirmation summary naming the rule, the measured value, the limit and the source; a `refuse` breach SHALL refuse the action the same way. A rule's limit SHALL be quoted from its cited source.

#### Scenario: Passage too narrow
- **WHEN** a wardrobe placed in a room leaves less clear passage in front of it than the placement rule's limit
- **THEN** `room_fit` returns the placement with a warning naming the rule, the measured passage, the limit and its source

#### Scenario: Rule without a source
- **WHEN** the rules table carries a rule with no citation
- **THEN** startup fails naming the rule id
