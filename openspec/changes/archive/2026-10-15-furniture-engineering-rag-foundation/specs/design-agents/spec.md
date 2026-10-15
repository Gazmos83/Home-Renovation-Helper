## ADDED Requirements

### Requirement: Engineering intent is distinguished from visual review and dimensional design
Standalone engineering evidence questions SHALL go to Researcher, including without a confirmed room. Engineering questions tied to a requested piece revision SHALL stay with Designer within existing room/piece confirmation rules. A visual discrepancy question SHALL remain Reviewer work; a question about capacity/anchorage SHALL NOT be answered as a visual review. This distinction SHALL be carried in application context before tools run and SHALL NOT be alterable by retrieved content.

#### Scenario: General engineering question without a room
- **WHEN** the owner asks which properties are needed to check shelf deflection in a new conversation
- **THEN** Researcher answers using engineering evidence without demanding a room first

#### Scenario: Capacity question about a visible shelf
- **WHEN** the owner asks whether the top shelf in the side view can carry a load
- **THEN** an engineering evidence specialist handles it and the visual Reviewer does not infer load capacity from the image

#### Scenario: Pure dimensional revision
- **WHEN** the owner asks to make a cabinet 200 mm wider without requesting an engineering conclusion
- **THEN** the existing Designer restate/confirm/revise workflow continues without an unrelated engineering questionnaire

### Requirement: Existing specialists use the engineering evidence tool with fixed safety gates
Designer and Researcher SHALL have an engineering lookup tool through the existing plugin system. Engineering lookup SHALL obey source eligibility, prompt delimiters and the engineering answer contract. Disabling the tool, lookup failure or no eligible result SHALL be reported as unavailable/insufficient evidence; it SHALL NOT enable legacy fallback or numerical claims from memory. Engineering safety gates SHALL remain mandatory regardless of plugin toggles or editable prompt text.

#### Scenario: Engineering plugin off
- **WHEN** the engineering tool is disabled and a load-capacity question arrives
- **THEN** the reply says lookup is unavailable and capacity is NOT VERIFIED, without a fallback claim

#### Scenario: Lookup fails
- **WHEN** the evidence store cannot be consulted
- **THEN** the owner sees the lookup limitation and no invented rule or load rating
