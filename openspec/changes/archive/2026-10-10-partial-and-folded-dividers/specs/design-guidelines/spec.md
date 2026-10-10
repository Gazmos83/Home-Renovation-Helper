## MODIFIED Requirements

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
