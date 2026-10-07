## ADDED Requirements

### Requirement: Intake and the Designer ask questions through a form
Intake and the Designer SHALL have an `ask_owner` tool, from a plugin that cannot be toggled off, that takes one to eight questions, each with its text (1–200 characters), an optional unit and optional choices (two to eight, each 1–60 characters). A valid call SHALL pause the turn with the questions pending; an invalid call SHALL be refused to the model with the reason and pause nothing. The answers (or the owner's message when the set is declined) SHALL return to the specialist as the tool's result in the same turn. Only one pending item SHALL be raised per round: an `ask_owner` call in a round that already pauses on a confirmation SHALL be refused as not run.

#### Scenario: Missing figures
- **WHEN** Intake lacks the ceiling height and the budget
- **THEN** it calls `ask_owner` with both questions, with units mm and EUR, and the turn pauses

#### Scenario: Too many questions
- **WHEN** a specialist calls `ask_owner` with nine questions
- **THEN** the call is refused to the model naming the limit and nothing is pending

### Requirement: A note that disagrees with the house file is resolved before numbers are proposed
When a text note attached by the owner gives a figure that disagrees with the house file or with a plan read in the same conversation, Intake SHALL list each disagreement in a table — what it is, the note's value, the other value and its source — and ask which value holds before proposing numbers through `record_brief` or `record_plan`. A disagreement SHALL never be resolved silently in either direction.

#### Scenario: Ceiling disagrees
- **WHEN** the house file has Wohnen's ceiling at 2500 mm and the attached note says 2450 mm
- **THEN** Intake's reply shows a table row for the ceiling with both values and their sources and asks which holds, and no brief is proposed in that turn
