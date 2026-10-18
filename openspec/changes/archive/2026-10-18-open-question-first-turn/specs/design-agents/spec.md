## ADDED Requirements

### Requirement: An open question is answered before the room offer
The Foreman's routing decision SHALL say whether the owner's message is an open question: the owner asks about or thinks aloud about a piece (usual sizes or heights, materials, ideas, what works) without asking for anything to be designed, imported, built, rendered, reviewed or priced. While the conversation has no confirmed room or apartment and has not declined one, a turn the routing model marks as an open question SHALL go to the Designer instead of being answered with "Would you like to view this piece in a room?". This rule comes after the design-file conflict reply, the code-answered height question, the help question and the Researcher's questions (price, product, guideline or engineering), which keep their order. A turn that carries a plan, a photo or a design file SHALL NOT be an open question.

On an open-question turn the Designer SHALL answer in plain words and SHALL have only its guideline search tool. It SHALL NOT create, import or revise a piece, compose a room, record a brief, a decision or a verdict, or ask a form, and it SHALL NOT ask which room the piece is for. The turn SHALL NOT change the conversation's confirmed room, its declined flag or its bound piece. The next turn that is not an open question is routed by the other rules, so a wish for a piece then gets the room offer.

#### Scenario: Brainstorming in a new conversation
- **WHEN** a new conversation has no confirmed room and the owner writes "I'd like to build a kitchen counter, how tall should it be?"
- **THEN** the Designer answers with a height for a kitchen counter, no piece is created, and the reply does not ask about a room

#### Scenario: The wish after the question gets the room offer
- **WHEN** the Designer answered an open question in a conversation with no room, and the owner then writes "OK, design me one 900 mm high"
- **THEN** the reply is "Would you like to view this piece in a room?" and no specialist runs

#### Scenario: A request phrased as a question is not brainstorming
- **WHEN** a conversation has no confirmed room and the owner writes "Can you design a shoe bench for me?"
- **THEN** the routing model does not mark it an open question and the reply is "Would you like to view this piece in a room?"

#### Scenario: A file is never an open question
- **WHEN** a conversation has no confirmed room and the owner attaches `lamellen-kommode.json` and asks "is this a good height?"
- **THEN** the reply is "Would you like to view this piece in a room?"

#### Scenario: Help and engineering keep their place
- **WHEN** a conversation has no confirmed room and the owner asks "how do I download the design template?"
- **THEN** Intake answers it as a help question
