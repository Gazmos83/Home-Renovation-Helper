## ADDED Requirements

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
