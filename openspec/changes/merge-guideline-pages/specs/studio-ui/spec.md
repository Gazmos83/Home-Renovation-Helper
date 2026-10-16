## MODIFIED Requirements

### Requirement: Snapshots, remnants and guideline notes have pages
The Studio SHALL let the owner record a snapshot (optionally prefilling an entry), list and delete snapshots on the Snapshots tab of the Pricing Overview page; list, add and remove remnants on its Remnants tab; and list, add, edit and delete guideline notes with their citation on the Guidelines view of the Design Studio's Design Knowledge tab. Every form SHALL show the API's refusal reason next to the field it names.

#### Scenario: Future-dated snapshot
- **WHEN** the owner records a snapshot dated tomorrow
- **THEN** the form shows the refusal next to the date

#### Scenario: Prefilled entry reaches the Prices tab
- **WHEN** the owner records a snapshot that prefills an entry and then chooses the Prices tab
- **THEN** the new entry is listed there without a reload

#### Scenario: Note refused on the Guidelines view
- **WHEN** the developer adds a guideline note without a source citation on the Guidelines view
- **THEN** the note form shows the refusal next to the citation field

### Requirement: Hardware data sheets are managed on the guidelines page
The Guidelines view of the Design Studio's Design Knowledge tab SHALL have a Hardware data section. In it the owner can list, add, edit and delete data sheets, with each sheet's key, kind, maker, model, values and source. A value left empty SHALL be shown as missing, never as zero. Each measured value SHALL be entered as one number or as a minimum and maximum, and a range SHALL be shown as a range. Every form SHALL show the API's refusal reason next to the field it names. The section SHALL pass a recorded browser check before it counts as done.

#### Scenario: Data sheet added
- **WHEN** the owner adds a hinge data sheet with a toom page and two of its values
- **THEN** the list shows the sheet with its source, the two values, and the other values as missing

#### Scenario: Refused source
- **WHEN** the owner gives a `toom` source on another host
- **THEN** the form shows the refusal next to the page URL
