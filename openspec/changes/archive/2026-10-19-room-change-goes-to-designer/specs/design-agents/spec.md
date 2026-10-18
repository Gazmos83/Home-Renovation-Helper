## MODIFIED Requirements

### Requirement: A room is designed without a piece
When the owner asks to design or furnish a room rather than a piece, Intake SHALL confirm the room, or the apartment, through `confirm_room` or `record_plan`. It SHALL then ask what the room should hold: approved pieces of the house file, stand-ins with their sizes, or models of the library, or nothing. It SHALL NOT ask which piece to design, the purpose of a piece, or a piece's size or budget, and it SHALL NOT call `record_brief` for a room-only wish. Once the room is confirmed, its hand-off SHALL offer to compose the room, not to design a piece.

While the conversation has a confirmed room or apartment, a turn whose request the Foreman classifies as composing a room SHALL go to the Designer, whether or not the owner's message names the room, and with no piece and no brief. This SHALL hold when the Foreman's model chose Intake or the Builder. Moving, adding, removing or re-placing an item in a composed room SHALL count as composing it. A request to render a composition SHALL still go to the Builder. A request to design a new piece in a conversation with no brief SHALL still go to Intake.

#### Scenario: Room wish
- **WHEN** a conversation has no confirmed room and the owner, after attaching a plan, writes "design the living room"
- **THEN** Intake confirms `Wohnen` and then asks what the room should hold, and no reply asks which piece to design

#### Scenario: Compose without naming the room
- **WHEN** the confirmed room is `Wohnen`, the thread has no piece and no brief, and the owner writes "put a sofa stand-in 2200 by 900 against the window wall"
- **THEN** the Designer answers, not Intake

#### Scenario: Piece wish still goes to Intake
- **WHEN** the confirmed room is `Wohnen`, the thread has no piece and no brief, and the owner writes "I want a new bookshelf"
- **THEN** Intake answers

#### Scenario: Move after a composition was built
- **WHEN** `Wohnen` v13 is built, the last reply said the Builder can render it, the Foreman's model picks the Builder and flags composing, and the owner writes "Please move the table 500 mm away from wall 1 and 600 mm away from wall 5"
- **THEN** the Designer answers, not the Builder

#### Scenario: Render still goes to the Builder
- **WHEN** `Wohnen` v13 is built and the owner writes "render the room"
- **THEN** the Builder answers

### Requirement: A tool outside the specialist's set is refused naming its owner
When a specialist calls a tool it has not bound, nothing SHALL run and the call's result SHALL name the tool and either the specialist or specialists whose instruction header names it, or, when the specialist's own header names it but its plugin is switched off for the thread, that the tool is switched off in this conversation's tools. The result SHALL state that nothing was done. Every specialist's instructions SHALL tell it to say so plainly to the owner (that nothing was saved or changed, and why) and never to describe the refusal as the tool failing or refusing an update.

The one exception SHALL be `compose_room`. When a specialist other than the Designer calls it as the only tool call of its round, and the `compose_room` plugin is enabled, nothing SHALL run. The application SHALL continue the same turn in the Designer. That specialist's reply for the round, with its text, its tool call and the call's result, SHALL NOT be shown or kept. The Designer SHALL be told that the owner's latest messages ask to change the room and SHALL follow its change-list rule. This hand-off SHALL be decided by the application, not by a model, and SHALL happen at most once per turn.

#### Scenario: Designer calls Intake's tool
- **WHEN** the Designer calls `record_brief`
- **THEN** nothing is saved, the call's result names `record_brief` and Intake and says nothing was done, and no confirmation is raised

#### Scenario: Own tool switched off
- **WHEN** the Designer calls `cut_list` on a thread where the `cut_list` plugin is switched off
- **THEN** nothing runs and the result says `cut_list` is switched off in this conversation's tools

#### Scenario: Builder calls compose_room
- **WHEN** the Builder answers "That's the only change, please continue" by calling `compose_room` alone, with the text "I'll pass this change to the Designer"
- **THEN** nothing runs, the Designer answers in the same turn with its change list or the `compose_room` summary, and the owner's chat shows neither the Builder's text nor a refusal

#### Scenario: compose_room beside other calls
- **WHEN** the Builder calls `render_turntable` and `compose_room` in the same round
- **THEN** `compose_room` is refused naming the Designer, as for any other foreign tool, and no hand-off happens

## ADDED Requirements

### Requirement: A specialist knows its role and does not relay
Each specialist's prompt SHALL carry a fixed note, composed by code, naming the specialist it is on this turn. The note SHALL say that earlier assistant replies in the conversation may have been written by other specialists and that their limits are not its own. No specialist SHALL offer to pass a request to another specialist or say that it cannot see another specialist's work. A specialist other than the Designer that is asked to change a room SHALL say in one sentence that the room has not been changed, and SHALL NOT gather or confirm the room's change list.

#### Scenario: Designer after the Builder's refusals
- **WHEN** earlier replies in the thread said "moving furniture is done by the Designer, not by me" and the owner asks "Will you move the table?" on a turn the Designer answers
- **THEN** the Designer does not say the move is someone else's job; it restates the change list or calls `compose_room`

#### Scenario: Owner asks about progress
- **WHEN** the owner asks "Is the designer working on the room?"
- **THEN** the reply says whether a new room version was created or is waiting for the owner's yes, and does not say it cannot see the Designer's activity
