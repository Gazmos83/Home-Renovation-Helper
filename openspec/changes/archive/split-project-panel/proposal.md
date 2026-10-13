## Why

The conversation's Project flyout carries everything at once: the piece (approval, versions, picture, inspect, looks), the room (approval, looks, inspect) and the progress steps. It is long, and a piece question and a room question are mixed in one scroll. Three flyouts, one per subject, keep each short.

## What Changes

- The rail shows six icons: Tools, Decisions so far, **Brief**, **Project**, **Piece** and **Room** (Project, Piece and Room replace the single Project icon; Brief is new).
- **Brief** lists every brief setting of the conversation and lets the owner edit them in place: room (chosen from the stored rooms), purpose, highest the piece may be (mm), style and budget (EUR). Saving writes the brief to the conversation and, when a piece is bound, to that piece's stored brief, which the Reviewer reads. An edit is the owner's own confirmation, so it needs no yes/no card. Two new routes: read and save a thread's brief.
- **Project** keeps the progress steps, the next step, and the open review items line.
- **Piece** takes the piece's name, id and build state, its approval controls, the "N of 15 versions" note, delete version, the latest picture, "Inspect version N", the piece looks, and the "Waiting on a generator extension" list.
- **Room** takes the selected room section unchanged (approval, delete version, room looks, "Inspect <room>").
- Each flyout keeps its empty state in words: Piece says "No piece yet."; Room says "No room selected yet."
- **Room picture:** the Room panel shows the approved composition version's picture (as the Piece panel shows a piece's latest), from a new `approved_picture` field on the room in the progress read.
- **Agents read the brief:** the facts line given to the Foreman and every specialist carries the brief's settings, so an edit in the Brief tab reaches the next turn.
- **Specs:** every other requirement that says "Project panel" for piece or room content (approval, delete version, header, notices, version limit, pricing refusal, room 3D) is modified to name the Piece or Room panel; the progress requirement is split between Project and Piece.
- **Not changed:** apart from the Brief routes, no data, API or behaviour change; the same controls with the same labels and the same refresh while a build or render runs. The one backend touch is the wording of render and build notices (`backend/app/agent/notices.py`, and the `homeowner-chat` spec line that quotes it): "Project panel" becomes "Piece panel" for a piece version.

Changing the room in the Brief shows that room's stored measurements before saving, as every route into a conversation's room does; room measurements themselves are not edited here.

**Ladder step:** none (the brief is not the spec; no dimension is written). **Agents:** none. **Render guard and bpy allow-list:** unaffected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: the owner can read and edit a conversation's brief outside a chat turn, and the agents' facts carry it.
- `design-agents`, `house-file`, `furniture-packages`: wording only, "Project panel" becomes "Piece panel".
- `studio-ui`: the rail's Project icon becomes Project, Piece and Room icons, and the project panel's content is divided between them.

## Assumptions

- `TODO(user)`: which content goes in which tab is my reading (above). The owner has not yet said whether the steps should sit in Piece or the generator-extension list in Project.
- `TODO(user)`: "all Brief settings" is read as the five fields `record_brief` stores (room, purpose, max piece height, style, budget). Tell me if you meant more, such as room measurements.
- `TODO(user)`: an edit replaces both the conversation's brief and the bound piece's brief. Editing the height limit by hand also clears the "raised by version N" note.
- Style and budget are saved to the house file preferences only while the memory settings save preferences, as `record_brief` does.
