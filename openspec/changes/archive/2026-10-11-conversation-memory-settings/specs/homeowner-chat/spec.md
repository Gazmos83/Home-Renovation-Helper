## ADDED Requirements

### Requirement: The owner reads, corrects and compresses the conversation's notes
Beside the chat, the owner SHALL see a "Decisions so far" panel holding the note for the active build, or the conversation's own note when no build is active, or that there is none yet. The owner SHALL be able to edit and save the note; a saved edit SHALL be marked as the owner's and used as written from the next call. The panel SHALL offer a "compress now" action, as set out in the token-budget spec. The panel SHALL NOT show tokens, budgets, models or costs. Saved note text SHALL be neutralised so it cannot carry the untrusted-content delimiter. The routes SHALL require the owner's session and SHALL answer 404 for another thread's id that does not exist.

#### Scenario: Note shown
- **WHEN** the active build `hall-bench` has a stored note
- **THEN** the panel shows that note, and no token figure or model name

#### Scenario: No note yet
- **WHEN** the conversation has never been compressed
- **THEN** the panel says there is no note yet and offers "compress now"

#### Scenario: Owner edits the note
- **WHEN** the owner changes "doors: hinged" to "doors: push-latch" and saves
- **THEN** the next call sends the edited note, marked as the owner's

#### Scenario: Delimiter in an edited note
- **WHEN** the owner's edited note contains the untrusted-content delimiter
- **THEN** it is stored and sent neutralised

#### Scenario: Without a login
- **WHEN** the note route is called without the owner's session
- **THEN** it answers 401
