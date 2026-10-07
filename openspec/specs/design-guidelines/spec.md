# design-guidelines Specification

## Purpose
Defines the architectural guidance the agents use: a corpus of official building and workplace rules and the owner's own notes that the agents search and cite, and a checked-in table of hard numbers applied in code to placements and designs.

## Requirements

### Requirement: Guideline publications are ingested from a checked-in source list
The guideline corpus SHALL be built from a checked-in source list naming each publication with its title, jurisdiction, version or date, licence note and either a file the owner placed under the guidelines folder (`docs/guidelines/`; PDF or Markdown) or an official URL. A file source SHALL be read locally, with no network request, and SHALL be refused when its path leaves the guidelines folder or the file is missing. A URL source SHALL be fetched under the same robots and identity rules as retail pages. PDF, HTML and Markdown text SHALL be extracted, chunked by section where the text marks sections, and embedded into the corpus under the category `guideline`. A source that refuses, cannot be read or is missing SHALL be reported and skipped, never fetched another way. A publication whose host refuses this service SHALL NOT be listed by URL; the owner supplies it as a file. DIN standards and copyrighted guides MAY be ingested only as the owner's own local files and SHALL NOT be committed to the repository.

#### Scenario: Local PDF ingested
- **WHEN** the owner places the ASR A1.2 PDF under the guidelines folder, lists it, and runs the guideline ingestion
- **THEN** its passages are searchable with their rule number, section and publication date, and no network request was made

#### Scenario: Missing file
- **WHEN** a listed file does not exist
- **THEN** the ingestion reports it by source id, skips it and continues with the others

#### Scenario: Path outside the folder
- **WHEN** a listed path leaves the guidelines folder
- **THEN** loading the source list fails naming the source

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
