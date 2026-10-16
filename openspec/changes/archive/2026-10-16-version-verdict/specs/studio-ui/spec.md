## ADDED Requirements

### Requirement: The inspector shows and sets the version's verdict
The inspector, both its page and the conversation's split view, SHALL show the shown version's verdict above its tabs as one compact row, on every tab, whether or not the version is built or rendered. The row SHALL hold a thumbs up ("Matches what I confirmed") and a thumbs down ("Doesn't match what I confirmed"), each with that accessible name and tooltip, the chosen one shown as pressed. With no verdict, only the two thumbs SHALL be shown. A note field SHALL appear only once a thumb is chosen. A thumbs up SHALL be saved at once, with an optional note. A thumbs down SHALL be saved only with a note that is not blank; until then nothing is saved. Pressing the chosen thumb again SHALL clear the verdict. Editing the note and pressing Enter or leaving the field SHALL save it. For a thumbs down, the row SHALL show whether it is open, resolved or dismissed, and offer "Mark resolved" and "Dismiss" while it is open. Switching versions SHALL show that version's verdict. A refusal SHALL be shown with its reason next to the row. The row SHALL NOT show a model name, prompt, token count or cost, and it SHALL pass a recorded browser check before it counts as done.

#### Scenario: Blockout marked wrong in the inspector
- **WHEN** the owner opens `amesbury-wardrobe` v4, presses thumbs down, writes "the side sections lost their 5 drawers" and presses Enter
- **THEN** thumbs down is shown pressed with the note and "open", and a reload shows the same

#### Scenario: Note required
- **WHEN** the owner presses thumbs down and saves with an empty note
- **THEN** nothing is saved and the row asks for what does not match

#### Scenario: No note field before a choice
- **WHEN** the owner opens a version with no verdict
- **THEN** only the two thumbs are shown

#### Scenario: Cleared by pressing again
- **WHEN** the owner presses thumbs up on a version whose verdict is thumbs up
- **THEN** the verdict is cleared and the note field is gone

#### Scenario: Resolved
- **WHEN** the owner marks v4's open thumbs down resolved
- **THEN** the row shows it as resolved and no longer offers resolve or dismiss
