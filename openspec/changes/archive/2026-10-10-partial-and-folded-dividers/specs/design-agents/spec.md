## MODIFIED Requirements

### Requirement: The Designer may put fronts on a folded carcass
The Designer's instructions SHALL say that a module with `side_folds` may carry overlay fronts, adjustable shelves and dividers, that those fronts follow the folded opening (an n-gon when the outline is not a rectangle), and that dividers on a fold without positions split the narrowest opening along their span into equal bays. Bevels SHALL stay unexpressible.

#### Scenario: Instructions allow fronts on a fold
- **WHEN** the Designer's instructions are loaded
- **THEN** they name `side_folds` together with fronts, adjustable shelves and dividers, and they no longer say dividers on a fold are not expressible

#### Scenario: A panel bend is side_folds
- **WHEN** the Designer's instructions are loaded
- **THEN** they say a bend in a carcass side is the field `side_folds`, that the Designer must never tell the owner there is no field for a bend angle, and that the field applies to the module the owner named (its id from the piece summary)

## ADDED Requirements

### Requirement: The Designer can express a partial-height divider
The Designer's instructions SHALL say that a divider that does not run the full height is expressed with `divider_spans`, one entry per divider, left to right, each with `from_board` (`"bottom"` or a shelf number counting every shelf from the lowest) and `to_board` (`"top"` or a shelf number), and that only fixed shelves can anchor a divider. They SHALL give "a vertical wall from the top shelf to the top of the cabinet" on a module with 4 fixed shelves as `"dividers": 1, "divider_spans": [{"from_board": 4, "to_board": "top"}]`. The Designer SHALL restate the span in the change list and wait until the owner says the list is complete. The Designer SHALL never tell the owner that a partial-height divider cannot be made.

The piece summary SHALL name each divider's span when spans are set, e.g. "1 divider (equal bays) from shelf 4 to the top", and each shelf's kind when `shelf_kinds` is set, e.g. "shelf kinds (lowest first): adjustable, adjustable, adjustable, fixed".

#### Scenario: Instructions name divider spans
- **WHEN** the Designer's instructions are loaded
- **THEN** they name `divider_spans`, `from_board` and `to_board`, and give the top-shelf-to-top example

#### Scenario: Span visible in the summary
- **WHEN** module `cabinet` has 1 divider with `divider_spans` [{`from_board`: 4, `to_board`: "top"}]
- **THEN** the Designer's context gives "1 divider (equal bays) from shelf 4 to the top" for `cabinet`

#### Scenario: Full-height summary unchanged
- **WHEN** a module has 2 dividers without spans
- **THEN** the Designer's context gives "2 dividers (equal bays)" as before

#### Scenario: Shelf kinds visible in the summary
- **WHEN** module `cabinet` has `shelf_kinds` ["adjustable", "adjustable", "adjustable", "fixed"]
- **THEN** the Designer's context gives "shelf kinds (lowest first): adjustable, adjustable, adjustable, fixed" for `cabinet`

### Requirement: The Designer asks where a new divider goes
When `create_piece` or `revise_package` is called with a new divider (the count rises, or a span is added) and the revised module has no `divider_positions_mm`, the tool SHALL NOT propose the version. It SHALL instead return, computed by code:
- the centred position for each divider (equal compartments; on a folded module, of the narrowest opening along its span), in millimetres from the left side's inner face;
- the compartment widths at each shelf the divider splits, or across its span when it splits none;
- for each compartment, the configured shelf-span limit for the board's thickness with its cited source and whether the compartment is within it; or the statement that no shelf-span limit is configured.

The Designer SHALL relay this to the owner (through the Foreman) as a question: the recommended position, the compartment widths, the limit or its absence, and any guideline passages `search_guidelines` returns on shelf spans or dividers, each cited. The Designer SHALL then write the position the owner accepts or gives as `divider_positions_mm`. A design imported from a file SHALL NOT be refused for missing positions.

#### Scenario: Position asked with no limit configured
- **WHEN** the owner asks for "a vertical wall from the top shelf to the top of the cabinet" on the 800 mm `cabinet` with 4 fixed shelves and no position, and no shelf-span rule is configured
- **THEN** no version is proposed, and the owner is asked to confirm a divider 373 mm from the left side's inner face, giving two 373 mm compartments, with the statement that no shelf-span limit is configured yet

#### Scenario: Position asked with a limit configured
- **WHEN** a shelf-span rule gives 800 mm for 18 mm boards with its cited source, and the owner asks for one divider without a position across shelves 1164 mm wide
- **THEN** the recommendation gives two 573 mm compartments, says both are within 800 mm, and cites the rule's source

#### Scenario: Owner gives the position
- **WHEN** the owner answers "200 mm from the left"
- **THEN** the revision carries `divider_positions_mm` [200], and the measurement check holds it against the owner's words

#### Scenario: Import not asked
- **WHEN** an imported design has dividers without positions
- **THEN** it is accepted with equal bays, as before

### Requirement: The Designer asks before fixing a shelf
When the owner asks for a divider that would stand on or reach an adjustable shelf, the Designer SHALL tell the owner (through the Foreman) that only a fixed shelf can hold a divider, name the shelf, and ask whether to fix it. The question SHALL state what changes: that shelf becomes a fixed board screwed with 4 confirmat screws, and the module needs that shelf's pins fewer. When the owner agrees, the Designer SHALL revise `shelves`, `adjustable_shelves` and `shelf_kinds` together with the divider in one revision, whose preview lists the hardware and cut-list changes. When the owner declines, the Designer SHALL not add the divider and SHALL say so. The Designer SHALL never change a shelf's kind without the owner's yes.

#### Scenario: Owner agrees to fix the top shelf
- **WHEN** `cabinet` has 4 adjustable shelves and the owner asks for a divider from the top shelf to the top, then answers yes to fixing shelf 4
- **THEN** the proposed revision sets `shelves` 1, `adjustable_shelves` 3, `shelf_kinds` ["adjustable", "adjustable", "adjustable", "fixed"] and the divider, and its preview lists the confirmat line rising by 4 and the shelf pins falling by one shelf's pins

#### Scenario: Owner declines
- **WHEN** the owner answers no to fixing the shelf
- **THEN** no revision is proposed and the reply says the divider was not added because its shelf stays adjustable

#### Scenario: Instructions name the rule
- **WHEN** the Designer's instructions are loaded
- **THEN** they say only fixed shelves can hold a divider, that the owner is asked before a shelf is fixed, and that a new divider's position is asked with the tool's recommendation
