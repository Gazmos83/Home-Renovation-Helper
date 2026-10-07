## ADDED Requirements

### Requirement: Room corrections go to Intake
A message that corrects or adds to a room's measurements, corners, corner angles, ceiling height, wall thickness or openings, or that attaches a new or revised plan of a room, SHALL be handled by Intake, also when the thread has a confirmed brief or a bound piece. Intake SHALL propose the corrected room through `record_brief` or `record_plan` and the owner's `yes`, as for a first brief. A change to the piece itself (its size, modules, shelves, fronts or materials) SHALL stay with the Designer.

#### Scenario: Corner angle corrected after the brief
- **WHEN** a thread has a confirmed brief for the living room and the owner writes "bottom wall/left wall corner = 76°"
- **THEN** Intake answers and proposes the corrected room for confirmation

#### Scenario: Revised plan attached after a piece exists
- **WHEN** the bound piece has a version and the owner attaches `blueprint_revision.png` saying it is the source of truth for the room
- **THEN** Intake answers

#### Scenario: Piece change stays with the Designer
- **WHEN** a thread has a confirmed brief and the owner writes "make it 2206 mm wide"
- **THEN** the Designer answers

### Requirement: A tool outside the specialist's set is refused naming its owner
When a specialist calls a tool it has not bound, nothing SHALL run and the call's result SHALL name the tool and either the specialist or specialists whose instruction header names it, or, when the specialist's own header names it but its plugin is switched off for the thread, that the tool is switched off in this conversation's tools. The result SHALL state that nothing was done. Every specialist's instructions SHALL tell it to say so plainly to the owner (that nothing was saved or changed, and why) and never to describe the refusal as the tool failing or refusing an update.

#### Scenario: Designer calls Intake's tool
- **WHEN** the Designer calls `record_brief`
- **THEN** nothing is saved, the call's result names `record_brief` and Intake and says nothing was done, and no confirmation is raised

#### Scenario: Own tool switched off
- **WHEN** the Designer calls `cut_list` on a thread where the `cut_list` plugin is switched off
- **THEN** nothing runs and the result says `cut_list` is switched off in this conversation's tools

### Requirement: No specialist promises to report back after the turn
A turn SHALL end with its reply, and nothing SHALL message the owner afterwards. No specialist's instructions SHALL let it promise to tell the owner later when a build, a render or a review finishes. The Builder and the Designer SHALL say that a started build's status shows in the conversation's Project panel and can be asked for in a later message.

#### Scenario: Owner asks to be told when the build is done
- **WHEN** a build has started and the owner asks "Will you tell me when the build is complete?"
- **THEN** the reply says the Project panel shows the build's status and that the owner can ask again, and it does not promise a later message
