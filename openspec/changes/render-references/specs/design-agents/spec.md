## ADDED Requirements

### Requirement: Questions about what the owner sees go to the Reviewer
A message asking whether something the owner sees in the Piece Inspector (a view such as front or exploded, a module or a part) is right, or asking for the piece to be checked against the brief, SHALL be handled by the Reviewer, within the existing rule that the Reviewer needs a screenshot or a render on the bound piece's latest version. A message asking to change what the owner sees SHALL stay with the Designer. The Foreman's instruction SHALL state this in one short line for the Reviewer and one rule, with no code-like detail.

#### Scenario: Question about a view
- **WHEN** the bound piece's latest version has a draft turntable and the owner writes "is the top shelf in the side view right?"
- **THEN** the Reviewer answers

#### Scenario: Question about the exploded view
- **WHEN** the bound piece's latest version has a draft turntable and the owner writes "is the shelf right in the exploded view?"
- **THEN** the Reviewer answers

#### Scenario: Change to what the owner sees
- **WHEN** the bound piece's latest version has a draft turntable and the owner writes "lower the top shelf in the side view"
- **THEN** the Designer answers

#### Scenario: Question with nothing rendered
- **WHEN** the bound piece's latest version has no screenshot or render and the owner asks whether the front view is right
- **THEN** the Reviewer is not chosen and the reply says what must exist first
