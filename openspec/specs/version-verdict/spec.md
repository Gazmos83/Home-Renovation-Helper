# version-verdict Specification

## Purpose

Lets the owner say whether a piece version matches what they confirmed, with a note of what is wrong, so the mistake reaches the Designer's next revision and is counted against the model that produced the version, even when the version has no render.

## Requirements

### Requirement: Each new version records the slot and model that produced it
When an agent tool creates a piece version (a new piece, a revision, or an imported design or version), the service SHALL record on that version the slot and model of the agent that called the tool. A version created outside an agent turn, or before this requirement, SHALL record no slot and no model. The slot and model SHALL NOT be written into the version folder and SHALL NOT appear in any homeowner response.

#### Scenario: Designer revises a piece
- **WHEN** the Designer, routed to `~deepseek/deepseek-v4-flash-latest`, creates `amesbury-wardrobe` v5 with `revise_package` after the owner's "yes"
- **THEN** v5 records slot `designer` and that model

#### Scenario: Older version
- **WHEN** the developer reads the origin of `amesbury-wardrobe` v4, made before this change
- **THEN** it has no slot and no model

### Requirement: The owner gives a version a verdict
The owner SHALL be able to give any recorded piece version, whether built, unbuilt, rendered or not, a verdict of `matches` ("Matches what I confirmed") or `mismatch` ("Doesn't match"), with a note of at most 1 000 characters. A `mismatch` verdict SHALL require a note that is not blank. Giving a verdict again SHALL replace the version's verdict, and clearing SHALL remove it. A version holds at most one verdict. A verdict for a version that is not recorded SHALL be refused, naming the version. Saved note text SHALL be neutralised so it cannot carry the untrusted-content delimiter. The routes SHALL require the owner's session. A verdict SHALL NOT change any spec, dimension, figure, price, approval, build or render.

#### Scenario: Blockout marked wrong
- **WHEN** `amesbury-wardrobe` v4 has only its blockout screenshots and the owner marks it "Doesn't match" with "the side sections lost their 5 drawers"
- **THEN** the verdict is stored on v4 as `mismatch` with that note, and it is open

#### Scenario: Mismatch without a note
- **WHEN** the owner marks a version "Doesn't match" with an empty note
- **THEN** it is refused saying a note of what does not match is needed, and nothing is stored

#### Scenario: Changed mind
- **WHEN** the owner marks v4 "Matches what I confirmed" after marking it "Doesn't match"
- **THEN** v4 has one verdict, `matches`, and the earlier one is gone

#### Scenario: Unknown version
- **WHEN** the owner gives a verdict on `amesbury-wardrobe` v9, which does not exist
- **THEN** it is refused naming version 9, and nothing is stored

### Requirement: A mismatch stays open until the owner closes it
A `mismatch` verdict SHALL be `open` when given or changed, and the owner SHALL be able to mark it `resolved` or `dismissed`. A `matches` verdict has no status. Approving, unapproving or revising a version SHALL NOT change any verdict's status, and an open verdict SHALL NOT block approving the version. Deleting a version SHALL delete its verdict.

#### Scenario: Resolved after a fix
- **WHEN** the owner marks v4's open mismatch resolved after v5 restored the drawers
- **THEN** v4's verdict is `resolved` and is no longer among the open verdicts

#### Scenario: Approval not blocked
- **WHEN** v4 has an open mismatch and the owner approves v4
- **THEN** v4 is approved and its verdict stays open

#### Scenario: Version deleted
- **WHEN** the owner deletes v4, which has a verdict
- **THEN** the verdict is gone with the version

### Requirement: A verdict given in chat is confirmed before it is recorded
When the owner says in words that a version is right or wrong, the Designer SHALL propose a verdict, naming the piece, the version, the verdict and the note it read. Nothing SHALL be stored before the owner answers `yes`; on any other answer nothing SHALL be stored. The piece SHALL be the conversation's bound piece, never a value the model supplies. When the owner does not say which version, the proposal SHALL use the piece's latest version. The same checks as the owner's routes SHALL apply. The tool SHALL be switchable per conversation like other plugins.

#### Scenario: Spoken mismatch
- **WHEN** in a conversation bound to `amesbury-wardrobe` the owner writes "v4 is wrong, the side drawers are missing"
- **THEN** the reply asks to record "Doesn't match — the side drawers are missing" on `amesbury-wardrobe` version 4, and it is stored only after `yes`

#### Scenario: Declined
- **WHEN** the owner answers `no` to a proposed verdict
- **THEN** nothing is stored

#### Scenario: No piece bound
- **WHEN** the conversation has no bound piece and the owner says "this version is wrong"
- **THEN** no verdict is proposed and the reply asks which piece is meant

### Requirement: Verdicts reach tracing as tagged feedback
When tracing is configured, every stored or changed verdict SHALL be recorded as a feedback trace tagged with the verdict and, when known, the version's slot and model, carrying the note. A tracing failure SHALL be logged and SHALL NOT affect the stored verdict. With tracing off, nothing SHALL be sent anywhere.

#### Scenario: Traced mismatch
- **WHEN** tracing is configured and the owner marks v5, made by the Designer, "Doesn't match"
- **THEN** a feedback trace tagged `mismatch`, slot `designer` and the Designer's model is recorded with the note

#### Scenario: Tracing unreachable
- **WHEN** tracing is configured but unreachable and the owner gives a verdict
- **THEN** the verdict is stored and the owner sees no error
