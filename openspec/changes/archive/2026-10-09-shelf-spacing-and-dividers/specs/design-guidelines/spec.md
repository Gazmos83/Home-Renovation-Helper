## ADDED Requirements

### Requirement: The shelf span is measured per bay
When a module has dividers, the shelf-span rule SHALL measure each bay's width instead of the module's inner width, and report the widest bay. The measurement SHALL name the module and the bay. Without dividers, the rule SHALL measure the inner width as before.

#### Scenario: Dividers bring the span within the limit
- **WHEN** a module with 18 mm boards and 1164 mm inner width breaches the shelf-span limit, and 2 dividers are added
- **THEN** the span is measured on the widest bay, and the rule is not breached when that bay is within the limit

#### Scenario: Unequal bays
- **WHEN** a module has one divider making bays of 400 and 546 mm
- **THEN** the shelf-span measurement gives 546 mm and names bay 2
