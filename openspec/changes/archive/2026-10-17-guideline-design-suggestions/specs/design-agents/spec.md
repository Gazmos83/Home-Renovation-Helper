## ADDED Requirements

### Requirement: The Designer offers cited guideline suggestions for a new piece
When the conversation has a confirmed brief and no active build, the Designer SHALL call `search_guidelines` for the brief's style, the piece and its room (when one is confirmed) before its first `create_piece` call, unless the owner has declined suggestions or asked to go straight to the draft. From the passages returned it SHALL offer at most three suggestions. Each SHALL name its publication or note and section, and SHALL say whether the piece's spec can hold it or it is advice only. Advice only means something the piece's document has no field for, such as a fabric, a wall colour or an accessory. Then the Designer SHALL ask the owner which suggestions to use, and SHALL NOT call `create_piece` in that reply.

Only suggestions the owner accepts SHALL go into the document, and only through fields the schema has. An advice-only suggestion SHALL NOT be written into the document and SHALL NOT be recorded as a generator-extension request. A number in a suggestion SHALL count as a confirmed size only once the owner accepts that suggestion. The document SHALL then go through the existing `create_piece` preview and `yes`.

When `search_guidelines` returns nothing, the Designer SHALL say it found no style guidance in the guidelines and SHALL NOT offer style advice from memory. Then it SHALL draft from the brief alone. Revisions, imports and rebuilds SHALL NOT trigger suggestions.

#### Scenario: Suggestions offered before the draft
- **WHEN** the brief for a hall bench in a transitional style is confirmed, the conversation has no active build, and the guidelines hold a style guide with a transitional section
- **THEN** the Designer calls `search_guidelines`, offers at most three suggestions that each cite the guide and its section and say whether the spec can hold them, asks which to use, and calls no `create_piece` in that reply

#### Scenario: Accepted suggestion drafted
- **WHEN** the owner accepts a suggestion for an oak carcass and rejects one for brass handles
- **THEN** the Designer's `create_piece` document uses oak for the carcass, carries no brass handle, and the owner is shown the usual preview and answers yes or no

#### Scenario: Advice-only suggestion accepted
- **WHEN** the owner accepts a suggestion for linen cushions on the bench
- **THEN** the document has no cushion entry and no generator-extension request is recorded

#### Scenario: Nothing matched
- **WHEN** `search_guidelines` returns no passage for the brief's style
- **THEN** the Designer says it found no style guidance in the guidelines, offers no style advice, and drafts from the brief

#### Scenario: Owner skips suggestions
- **WHEN** the owner says to go straight to the draft
- **THEN** the Designer offers no suggestions and calls `create_piece` with a document from the brief alone

#### Scenario: Revision offers nothing
- **WHEN** the conversation's active build is `hall-bench` v2 and the owner asks for a wider seat
- **THEN** the Designer follows the change-list confirmation and offers no style suggestions
