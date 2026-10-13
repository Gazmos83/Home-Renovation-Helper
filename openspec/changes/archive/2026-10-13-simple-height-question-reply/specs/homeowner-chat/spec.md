## ADDED Requirements

### Requirement: A plain question about the expected height gets a short reply
When the owner's message only asks what the expected, maximum or highest height is, the Foreman SHALL answer, by an application rule before any specialist or model call, with exactly: "The height is not verified. What should the height be?" That answer SHALL carry no engineering status text, source, missing-input list or legal note. A message that names strength, load, deflection, anchorage, safety or another engineering term, names a kitchen part, or asks about any other dimension SHALL be routed as before. The rule SHALL change no stored data.

#### Scenario: The short question
- **WHEN** the owner asks "What's expected height"
- **THEN** the reply is "The height is not verified. What should the height be?" and nothing else

#### Scenario: A longer or different question is routed as before
- **WHEN** the owner asks "What's the maximum height this cabinet can safely carry?"
- **THEN** the message is routed to the engineering path and not answered by this rule

#### Scenario: Another dimension
- **WHEN** the owner asks "What's the expected depth"
- **THEN** the rule does not apply

#### Scenario: Nothing is stored
- **WHEN** the rule answers
- **THEN** the brief, the note and the house file are unchanged
