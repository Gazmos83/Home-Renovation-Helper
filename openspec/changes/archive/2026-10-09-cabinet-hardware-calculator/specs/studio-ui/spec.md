## ADDED Requirements

### Requirement: Hardware data sheets are managed on the guidelines page
The guidelines page SHALL have a Hardware data section. In it the owner can list, add, edit and delete data sheets, with each sheet's key, kind, maker, model, values and source. A value left empty SHALL be shown as missing, never as zero. Each measured value SHALL be entered as one number or as a minimum and maximum, and a range SHALL be shown as a range. Every form SHALL show the API's refusal reason next to the field it names. The section SHALL pass a recorded browser check before it counts as done.

#### Scenario: Data sheet added
- **WHEN** the owner adds a hinge data sheet with a toom page and two of its values
- **THEN** the list shows the sheet with its source, the two values, and the other values as missing

#### Scenario: Refused source
- **WHEN** the owner gives a `toom` source on another host
- **THEN** the form shows the refusal next to the page URL

### Requirement: The Cut list tab shows the drilling list
The inspector's Cut list tab SHALL show the version's drilling list from `spec.json` `drilling`:
- each part's positions, with the values and sources used; an exact position as its value, a ranged one as its range, and one given as a rule as its words;
- the drilling-work counts.

When the list is incomplete, the tab SHALL show a banner, above the tables, that names every missing value. A version with no `drilling` SHALL say that drilling was not calculated for it. The tab SHALL pass a recorded browser check before it counts as done.

#### Scenario: Drilling shown
- **WHEN** the owner opens the Cut list of a version with adjustable shelves and complete data
- **THEN** the drilling table lists the side rows' hole heights and setbacks with their sources, and no banner is shown

#### Scenario: Ranged bracket ends shown
- **WHEN** the owner opens the Cut list of a version with a 1500 mm wall shelf and calculated brackets
- **THEN** the drilling table shows the outer brackets as "100–200 mm from each end" and the middle one as "evenly spaced between them", and no banner is shown

#### Scenario: Incomplete banner
- **WHEN** the owner opens the Cut list of a version whose hinge data sheet lacks the cup edge distance
- **THEN** a banner says the drilling list is incomplete and names "cup edge distance"
