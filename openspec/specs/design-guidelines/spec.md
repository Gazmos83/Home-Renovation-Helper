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
`search_guidelines` SHALL return the matching guideline passages with their publication, note or hardware data sheet, section and date, wrapped as untrusted content, and SHALL say when nothing matched; an agent quoting a guideline SHALL name its source. The Designer and the Researcher SHALL have the tool. The Researcher SHALL use it for a design rule or a number from a guideline, a note or a data sheet, name the publication, note or data sheet and its section, and say it found no guideline rather than quote a rule from memory.

#### Scenario: Ceiling height asked
- **WHEN** the owner asks the Designer what ceiling height a room needs in Berlin
- **THEN** the reply cites the Bauordnung Berlin passage it used, or says it found none

#### Scenario: Researcher asked for a shelf rule
- **WHEN** the owner asks the Researcher how many brackets a 1500 mm shelf needs
- **THEN** the Researcher calls `search_guidelines` and its reply names `topnotch-shelf-brackets` and the section it used, or says it found no guideline

### Requirement: Hard design rules are applied in code
A checked-in design-rules table SHALL hold each rule's id, what it applies to (a placement in a room, or a piece), the measurement checked, its limit and unit, its severity (`warn` or `refuse`) and its source citation; a rule without a citation SHALL fail startup naming the rule. `room_fit` SHALL apply placement rules (for example the clear passage in front of a piece and a door's swing area) and the Designer's create and revise previews SHALL apply piece rules (for example a worktop height range, a shelf span for a board thickness, or a wall shelf's bracket count and spacing). The shelf span SHALL be checked for fixed and adjustable shelves alike. A `warn` breach SHALL appear in the result and the confirmation summary naming the rule, the measured value, the limit and the source; a `refuse` breach SHALL refuse the action the same way. A rule's limit SHALL be quoted from its cited source. More than one rule naming the same bracket check SHALL fail startup naming both rules.

#### Scenario: Passage too narrow
- **WHEN** a wardrobe placed in a room leaves less clear passage in front of it than the placement rule's limit
- **THEN** `room_fit` returns the placement with a warning naming the rule, the measured passage, the limit and its source

#### Scenario: Rule without a source
- **WHEN** the rules table carries a rule with no citation
- **THEN** startup fails naming the rule id

#### Scenario: Adjustable shelves judged for span
- **WHEN** a module with only adjustable shelves is wider than the span rule allows for its board thickness
- **THEN** the preview warns naming the span rule, the measured span, the limit and the source

### Requirement: Hardware items carry cited drilling data
The owner SHALL be able to create, edit and delete one data sheet per hardware item. Each data sheet SHALL have:
- the item's hardware key, unique among data sheets;
- its kind, `hinge` or `shelf_pin`;
- the maker and the model;
- the drilling values its kind takes, each optional and in mm unless it is a count. A measured value SHALL be either one number or a range with a minimum below its maximum, as its source gives it. A count SHALL be one whole number;
- a source.

A `hinge` sheet SHALL take:
- the cup diameter, the cup depth and the cup edge distance;
- the end distance from the door's ends;
- an optional count table of door heights and hinges;
- the mounting-plate item key, the plate setback and the plate hole spacing.

A `shelf_pin` sheet SHALL take:
- the hole diameter and the hole depth;
- the pitch;
- the first and last hole heights;
- the front and rear setbacks;
- the pins per shelf.

The source SHALL be one of two kinds:
- `toom`: the toom product page URL, and optionally the maker's data-sheet URL linked from it. A page URL off the toom host SHALL be refused naming the host.
- `manual`: for an item bought elsewhere, a citation of the item's own data sheet entered by hand, such as the document, page and date.

A data sheet SHALL be refused when it cites a URL or citation another data sheet already cites and its maker or model differs. A value SHALL NOT be accepted without its source. Prices SHALL stay in the price list: an item bought elsewhere is priced by a `manual` price-list entry under the same key. Data sheets SHALL be added to the corpus as `guideline` passages naming the item and its source, and SHALL be removed from it when deleted. No data-sheet value SHALL be shipped in the repository.

A range whose minimum is not below its maximum, or a range given for a count, SHALL be refused naming the value.

#### Scenario: Ranged value kept
- **WHEN** the owner enters a hinge's end distance as 80–120 mm from its cited data sheet
- **THEN** the data sheet holds the range with its source, and the value is never stored as one number

#### Scenario: Range on a count
- **WHEN** the owner enters pins per shelf as 4–6
- **THEN** the data sheet is refused naming pins per shelf as a count

#### Scenario: toom hinge data sheet
- **WHEN** the owner adds a data sheet for `hinge-concealed-110` with its cup values, citing its toom product page
- **THEN** the data sheet exists with its source, and `search_guidelines` can return it with that citation

#### Scenario: Item bought elsewhere
- **WHEN** the owner adds a `manual` data sheet for a shelf pin bought at another shop, citing the maker's leaflet and page
- **THEN** the data sheet exists with that citation, and pricing that pin needs a `manual` price-list entry under the same key

#### Scenario: Another item's data sheet
- **WHEN** the owner cites the toom data sheet of one maker's hinge for a hinge of another model
- **THEN** the data sheet is refused, naming the maker and model the source belongs to

#### Scenario: Page off toom
- **WHEN** a `toom` source names a page on another host
- **THEN** the data sheet is refused naming the host

### Requirement: Wall-shelf brackets are checked for count and spacing
The closed set of piece checks SHALL include a bracket-count check and a bracket-spacing check for every wall shelf in a custom build. Both SHALL be applied by the Designer's create and revise previews like any other piece rule, at the severity their rule states. The same two rules SHALL also give the bracket calculator its count and its end-distance range, which the rule SHALL hold as a range with its minimum, maximum, unit and source.

**Count check.** The count check SHALL read a table of rows, each giving a longest board length and a minimum number of brackets. A board SHALL be judged against the first row whose length is at least the board's length. A board longer than the last row SHALL use the last row. A breach SHALL be fewer brackets than that row's minimum.

**Spacing check.** The spacing check SHALL take:
- the shortest and longest distance from each end of the board to its outer bracket;
- a tolerance for even spacing.

A breach SHALL be either of these:
- an outer bracket closer to its end than the shortest distance, or further from it than the longest;
- with three or more brackets, a gap between neighbouring brackets that differs from the mean gap by more than the tolerance.

A shelf with a single bracket SHALL be judged on its end distances only.

**Reporting.** Each breach SHALL name the rule, the shelf, the measured value, the limit and the source, as for any other rule. Calculated brackets SHALL be judged by the count check. The spacing check SHALL judge the owner's positions only, since calculated positions are the cited range itself.

The shipped rules SHALL hold both checks at severity `warn`, citing the guideline source `topnotch-shelf-brackets`, with every limit quoted from it:
- the count table: up to 600 mm, 2; up to 1200 mm, 2; up to 1800 mm, 3; up to 2000 mm, 4;
- outer brackets 100 to 200 mm from each end;
- inner brackets "at equal distances between the two outer brackets".

#### Scenario: Too few brackets for a long shelf
- **WHEN** a 1500 mm wall shelf's owner positions hold two brackets
- **THEN** the preview shows a warning naming the count rule, the shelf, "2 brackets", "at least 3" and the source

#### Scenario: Length between two rows uses the next row
- **WHEN** a 650 mm wall shelf's owner positions hold two brackets
- **THEN** no count warning is shown, since the 1200 mm row asks for at least 2

#### Scenario: Longer than the table
- **WHEN** a 2400 mm wall shelf's owner positions hold three brackets
- **THEN** the preview warns that the last row asks for at least 4

#### Scenario: Outer bracket too close to the end
- **WHEN** a 1200 mm wall shelf's owner positions are 50, 600 and 1150 mm
- **THEN** the preview warns, for each end, that the outer bracket is 50 mm from it, against a limit of 100 to 200 mm

#### Scenario: Uneven inner spacing
- **WHEN** an 1800 mm wall shelf's owner positions are 150, 500 and 1650 mm
- **THEN** the preview warns that the gaps are not evenly spaced, naming the largest difference from the mean gap and the tolerance

#### Scenario: A warning does not block
- **WHEN** a create preview carries only bracket warnings
- **THEN** the owner can still confirm, and the piece is created with the warnings shown in its summary

#### Scenario: Calculated brackets pass
- **WHEN** a 1500 mm wall shelf has no owner positions
- **THEN** the calculator lists 3 brackets, the outer two at the cited 100–200 mm from each end, and the preview shows no bracket warning

### Requirement: The shelf span is measured per bay
When a module has dividers, the shelf-span rule SHALL measure the widest shelf board across every shelf level and bay, instead of the module's inner width. A level that no divider crosses is one board as wide as its cut. The measurement SHALL name the module, and the bay when that board's level is split. Without dividers, the rule SHALL measure the widest inner width of the module's shelves: the unbent inner width when there is no side fold, and the largest shelf cut width when a fold is `towards` the outside. An inside fold SHALL keep the unbent inner width as the span, because that is the widest shelf.

#### Scenario: Dividers bring the span within the limit
- **WHEN** a module with 18 mm boards and 1164 mm inner width breaches the shelf-span limit, and 2 full-height dividers are added
- **THEN** the span is measured on the widest bay, and the rule is not breached when that bay is within the limit

#### Scenario: Unequal bays
- **WHEN** a module has one full-height divider making bays of 400 and 546 mm
- **THEN** the shelf-span measurement gives 546 mm and names bay 2

#### Scenario: Partial divider leaves a whole shelf
- **WHEN** a module with 964 mm inner width has a divider from the bottom panel to its second fixed shelf, and a third fixed shelf above
- **THEN** the shelf-span measurement gives 964 mm, because the second and third shelves are whole boards

#### Scenario: Outside fold widens the span
- **WHEN** a module with 18 mm boards has a left outside height fold that makes the highest fixed shelf 1200 mm wide, wider than the unbent inner width
- **THEN** the shelf-span measurement gives 1200 mm

### Requirement: Guideline PDFs can be uploaded from the developer panel
The developer SHALL be able to upload a guideline PDF with a title, jurisdiction, publication date and licence note. The upload SHALL be refused, naming the problem, when the file is not a PDF (by its content, not its name), is larger than the upload cap, cannot be read as text, or has the same content as a source already listed. An accepted file SHALL be stored under the gitignored guidelines PDF folder with a generated file name, recorded with its metadata, and ingested into the corpus at once under the category `guideline`, with no network request. The developer SHALL be able to list every guideline source (checked-in and uploaded) with its ingestion state, re-ingest one, and delete an uploaded one, which removes its file and its passages. Checked-in sources SHALL NOT be deletable from the panel. Ingestion from the command line SHALL include uploaded sources. Uploaded passages SHALL carry the same prompt-injection delimiters as every other retrieved chunk. The routes SHALL sit behind the developer gate.

#### Scenario: PDF uploaded and searchable
- **WHEN** the developer uploads a readable PDF titled "ASR A1.2" with its date and licence note
- **THEN** it is listed as ingested, and `search_guidelines` can return its passages with that title and date

#### Scenario: Not a PDF
- **WHEN** the uploaded file is a renamed image
- **THEN** it is refused as not a PDF and nothing is stored

#### Scenario: Same file twice
- **WHEN** the developer uploads a file whose content matches an uploaded source
- **THEN** it is refused naming the existing source

#### Scenario: Upload deleted
- **WHEN** the developer deletes an uploaded source
- **THEN** its file and its passages are gone, and `search_guidelines` no longer returns them

#### Scenario: Checked-in source protected
- **WHEN** the developer tries to delete a source from the checked-in list
- **THEN** it is refused, and the source stays

#### Scenario: Panel disabled
- **WHEN** the panel is disabled and an upload route is called with a valid session
- **THEN** the response is 404

### Requirement: Design rules are edited from the developer panel
The developer SHALL be able to list every design rule with its id, check, parameters, severity, quoted source and origin (the checked-in table or the panel), and to add a rule or edit one. A rule SHALL name a check from the closed set and SHALL cite a source: a listed publication or an existing owner note. A saved rule SHALL be validated exactly as the checked-in table is at startup; a rule that fails SHALL be refused naming the rule and the field, and the rules in force SHALL stay unchanged. A saved rule SHALL apply from the next check, without a restart. Edits SHALL be stored apart from the checked-in table, which SHALL NOT be rewritten. Resetting an edited rule SHALL restore the checked-in version; a rule added on the panel SHALL be deletable. A stored edit that no longer validates at startup SHALL be skipped and shown as invalid, naming the rule, and SHALL NOT stop the service. The routes SHALL sit behind the developer gate.

#### Scenario: Rule added from the panel
- **WHEN** the developer adds a `shelf_span_mm_for_thickness` rule of 800 mm for 18 mm boards citing an owner note
- **THEN** the next piece check measures shelf spans against 800 mm, without a restart, and the rule is listed with origin "panel"

#### Scenario: Rule without a source refused
- **WHEN** the developer saves a rule with no source
- **THEN** it is refused naming the rule and `source`, and the rules in force are unchanged

#### Scenario: Rule reset to the file
- **WHEN** the developer edited `shelf-bracket-count` and then resets it
- **THEN** the checked-in version is in force again

#### Scenario: Invalid override does not stop startup
- **WHEN** a stored rule cites an owner note that was deleted, and the service starts
- **THEN** the service starts, the rule is not applied, and the panel shows it as invalid, naming the missing note

#### Scenario: Checked-in table untouched
- **WHEN** the developer edits any rule
- **THEN** `config/design_rules.yaml` is unchanged

### Requirement: Legacy guidance does not establish verified engineering evidence
Existing guideline publications, owner notes, drilling sheets and geometric rules SHALL retain their ordinary preliminary-guidance role outside the separate quarantine experiment. They SHALL NOT establish verified resistance, allowable span or anchorage solely by citation, thickness or bracket count. During an engineering turn, guideline search SHALL use engineering rights/applicability eligibility; an unreviewed legacy source SHALL yield metadata/no eligible evidence rather than its text. Foundation rollout SHALL NOT delete/rewrite legacy files, chunks or saved hardware inputs.

#### Scenario: Retailer bracket table cited
- **WHEN** a legacy bracket rule gives a count for a shelf
- **THEN** its layout guidance is not presented as verified shelf or wall-fixing capacity, including beyond its published table

#### Scenario: Guideline tool used for engineering
- **WHEN** an engineering turn calls guideline search for an unreviewed local PDF
- **THEN** no text from that source is returned to the model and the missing review is stated

#### Scenario: Ordinary guidance preserved
- **WHEN** a non-engineering turn uses an existing owner guideline note after foundation rollout
- **THEN** the ordinary guideline behaviour remains available and the foundation has not quarantined its stored content globally
