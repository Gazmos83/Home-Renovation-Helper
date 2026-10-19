## MODIFIED Requirements

### Requirement: A specialist's empty answer is never the turn's reply
When a specialist's final answer has no text and no tool call, the specialist SHALL be called once more with a note that its answer was empty. If the second answer is also empty, the turn SHALL end with a fixed reply naming the specialist by its persona (for example "Lil' Worm" for Intake) and asking the owner to rephrase or ask again. Both calls SHALL be counted against the slot's token budget like any other.

#### Scenario: Empty then answered
- **WHEN** Intake's first answer to "Revise it" is empty and its second is a sentence
- **THEN** the owner sees the sentence and no empty entry

#### Scenario: Empty twice
- **WHEN** Intake answers empty twice
- **THEN** the turn's reply says "Lil' Worm gave no answer. Please rephrase your message or ask again."
