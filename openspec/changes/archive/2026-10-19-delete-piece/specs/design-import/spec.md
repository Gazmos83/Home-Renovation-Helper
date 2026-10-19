## ADDED Requirements

### Requirement: A design file that matches an existing piece is named when it is attached
When the owner's message carries a design file and the conversation has no piece, the application SHALL check the file against the house file's pieces before any specialist runs. The file matches a piece when any of these holds:
- its file name, without `.json`, is the piece's id;
- the name inside the design, made into an id the way an apartment name is, is the piece's id;
- the name inside the design equals the piece's name, ignoring case.

On a match the application SHALL answer that turn itself, with no specialist and no room question. The answer names the file and the piece (name and id) and gives three ways on:
- to update the piece, attach the file in that piece's conversation, which imports it as the next version; when the piece has no conversation, name the piece in this conversation and attach the file again;
- to start over, delete the piece on the Pieces page and attach the file again;
- to keep both, change the design's name and attach it again.

The answer SHALL be decided and written by the application, not by a model. A conversation already bound to the matching piece SHALL import the file as before. A file that matches no piece SHALL be handled as before.

#### Scenario: File named like an existing piece
- **WHEN** the owner attaches `kommode-harmony.json` in a new conversation and piece `kommode-harmony` exists
- **THEN** the reply names `kommode-harmony.json` and "Kommode Harmony (Höffner 13207807)" (`kommode-harmony`) with the three ways on, no specialist runs, the room question is not asked, and nothing is imported

#### Scenario: Name inside the design matches
- **WHEN** the owner attaches `export.json` whose design is named "Sideboard" and piece `sideboard-1200` is named "Sideboard"
- **THEN** the reply names `sideboard-1200` with the three ways on

#### Scenario: No match
- **WHEN** the owner attaches `lamellen-kommode.json` named "Lamellen-Kommode" and no piece has that id or name
- **THEN** the turn is handled as before

#### Scenario: Bound to the matching piece
- **WHEN** the owner attaches `kommode-harmony.json` in `kommode-harmony`'s own conversation
- **THEN** no conflict reply is given, and the file can be imported as `kommode-harmony`'s next version as before
