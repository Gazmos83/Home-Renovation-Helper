## MODIFIED Requirements

### Requirement: No specialist promises to report back after the turn
A turn SHALL end with its reply, and no specialist SHALL message the owner afterwards. No specialist's instructions SHALL let it promise to tell the owner later when a build, a render or a review finishes. The only message after a turn SHALL be the render notice that code posts when a render started in the conversation finishes or fails; it is never written by a model. The Builder and the Designer SHALL say that a started build's status shows in the conversation's Piece panel and can be asked for in a later message.

#### Scenario: Owner asks to be told when the build is done
- **WHEN** a build has started and the owner asks "Will you tell me when the build is complete?"
- **THEN** the reply says the Piece panel shows the build's status and that the owner can ask again, and it does not promise a later message

#### Scenario: Render notice is posted by code
- **WHEN** a draft turntable started in the conversation finishes after the turn has ended
- **THEN** a render notice appears in the conversation, posted by code, and no specialist runs or writes a message

### Requirement: A revision past the version limit is refused by code
When a piece already holds 15 versions, `revise_package`, and the rebuild of an unchanged piece, SHALL refuse before asking for confirmation. The refusal SHALL be written by code and SHALL say that the piece has 15 versions and that the owner can delete one on the Pieces page or in the Piece panel and then ask again. The Designer SHALL relay that refusal and SHALL NOT propose deleting a version itself. When the new version would be the 13th, 14th or 15th the piece holds, the confirmation summary SHALL add a line written by code: "This will be version <n> of 15 the piece can hold."

#### Scenario: Revision refused at the limit
- **WHEN** `listening-wall` holds 15 versions and the owner asks "make the shelves 20 mm thicker"
- **THEN** no confirmation is shown, no version is made, and the reply says the piece has 15 versions and one can be deleted on the Pieces page or in the Piece panel

#### Scenario: Heads-up near the limit
- **WHEN** `listening-wall` holds 12 versions and the Designer proposes a revision
- **THEN** the confirmation summary includes "This will be version 13 of 15 the piece can hold."

#### Scenario: No heads-up early
- **WHEN** `listening-wall` holds 4 versions and the Designer proposes a revision
- **THEN** the confirmation summary has no version-limit line
