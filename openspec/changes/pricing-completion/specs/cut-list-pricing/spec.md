## ADDED Requirements

### Requirement: A price question in the conversation shows the priced cut list
When the owner asks in a conversation what a piece will cost, and the Researcher prices an approved version, the reply SHALL show the stored pricing line by line as one table, then the total. The table SHALL hold:
- each sheet material with its sheet count, use and cost;
- each hardware line with its item, quantity and cost;
- each edge-band line with its cost;
- the cut service;
- the delivery.

A line without a price SHALL appear as "unpriced" with its reason, and the reply SHALL say that the pricing is incomplete and that no price was guessed. Every amount in the reply SHALL come from that stored pricing. No amount SHALL be estimated, rounded differently or added from elsewhere. When the version is not approved, the reply SHALL say where the owner approves it, and no pricing SHALL be made.

#### Scenario: Complete pricing in the chat
- **WHEN** the bound piece's version 2 is approved, every line has a price-list entry, and the owner asks "what will this cost?"
- **THEN** the reply shows a table with each material, each hardware line, the edge band, the cut service and the delivery, each with its cost from the stored pricing, then the total, and says the pricing is complete

#### Scenario: Unpriced hardware line
- **WHEN** the approved version's cut list has a hinge with no price-list entry and the owner asks what it will cost
- **THEN** the hinge line shows "unpriced" with the reason "no price-list entry for this hardware item", and the reply says the pricing is incomplete and no price was guessed

#### Scenario: Version not approved
- **WHEN** the bound piece's latest version is built but not approved and the owner asks what it will cost
- **THEN** no pricing is made and the reply says where to approve the version and offers to price it then
