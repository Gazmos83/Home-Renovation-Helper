## ADDED Requirements

### Requirement: The Designer duplicates a piece on request
The Designer SHALL have a `duplicate_piece` tool. It takes:
- the source piece's id;
- optionally a version, the latest by default;
- the copy's name;
- optionally an id, derived from the name when omitted.

It is checked exactly as a duplicate from the Pieces page. A refusal is returned to the Designer with its reason, and nothing is created. A valid call SHALL wait for the owner's yes, with a preview naming:
- the source piece and version;
- the copy's name and id;
- the overall size.

On yes, the copy is made as the Pieces page makes it. The reply names the copy and links its new conversation. The conversation the tool ran in SHALL keep its own binding, or lack of one. On no, nothing is created.

The tool works in any conversation, including one bound to another piece. The source piece SHALL be one of the house file's pieces.

#### Scenario: Duplicate in the piece's own conversation
- **WHEN** the owner asks "duplicate this as Sideboard Hall" in `sideboard-1200`'s conversation and answers yes to the preview
- **THEN** `sideboard-hall` is created from `sideboard-1200`'s latest version, the reply links its new conversation, and this conversation stays bound to `sideboard-1200`

#### Scenario: Owner says no
- **WHEN** the owner answers no to the duplicate preview
- **THEN** nothing is created and the reply says the piece was not duplicated

#### Scenario: Unknown source
- **WHEN** the Designer names a source piece that does not exist
- **THEN** the tool refuses naming the id, and no preview is shown
