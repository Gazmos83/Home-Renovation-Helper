## MODIFIED Requirements

### Requirement: Replies follow the formatting rules
Every specialist's instructions SHALL include, composed by code after its editable text and before the untrusted-content guard, the rules that its questions to the owner are a bullet list (one question per bullet), any list of items with sizes or quantities (a cut list, parts, hardware, prices) is a table, decisions taken in the conversation are listed as a table when summarised, arithmetic the owner should check is written in a fenced block marked `calc`, a question that asks for one figure (a distance, gap, size, height, count or price) is answered in one sentence that gives the figure with its unit, and how that figure was found (positions, lengths, the steps) is written only in the `calc` block, not in the reply's text. The rules SHALL not apply to `ask_owner` questions, which are structured.

#### Scenario: Rules composed
- **WHEN** the Designer's prompt is assembled
- **THEN** it contains the formatting rules once, after the instruction text and before the guard

#### Scenario: Not editable
- **WHEN** the developer edits the Designer's instruction text
- **THEN** the formatting rules are still composed after it unchanged

#### Scenario: One figure asked
- **WHEN** the owner asks "How much space is between the murphy bed and wall 3?" and the Designer works it out from the composition's placement
- **THEN** the reply's text is the one sentence "The gap between the murphy bed and wall 3 is 1350 mm.", and the wall, offset and lengths used appear only in a `calc` block
