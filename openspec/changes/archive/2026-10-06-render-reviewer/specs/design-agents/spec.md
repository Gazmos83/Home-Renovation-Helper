## MODIFIED Requirements

### Requirement: The Foreman routes each turn to one specialist
Each turn SHALL be handled by exactly one specialist — Intake, Designer, Builder, Researcher or Reviewer — chosen by the Foreman from the conversation and the house file, bounded by application rules: the Builder is never chosen when the thread has no bound piece with a built version, the Reviewer is never chosen unless the bound piece's latest version has a screenshot or a render, a thread with no piece and no confirmed brief goes to Intake unless the owner asks a question the Researcher answers (a price, a product, a guideline), and the Researcher prices only a bound piece's version. A pending confirmation SHALL resume in the specialist that raised it. The owner never names a specialist and a message cannot force one.

#### Scenario: New wish
- **WHEN** a thread has no piece and the owner describes what they want
- **THEN** Intake answers

#### Scenario: No piece, render asked
- **WHEN** a thread has no piece and the owner asks for a turntable
- **THEN** Intake or the Designer answers, explaining what must exist first; the Builder is not chosen

#### Scenario: Price question
- **WHEN** a thread's piece has a version and the owner asks what the boards will cost
- **THEN** the Researcher answers with a pricing of that version

#### Scenario: Review asked with nothing rendered
- **WHEN** the bound piece's latest version has no screenshot or render and the owner asks for a check
- **THEN** the Reviewer is not chosen and the reply says what must exist first

### Requirement: Each specialist runs on its routed model with its instruction file
Each specialist SHALL call the model routed for its slot (`intake`, `designer`, `builder`, `researcher`, `reviewer`; the Foreman on `foreman`) with that slot's generation profile, and SHALL be prompted from its checked-in instruction file: a header naming its tools (not editable) and text, followed by the fixed notes and the untrusted-content guard composed by code, exactly once and last. A missing or malformed instruction file SHALL stop startup naming the file.

#### Scenario: Prompt shape
- **WHEN** the Designer's prompt is assembled
- **THEN** it ends with the untrusted-content guard, contains it once, and binds exactly the tools its header names

#### Scenario: Instruction file missing
- **WHEN** `reviewer.md` is absent
- **THEN** startup fails naming `reviewer.md`
