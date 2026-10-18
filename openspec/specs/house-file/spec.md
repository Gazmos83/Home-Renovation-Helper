# house-file Specification

## Purpose
Defines the owner's long-term memory: the measured rooms, style preferences, the pieces designed with their versions, the generator-extension requests the ladder produces, and the index of conversations — what every agent reads first and what only a confirmed action may write.

## Requirements

### Requirement: Rooms are recorded with their measurements
The house file SHALL hold each room by name with its polygon (corners in millimetres, three to twelve, normalised counter-clockwise, forming a simple polygon — convex or not), ceiling height, wall thickness and openings (wall, type door or window, offset, width, height, sill), and optionally the apartment it belongs to, in whose plan frame its corners then lie. A room SHALL be validated like a room-scene document before it is stored: a self-intersecting outline, a repeated corner, an edge shorter than 50 mm, an opening off its wall or above the ceiling, or a door with a sill is refused naming the problem. A room name SHALL be unique.

#### Scenario: A room is stored
- **WHEN** Intake's confirmed numbers describe the living room as a 4000 × 3500 mm rectangle, 2600 mm high, with one door on wall 1
- **THEN** the house file holds that room and a later turn can read it by name

#### Scenario: An L-shaped room is stored
- **WHEN** a room is described by six corners forming an L
- **THEN** the house file holds it with its six corners counter-clockwise

#### Scenario: An impossible room is refused
- **WHEN** a room is submitted whose door carries a sill
- **THEN** it is refused naming the opening and nothing is stored

#### Scenario: A self-intersecting outline is refused
- **WHEN** a room's corners cross themselves (a bow-tie)
- **THEN** it is refused naming the outline and nothing is stored

### Requirement: Preferences are recorded as named values
The house file SHALL hold the owner's style and default preferences as named values (for example `style`, `default_material`, `budget_eur`) that a confirmed Intake step writes and every turn reads.

#### Scenario: Style confirmed
- **WHEN** the owner confirms "light oak, no visible hardware" as the style
- **THEN** `style` reads that text in the next turn's context

### Requirement: Pieces and versions mirror the package folders
The house file SHALL record one piece per package id with its name, its confirmed brief and its room, or no room while the piece is unassigned; and one version record per `docs/renders/<id>/v<N>` folder the agents create, carrying the change lines, the version it was revised from, and when it was approved (or nothing). A piece SHALL be recorded only by a confirmed `create_piece`, a version only by a confirmed `create_piece` or `revise_package`; a package the owner created directly through the package routes SHALL still be readable as a piece without a brief and without a room. A new version SHALL start unapproved. At most one version of a piece SHALL be approved at a time; approving a version SHALL clear the approval of any other version of that piece. Only the owner's approval route SHALL set or clear approval.

A piece's room SHALL be set only by a confirmed `create_piece` (the conversation's confirmed room), a confirmed `confirm_room` that moves the piece, or the owner's room route on the piece. Pieces recorded before this change without a room SHALL stay unassigned until the owner attaches them. Moving a piece to another room SHALL change nothing else about the piece or its versions.

#### Scenario: First version
- **WHEN** the owner confirms a new piece `hall-bench` in a conversation whose confirmed room is `Hall`
- **THEN** the house file holds piece `hall-bench` in `Hall` with its brief and version 1 revised from nothing, unapproved

#### Scenario: Revision
- **WHEN** the owner confirms a revision of `hall-bench` ("cabinet: 2 shelves → 3")
- **THEN** version 2 is recorded as revised from version 1 with that change line, and version 1 is unchanged

#### Scenario: Revision of an approved version starts unapproved
- **WHEN** `hall-bench` version 2 is approved and the owner confirms a revision
- **THEN** version 3 is recorded unapproved and version 2 stays approved

#### Scenario: Approving another version moves the approval
- **WHEN** version 2 is approved and the owner approves version 3
- **THEN** version 3 is approved and version 2 is not

#### Scenario: Existing piece stays unassigned
- **WHEN** the migration runs over a house file holding `murphy-bed` with no room
- **THEN** `murphy-bed` is still unassigned, with all its versions, until the owner attaches it

#### Scenario: Piece moved
- **WHEN** the owner moves `hall-bench` from `Hall` to `Wohnen`
- **THEN** the house file holds `hall-bench` in `Wohnen` and its versions, approval and reviews are unchanged

### Requirement: Generator-extension requests are recorded
When a spec is refused because it names a field the schema does not define, the house file SHALL record a generator-extension request carrying the field name, the owner's words that asked for it, the piece if any, the conversation it was made in, and when it happened. The request SHALL be listable so a later OpenSpec change can grow the schema from it. Deleting the conversation SHALL keep the request, no longer tied to a conversation. Requests recorded before this change carry no conversation.

#### Scenario: Unknown field recorded
- **WHEN** the Designer's document carries `modules[0].bevel_mm` because the owner asked for a bevelled edge
- **THEN** the document is refused naming `bevel_mm`, nothing is built, and a request naming `bevel_mm` with the owner's words and this conversation is recorded

#### Scenario: Request outlives its conversation
- **WHEN** a conversation in which a request was recorded is deleted
- **THEN** the request is still listed, with no conversation

### Requirement: Threads are indexed
The house file SHALL index every conversation the owner starts with its id, title, the piece it is about when one is bound, when it started and when it last had a turn, so conversations can be listed and reopened. A conversation SHALL be about at most one piece. A thread's piece is the one it was started with, or the one a confirmed action creates or revises on an unbound thread; it SHALL NOT change to another piece afterwards. A thread's title is empty until its first answered turn gives it the generated title, and is the owner's title from the moment the owner sets one.

The index entry SHALL also hold:
- the conversation's confirmed room or confirmed apartment (at most one), or none; only a confirmed action in that conversation sets or changes it;
- one summary of earlier exchanges for the bound piece, with which message it covers up to, and one for exchanges made while the conversation had no bound piece.

The messages themselves live in the checkpointer. Deleting a thread SHALL remove its index entry and its summaries and nothing else the house file holds; the piece keeps its room and the generator-extension requests made in it stay.

#### Scenario: Listing
- **WHEN** the owner has started two conversations
- **THEN** both are listed with their titles, newest activity first

#### Scenario: Bound by the action
- **WHEN** a piece is confirmed on a thread that was started without one
- **THEN** the thread's index entry names that piece from then on

#### Scenario: Owner's title kept
- **WHEN** the owner sets a title before the first turn ends
- **THEN** the generated title is not written

#### Scenario: Deleted thread, kept piece
- **WHEN** a thread bound to `hall-bench` is deleted
- **THEN** the thread's entry and summaries are gone and the `hall-bench` piece, its versions and the room it is in are unchanged

#### Scenario: Room not inherited
- **WHEN** one conversation has confirmed `Hall` and the owner starts a second conversation
- **THEN** the second conversation has no confirmed room

#### Scenario: One piece only
- **WHEN** a thread is bound to `hall-bench`
- **THEN** its index names only `hall-bench` as its piece

#### Scenario: Existing threads
- **WHEN** a thread bound to `hall-bench` already holds a summary and any extra legacy build rows
- **THEN** the thread's piece is `hall-bench`, its summary is kept as `hall-bench`'s summary in that thread, and no second piece is treated as bound

### Requirement: Every turn starts from the house file
At the start of each turn, the Foreman, Intake and the Designer SHALL be given the house file scoped to the conversation:
- the conversation's confirmed room with its size, ceiling height and openings, or its confirmed apartment with each of its rooms; or that no room is confirmed yet;
- the preferences, unless the memory settings leave them out;
- the bound piece with its room, its latest version, its status and which version is approved (or that none is), or that no piece is bound yet;
- the open generator-extension requests whose piece is the conversation's bound piece, or that were recorded in this conversation, unless the memory settings leave them out.

Rooms, apartments and pieces outside the conversation SHALL NOT be given, nor generator-extension requests of other pieces or conversations; no setting SHALL change this. Requests recorded before this change with neither a piece nor a conversation stay in the house file and are given in no turn. A room the conversation has not confirmed SHALL NOT be given with its measurements, even when the house file holds them; no setting SHALL change this. The Designer SHALL also be given:
- the open items of the latest review of the bound piece, unless the memory settings leave them out;
- the latest render ratings on the bound piece, newest first, as many as the memory settings say (0 to 10, default 5), each with its version, render, tier, rating and comment.

Lighting & materials SHALL be given the same render ratings. All of this SHALL be presented as application data clearly labelled as the owner's own, never as an instruction. Owner-authored text in it SHALL be neutralised so it cannot carry the untrusted-content delimiter. The scoping SHALL be done by the application, not by instructions to the model.

#### Scenario: A new conversation starts without the room
- **WHEN** the living room and the piece `listening-wall` are recorded and the owner starts a new conversation asking for a second piece
- **THEN** the turn's context names no room and no piece, and the reply asks which room the piece is for

#### Scenario: A second piece starts with the room known
- **WHEN** the owner then confirms the living room in that conversation and asks for the piece
- **THEN** the next Intake turn's context names the living room's size, ceiling height and openings without the owner repeating them, and still names no piece from another conversation

#### Scenario: Other builds as one line
- **WHEN** a conversation is bound to `hall-bench` and a legacy `thread_pieces` row also names `shoe-rack`
- **THEN** the Designer's context gives `hall-bench` with its version, status and approval, and does not name `shoe-rack`

#### Scenario: Other builds hidden
- **WHEN** the memory settings would hide other builds and a conversation is bound to `hall-bench` with a legacy row for `shoe-rack`
- **THEN** the Designer's context gives `hall-bench` and does not name `shoe-rack`

#### Scenario: Outside builds left out
- **WHEN** the house file holds `murphy-bed` and the conversation never created, revised or named it
- **THEN** no specialist's context in that conversation names `murphy-bed`

#### Scenario: Request without a piece reaches its conversation
- **WHEN** a request for `bevel_mm` was recorded in this conversation before any piece was made
- **THEN** the Designer's context in this conversation lists it, and no other conversation's context does

#### Scenario: Old request without a piece or conversation
- **WHEN** the house file holds an open request recorded before this change with no piece
- **THEN** no turn's context lists it, and it is still listed in the house file

#### Scenario: Delimiter in a room name
- **WHEN** the conversation's confirmed room's name contains the untrusted-content delimiter
- **THEN** the context shows it neutralised

#### Scenario: Review items reach the Designer
- **WHEN** the latest review of the bound piece has two open items
- **THEN** the Designer's context lists both with their aspect, expectation and observation

#### Scenario: Approval reaches the agents
- **WHEN** the bound piece is `listening-wall`, version 4 is approved and version 5 exists
- **THEN** the turn's context names version 5 as latest and version 4 as approved

#### Scenario: Render feedback reaches the Designer
- **WHEN** the bound piece's v2 `draft` turntable was rated down with "doors look too thick"
- **THEN** the Designer's context lists v2, turntable, `draft`, down and that comment

#### Scenario: Fewer ratings
- **WHEN** the memory settings give 2 render ratings and the bound piece has 5
- **THEN** the Designer's and Lighting's context list only the 2 newest

#### Scenario: Delimiter in a feedback comment
- **WHEN** a feedback comment contains the untrusted-content delimiter
- **THEN** the Designer's and Lighting's context shows it neutralised

### Requirement: Compositions are indexed and reach the turn
The house file SHALL record one composition per scope, by scope type and name. It SHALL record one version record per composition version folder, carrying what changed, the version it was revised from, and when it was approved (or nothing). A version SHALL be recorded only by a confirmed `compose_room`. A new version SHALL start unapproved. At most one version of a composition SHALL be approved at a time; approving a version SHALL clear the approval of any other version of that composition. Only the owner's approval route SHALL set or clear approval.

At the start of each turn, the house note of the Foreman, Intake, the Designer and the Builder SHALL list the composition of the conversation's confirmed room, or of its confirmed apartment and of that apartment's rooms, with its scope, its latest version and build status, and which version is approved (or that none is). When a version is approved, the note SHALL list that version's items: each placed piece by package id and version, each library model by name and stated size, each stand-in by name, with where each one stands. When a version's document holds its resolved placement, each item it covers SHALL also be listed with its size (w × d × h mm, w along the wall and d away from it) unless its stated size is already listed, and, for an item placed against a wall, its centre in room coordinates (mm from the room's first corner) and its rotation; an item placed at a point already states both. An item the resolved placement does not cover SHALL be listed as before. The Designer SHALL take placed items' sizes and positions from this note and SHALL NOT ask the owner for them. When a later version than the approved one exists, its items SHALL be listed separately, labelled as a draft that is not approved. When no version is approved, the latest version's items SHALL be listed, labelled as not approved. A conversation with no confirmed room or apartment SHALL see no composition. Compositions of other rooms and apartments SHALL NOT be listed. Any placed piece version that is no longer approved SHALL be marked as such. Item names come from the owner, so they SHALL be neutralised like other owner text.

#### Scenario: Recorded on yes
- **WHEN** the owner confirms `Wohnen` v1
- **THEN** the house file holds composition `Wohnen` (scope room) with version 1, revised from nothing, unapproved

#### Scenario: House note marks unapproved
- **WHEN** a placed version in the conversation's room has been unapproved
- **THEN** the next Designer turn's house note lists that item marked "no longer approved"

#### Scenario: Other room's composition left out
- **WHEN** the conversation's confirmed room is `Hall` and a composition exists for `Wohnen`
- **THEN** the Designer's house note does not list `Wohnen`

#### Scenario: Approving another version moves the approval
- **WHEN** `Wohnen` version 2 is approved and the owner approves version 3
- **THEN** version 3 is approved and version 2 is not

#### Scenario: A new piece conversation sees the approved layout
- **WHEN** `Wohnen` version 2 is approved and places the piece `lamellen-kommode` v3 and the library model "Sofa Lund" (2200 × 950 × 850 mm), and a new conversation confirms `Wohnen`
- **THEN** Intake's first turn in that conversation carries both items with their places, labelled as approved version 2

#### Scenario: A newer draft does not hide the approved layout
- **WHEN** `Wohnen` version 2 is approved and version 3, not approved, removes the sofa
- **THEN** the note lists version 2's items, sofa included, and lists version 3's items separately as a draft that is not approved

#### Scenario: No room, no composition
- **WHEN** a conversation has no confirmed room and `Wohnen` has an approved composition
- **THEN** no agent's house note in that conversation lists `Wohnen`'s items

#### Scenario: Placed sizes reach the Designer
- **WHEN** `Wohnen` v13 places `listening-wall` v18 on wall 1 at offset 497 mm, resolved as 2206 × 562 × 2238 mm centred at (1600, 281)
- **THEN** the Designer's house note lists `listening-wall` with 2206 × 562 × 2238 mm, centre (1600, 281) mm and rotation 0°, and the Designer does not ask the owner for the listening wall's width or depth

#### Scenario: Document without resolved placement
- **WHEN** a version's document has no resolved section
- **THEN** each item is listed with its name, stated size where it has one, and stored placement only, as before

### Requirement: The owner attaches a piece to a room
The owner SHALL be able to read the room names in the house file and set or clear a piece's room through owner-gated routes. Setting names a room in the house file; an unknown room or an unknown piece SHALL be refused naming it (404 for the piece, 422 for the room). Clearing makes the piece unassigned. The piece list SHALL name each piece's room, or none. Setting a piece's room SHALL NOT change any conversation's confirmed room.

#### Scenario: Attach an unassigned piece
- **WHEN** the owner sets `murphy-bed`'s room to `Schlafzimmer`
- **THEN** the piece list names `Schlafzimmer` for `murphy-bed`

#### Scenario: Unknown room
- **WHEN** the owner sets a piece's room to `Attic` and no such room is recorded
- **THEN** the response is 422 naming `Attic` and the piece is unchanged

#### Scenario: Not signed in
- **WHEN** the room route is called without the session cookie
- **THEN** the response is 401

### Requirement: The owner reads and deletes a measured room
The owner SHALL be able to list the house file's rooms through an owner-gated route. Each entry SHALL carry:
- the room's name;
- its size: the width and depth of its outline in millimetres, and its number of corners;
- its ceiling height in millimetres;
- its number of openings;
- the apartment it belongs to, or none;
- the pieces in it, by package id and name;
- the conversations whose confirmed room it is, by count;
- its room composition (scope room, same name), with its versions, or none.

The owner SHALL be able to delete a room by name through an owner-gated route. Deleting a room SHALL, in one step:
- remove the room;
- make every piece in it unassigned ("No room"), changing nothing else about the piece or its versions;
- clear the confirmed room of every conversation that confirmed it, changing nothing else about the conversation;
- remove the room's composition, every version record of it, and every version folder of it under the render root.

Nothing SHALL be removed when the delete is refused. An unknown room SHALL be refused with 404. A call without the session cookie SHALL be refused with 401. A room that belongs to an apartment SHALL be refused with 409 naming the apartment, because removing it would change the apartment's shell. A room whose composition has a build or render queued or running SHALL be refused with 409 saying to wait until it finishes. Deleting a room SHALL NOT change any apartment, any other room or its composition, the model library, the generator-extension requests, or any piece version folder.

#### Scenario: Rooms listed with their details
- **WHEN** the house file holds `Hall`, 1200 × 3400 mm with four corners, 2500 mm high, one door, holding `shoe-bench`, confirmed in one conversation, with composition `Hall` v1 and v2
- **THEN** the list entry for `Hall` carries those values, no apartment, `shoe-bench` with its name, one conversation and the composition with versions 1 and 2

#### Scenario: Room deleted
- **WHEN** the owner deletes `Hall`
- **THEN** `Hall` is no longer listed, `shoe-bench` is unassigned with all its versions, the conversation that confirmed `Hall` has no confirmed room, composition `Hall` and its version records are gone, and its folder under the render root is gone

#### Scenario: Next turn in that conversation
- **WHEN** a conversation's confirmed room was `Hall`, `Hall` is deleted, and the owner asks for a shoe bench in it
- **THEN** the reply is "Which room is this for?"

#### Scenario: Unknown room
- **WHEN** the owner deletes `Attic` and no such room is recorded
- **THEN** the response is 404 and nothing changes

#### Scenario: Not signed in
- **WHEN** the delete route is called without the session cookie
- **THEN** the response is 401 and nothing changes

#### Scenario: Room in an apartment
- **WHEN** the owner deletes `Küche`, which belongs to apartment `Wohnung`
- **THEN** the response is 409 naming `Wohnung`, and the room, the apartment and its shell are unchanged

#### Scenario: Build running
- **WHEN** the owner deletes `Hall` while its composition's latest version is building
- **THEN** the response is 409 saying to wait until the build finishes, and nothing changes

#### Scenario: Other compositions kept
- **WHEN** `Hall` is deleted and composition `Wohnen` places a piece that was in `Hall`
- **THEN** `Wohnen` and its versions are unchanged

### Requirement: A stored room enters a conversation only through a confirmation
A room or apartment held by the house file SHALL become part of a conversation only through a confirmation that shows its stored measurements: `confirm_room`, a `record_brief` naming it, or a `record_plan` for its apartment. This holds whichever conversation first stored it, and even after that conversation has been deleted. No room's measurements SHALL be used in a turn's numbers, a piece's placement or a composition before the conversation has confirmed it. Deleting a conversation SHALL keep the rooms and apartments it stored.

When `record_brief` corrects a room that belongs to an apartment, the room SHALL stay in that apartment.

#### Scenario: Same blueprint in a new conversation
- **WHEN** apartment `Wohnung` with `Wohnen` and `Küche` was stored in a conversation that the owner has since deleted, and in a new conversation the owner attaches the same blueprint
- **THEN** no room is confirmed and no stored figure is used until the owner answers `yes` to a card that shows `Wohnung`'s stored rooms

#### Scenario: Stored room offered, not assumed
- **WHEN** `Hall` is stored, a new conversation has no confirmed room, and the owner writes "a shoe bench for the hall"
- **THEN** the hall's stored size, ceiling height and openings are shown on a card before any number is proposed, and nothing uses them before `yes`

#### Scenario: Apartment room corrected through a brief
- **WHEN** `Küche` belongs to `Wohnung` and the owner confirms a `record_brief` that corrects the kitchen's ceiling height
- **THEN** `Küche` has the new height and still belongs to `Wohnung`

### Requirement: Deleting a composition version removes its records
When the owner deletes a composition version, the house file SHALL remove, in the same transaction, that version record. If removing the version's folder fails, the records SHALL stay as they were and the delete SHALL be reported as failed.

When the deleted version was the composition's last, the house file SHALL also remove the composition. The measured room or apartment of that scope SHALL stay.

#### Scenario: Records of the deleted version go
- **WHEN** `Wohnen` has versions 1 and 2 and the owner deletes version 1
- **THEN** the house file holds version 2 only, and measured room `Wohnen` is unchanged

#### Scenario: Last version removes the composition
- **WHEN** `Wohnen` has only version 1 and the owner deletes version 1
- **THEN** the house file holds no composition `Wohnen`, and measured room `Wohnen` is unchanged

### Requirement: Deleting a version removes its records
When the owner deletes a piece version, the house file SHALL remove, in the same transaction:
- the version record;
- every review of that version and its items;
- every render run of that version and the feedback on it;
- every pricing of that version.

The render notices in the piece's conversations that name that version SHALL keep their text, but SHALL no longer name the piece or the version, so they show no button. Records of other versions SHALL be unchanged. If removing the version's folder fails, the records SHALL stay as they were and the delete SHALL be reported as failed.

When the deleted version was the piece's last, the house file SHALL also:
- remove the piece;
- clear the piece from every conversation it was bound to (the active piece and the conversation's list of builds).

The conversations themselves and their messages SHALL stay. Generator-extension requests naming the piece SHALL stay.

#### Scenario: Records of the deleted version go
- **WHEN** `hall-bench` version 2 has a review with two items, a rated draft render and a pricing, and the owner deletes version 2
- **THEN** the house file holds no review, item, render run, feedback or pricing for `hall-bench` version 2, and those of version 3 are unchanged

#### Scenario: Notice loses its button
- **WHEN** a conversation holds a "draft turntable of hall-bench version 2 is ready" notice and the owner deletes version 2
- **THEN** the notice is still shown with its text and has no Review button

#### Scenario: Last version unbinds the conversation
- **WHEN** the conversation "Hall bench" is bound to `hall-bench`, which has only version 1, and the owner deletes version 1
- **THEN** the piece is gone, the conversation is still listed with its messages, and its Project panel shows no piece

### Requirement: What the house file saves follows the memory settings
Review results SHALL be saved automatically; confirming a review before it is saved is deferred and no setting offers it. Style and budget preferences in a confirmed brief SHALL be saved (default) or, when the memory settings say so, not saved; the rest of the brief SHALL be saved as before. Generator-extension requests SHALL always be saved; no setting SHALL change this. With the default settings the house file SHALL be written exactly as before this change.

#### Scenario: Preferences not saved
- **WHEN** the memory settings do not save preferences and the owner confirms a brief with style "oak, minimal"
- **THEN** the room and heights are saved and no style preference is written

#### Scenario: Extension requests always saved
- **WHEN** a revision is refused for an unknown field, whatever the memory settings say
- **THEN** a generator-extension request is recorded

### Requirement: A piece reports its conversation
The house file SHALL expose, for each piece, the id of the conversation bound to it when one exists, or none. At most one conversation SHALL be bound to a given piece. The pieces list the owner reads SHALL carry that conversation id so the Studio can open or start the right chat from the Pieces page.

#### Scenario: Bound piece
- **WHEN** a conversation is about `hall-bench`
- **THEN** the pieces list entry for `hall-bench` names that conversation's id

#### Scenario: Piece with no conversation
- **WHEN** `shoe-rack` has never been bound to a conversation
- **THEN** the pieces list entry for `shoe-rack` carries no conversation id

### Requirement: Open review items in the context follow the current version
The open review items placed in a conversation's context SHALL come from the newest review of the piece's current version, which is its approved version when one is approved and otherwise its latest version. Items of a review of any other version SHALL NOT be placed in the context, and each item shown SHALL name the version it is about. When the current version has no review, no review items SHALL be shown. The reviews and their items SHALL NOT be deleted, edited or closed by this, and approving or unapproving a version SHALL change what is shown from the next turn.

#### Scenario: A review of an older version is not shown
- **WHEN** version 1 has a review with an open item expecting a width of 1200 mm, and version 3 is approved with no review
- **THEN** the context carries no review items

#### Scenario: The approved version's review is shown, labelled
- **WHEN** version 3 is approved and its review has one open item
- **THEN** the context lists that item and says it is about version 3, and shows no item of the newer review of version 4 if one exists

#### Scenario: No approved version
- **WHEN** no version is approved and the latest version, 2, has a review with two open items
- **THEN** the context lists those two items, labelled version 2

#### Scenario: Approval changes the next turn
- **WHEN** the owner approves version 1 after version 2 was reviewed
- **THEN** the next turn's context shows version 1's review items and not version 2's

#### Scenario: Nothing is deleted
- **WHEN** an older version's review is no longer shown
- **THEN** it and its items are still stored, with their statuses unchanged

### Requirement: Open version verdicts are in the context
When the memory settings include version verdicts (the default), a conversation's context SHALL list the bound piece's open `mismatch` verdicts, newest first and at most 5, across all of its versions. Each line SHALL name the version and carry the owner's note, neutralised so it cannot carry the untrusted-content delimiter, within the house-file block labelled as the owner's data, and labelled as the owner's verdict that the version does not match what was confirmed. Resolved and dismissed verdicts and `matches` verdicts SHALL NOT be listed. Verdicts of other pieces SHALL NOT be listed. Listing them SHALL NOT change any verdict.

#### Scenario: Designer sees the mistake
- **WHEN** `amesbury-wardrobe` v4 has an open mismatch "the side sections lost their 5 drawers" and the owner asks for a revision
- **THEN** the Designer's context lists that note, labelled version 4 and as the owner's verdict

#### Scenario: Resolved not shown
- **WHEN** v4's mismatch is resolved
- **THEN** the next turn's context lists no verdict for v4

#### Scenario: Setting off
- **WHEN** the developer turns version verdicts off in the memory settings
- **THEN** the next turn's context lists no verdicts, and the verdicts are still stored
