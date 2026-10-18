## ADDED Requirements

### Requirement: An answered engineering question does not make later turns engineering turns
When a turn is routed to the engineering path, the owner's message of that turn SHALL belong to the engineering exchange together with its replies and tool results. Later routing and agent calls SHALL leave out the whole exchange, the question as well as the answer, as they already leave out its replies. A later message SHALL be an engineering turn only when its own text names an engineering term, or when the routing model flags that message itself. In conversations stored before this change, an owner message followed in its turn by an engineering reply SHALL count as part of that exchange, without changing stored data. The owner's chat view SHALL still show every message.

#### Scenario: The reported loop
- **WHEN** the owner asks "Will the bridge be structurally stable if the dividers are removed?", gets the engineering status reply, then writes "Keep and shorten the dividers."
- **THEN** the second message is not routed as an engineering turn by the earlier question, the Designer's reply reaches the owner, and the earlier question and its status reply are not in the second turn's requests

#### Scenario: A new engineering question still is one
- **WHEN** after an answered engineering question the owner asks "Can the shelf carry 30 kg?"
- **THEN** that turn is an engineering turn

#### Scenario: An existing looping conversation recovers
- **WHEN** a conversation stored before this change holds an unmarked owner question followed by an engineering status reply, and the owner sends a design request
- **THEN** the routing call does not contain that question, and the stored messages are unchanged
