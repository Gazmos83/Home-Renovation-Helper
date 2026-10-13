## ADDED Requirements

### Requirement: The engineering status is one short sentence
An engineering reply SHALL show its verification status as exactly one fixed, code-rendered sentence of at most 20 words: "Not verified: no engineering check is available, so load capacity, fixings and safety are unconfirmed." The reply SHALL NOT show the not-implemented sentence, the preliminary-advice line, the lookup-off line, a missing-inputs list, the legal note or a rejection notice. Evidence citations, property values, code-detected conflicts, code-generated reports and metadata links selected in the turn SHALL still follow the sentence. A rejected or invalid engineering answer SHALL show only the sentence.

#### Scenario: A load question with no evidence
- **WHEN** the owner asks "Can this shelf hold 30 kg?" and no evidence is selected
- **THEN** the reply is exactly the fixed sentence

#### Scenario: A rejected answer
- **WHEN** the specialist's engineering answer fails validation
- **THEN** the reply is exactly the fixed sentence and does not repeat the rejected claim

#### Scenario: Selected evidence is still shown
- **WHEN** the specialist selects an eligible evidence packet and property
- **THEN** the reply starts with the fixed sentence and then shows the citation and the property value

### Requirement: A placement request is not an engineering turn by the model flag alone
When the owner's message asks to put, place, move or position a piece relative to a wall, door, window or corner, or at a stated distance, and the application's engineering matcher finds no engineering term, the Foreman SHALL NOT route the turn to the engineering path, whatever the routing model flagged. A placement message that names an engineering term SHALL be routed as before.

#### Scenario: The reported placement
- **WHEN** the owner writes "Can you please put v18 to the right of the door of wall 1, 30 cm away from wall 2?" and the routing model flags an engineering question
- **THEN** the turn is not an engineering turn and no engineering status is shown

#### Scenario: Placement with a safety term
- **WHEN** the owner writes "Put the wall cabinet on wall 2, is it safe?"
- **THEN** the turn is routed to the engineering path
