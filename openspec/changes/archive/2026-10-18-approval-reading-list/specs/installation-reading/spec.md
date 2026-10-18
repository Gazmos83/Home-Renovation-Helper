## Purpose

Gives the owner a lawful, model-free path to the engineering sources relevant to hanging an approved piece on a wall. Recommended reading is chosen from catalogue metadata by fixed rules, and rights-eligible source text is read on the owner's own machine.

## ADDED Requirements

### Requirement: An approved version lists recommended reading for its wall-hung items
For an approved version, the service SHALL list recommended reading for each wall-hung item in the version's spec. A wall-hung item is every wall shelf, and every module whose `mounting` is `wall`. A module without `mounting: wall` SHALL NOT be treated as wall-hung, whatever its height or position.

Sources SHALL be chosen by a checked-in rule table that maps each item kind (`wall_shelf`, `wall_module`) to source `applicable_furniture` values and `collections`. A source version matches an item kind when it carries at least one of the kind's furniture values or collections. Only the current, non-superseded version of each registered source SHALL be considered. A source matching several items SHALL be listed once, naming every item it is for.

Each entry SHALL give the source's title, publisher, edition, standard or model, page or section, jurisdiction and verification status, each shown as "not recorded" when null, together with the rule that matched it and the catalogue's `source_url`. A local file path SHALL NOT be shown or linked. Entries SHALL be ordered with verified sources first, then by title.

A version that is not approved SHALL NOT be given a list; the service SHALL say that the version must be approved first. An approved version with no wall-hung items SHALL say that it has none, with an empty list.

#### Scenario: Wall shelf on an approved version
- **WHEN** `hall-shelf` v3 is approved and carries a 1200 mm wall shelf, and the catalogue holds DIN EN 14749 tagged `shelf` and the Bauordnung Berlin link tagged `kitchen_wall_anchoring`
- **THEN** the list holds both sources for the wall shelf, each with its edition, link and matched rule, and the verified one first

#### Scenario: Raised module without a mounting
- **WHEN** an approved version has a module at z = 1400 mm with no `mounting`
- **THEN** that module gets no reading entries and is not named as wall-hung

#### Scenario: Not approved
- **WHEN** the owner asks for the reading list of v4, which is built but not approved
- **THEN** no list is returned and the reply says v4 must be approved first

#### Scenario: Superseded edition
- **WHEN** a source has a superseded 2019 edition and a current 2022 edition, both tagged `wall_cabinet`
- **THEN** only the 2022 edition is listed for a wall-mounted module

### Requirement: Gaps and limits are stated on every reading list
Every reading list SHALL carry a fixed notice: it is recommended reading and not a safety approval, wall fixing depends on the wall substrate, the anchor and the load, and the list is NOT VERIFIED. When an item kind matches no source, the list SHALL name the item and say no recorded source covers it. The service SHALL NOT fill a gap with a guessed source, a web lookup or generated text.

#### Scenario: No source for wall-mounted modules
- **WHEN** an approved version holds a wall-mounted module and no current source matches `wall_module`
- **THEN** the list names that module with "No recorded source covers this item", and the notice is shown

### Requirement: Source text is read locally only while rights allow it
The owner SHALL be able to open a listed source's published blocks, paged in reading order, with each block's page or section reference. The service SHALL return block text only when the source version's current rights permit both local retrieval and retention, rechecked on every request. Otherwise it SHALL return no text, only the link and the reason, for example rights pending, revoked or expired. A source version with no published blocks SHALL say so. Only sources on the version's reading list, or cited by the version's stored engineering reports, SHALL be readable this way.

#### Scenario: Local use approved
- **WHEN** the owner opens DIN EN 14749 from the list and its current decision grants local retrieval and retention
- **THEN** its published blocks are shown with their page references

#### Scenario: Rights revoked between list and read
- **WHEN** the owner opens a source whose rights were revoked after the list was shown
- **THEN** no text is returned and the reply gives the link and "rights revoked"

#### Scenario: Source not on the list
- **WHEN** the owner requests the blocks of a source that is neither on the version's reading list nor cited by its reports
- **THEN** the request is refused and no text is returned

### Requirement: Reading never reaches a model or external tracing
Reading lists, block text and report views SHALL be computed by the service without any model call. They SHALL NOT be added to graph state, conversation history, a prompt, a tool result or a Langfuse export. They SHALL be served only to the authenticated owner, and the homeowner view SHALL show no model name, prompt, token count or cost.

#### Scenario: Reading leaves no model trace
- **WHEN** the owner opens a reading list and reads three blocks of a local-only source
- **THEN** no OpenRouter request is made, nothing is exported to Langfuse, and the conversation history is unchanged
