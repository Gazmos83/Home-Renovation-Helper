## MODIFIED Requirements

### Requirement: A design file that matches an existing piece is named when it is attached
When the owner's message carries a design file and the conversation has no piece, the application SHALL check the file against the house file's pieces before any specialist runs. The file matches a piece when any of these holds:
- its file name, without `.json`, is the piece's id;
- the name inside the design, made into an id the way an apartment name is, is the piece's id;
- the name inside the design equals the piece's name, ignoring case.

On a match the application SHALL answer that turn itself, with no specialist and no room question. The answer names the file and the piece (name and id) and gives three ways on:
- to update the piece, attach the file in that piece's conversation, which imports it as the next version; when the piece has no conversation, name the piece in this conversation and attach the file again;
- to start over, delete the piece on the Pieces page and attach the file again;
- to keep both, reply "keep both" with a new name for the design, and the file is imported as a new piece under that name.

The answer SHALL be decided and written by the application, not by a model. A conversation already bound to the matching piece SHALL import the file as before. A file that matches no piece SHALL be handled as before.

When the owner's next message after that answer asks to keep both, the application SHALL hand the earlier design file to the Designer, together with the name the owner gave if any. The application decides this, not a model. The Designer imports the file as a new piece with `import_design`, under the new name. `import_design` SHALL take an optional name, which replaces the name inside the design before it is checked. The new name SHALL NOT equal any existing piece's name, ignoring case. When the owner gave no name, the Designer asks for one before calling the tool. The import is previewed and confirmed as any import.

#### Scenario: File named like an existing piece
- **WHEN** the owner attaches `kommode-harmony.json` in a new conversation and piece `kommode-harmony` exists
- **THEN** the reply names `kommode-harmony.json` and "Kommode Harmony (Höffner 13207807)" (`kommode-harmony`) with the three ways on
- **AND** no specialist runs, the room question is not asked, and nothing is imported

#### Scenario: Name inside the design matches
- **WHEN** the owner attaches `export.json` whose design is named "Sideboard" and piece `sideboard-1200` is named "Sideboard"
- **THEN** the reply names `sideboard-1200` with the three ways on

#### Scenario: Keep both with a new name
- **WHEN** after that reply the owner answers "keep both, call it Sideboard Hall"
- **THEN** the Designer previews importing `export.json` as a new piece named "Sideboard Hall"
- **AND** on yes the piece is created and `sideboard-1200` is unchanged

#### Scenario: Keep both without a name
- **WHEN** after that reply the owner answers "keep both"
- **THEN** the Designer asks for the new piece's name, and nothing is imported yet

#### Scenario: New name still matches
- **WHEN** `import_design` is called with the name "sideboard" while piece `sideboard-1200` is named "Sideboard"
- **THEN** the tool refuses saying a piece already has that name

#### Scenario: No match
- **WHEN** the owner attaches `lamellen-kommode.json` named "Lamellen-Kommode" and no piece has that id or name
- **THEN** the turn is handled as before

#### Scenario: Bound to the matching piece
- **WHEN** the owner attaches `kommode-harmony.json` in `kommode-harmony`'s own conversation
- **THEN** no conflict reply is given, and the file can be imported as `kommode-harmony`'s next version as before
