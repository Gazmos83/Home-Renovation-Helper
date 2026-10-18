## ADDED Requirements

### Requirement: The inspector has a Reading tab
The inspector, both its page and the conversation's split view, SHALL have a Reading tab beside its Model, Cut list and Renders tabs.

For an approved version the tab SHALL show the reading list grouped by wall-hung item, with the fixed notice above it and any gap lines. Each entry SHALL show its citation fields and open its link in a new tab. An entry whose source can be read locally SHALL offer "Read here", which shows that source's blocks with their page references, paged. One whose source cannot be read SHALL show the reason instead.

For a version that is not approved, the tab SHALL say "Approve this version to see recommended reading" and show no list.

Below the list, the tab SHALL show the version's stored engineering reports, newest first. Each report SHALL show its overall outcome, "Conformity not established", whether it is stale with its reasons, and its evidence passages when available. A report whose evidence is unavailable SHALL show that limitation. A version with no stored reports SHALL say so in plain words.

Text SHALL be loaded only when the tab is shown. The open tab SHALL be part of the page's address. The tab SHALL NOT show a model name, prompt, token count or cost. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Reading after approval
- **WHEN** the owner approves `hall-shelf` v3 and opens the Reading tab
- **THEN** the wall shelf's sources are listed under the notice, and "Read here" on a local-use source shows its blocks

#### Scenario: Unapproved version
- **WHEN** the owner switches the inspector to v4, which is not approved
- **THEN** the Reading tab shows "Approve this version to see recommended reading" and no list

#### Scenario: Stale report
- **WHEN** v3 has a stored report and v4 is a newer geometry version
- **THEN** v3's report is shown as stale with "a newer geometry version exists"
