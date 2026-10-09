## MODIFIED Requirements

### Requirement: The Rooms page shows compositions and the model library
The Studio SHALL have a Rooms page for the owner, with three parts.

**Measured rooms.** For each room of the house file the page SHALL show:
- its name, its size (width × depth in millimetres, and the number of corners when it is not four), and its ceiling height;
- its number of openings;
- the apartment it belongs to, or nothing;
- the pieces in it by name, or "No pieces";
- whether it has a composition.

Each room SHALL have a delete action. Choosing it SHALL open a confirm dialog that names the room and what deleting it does:
- the pieces in it, by name, that become "No room";
- the number of conversations that lose their confirmed room;
- its composition and the number of its versions that are removed, with their renders.

Nothing SHALL be deleted until the owner confirms in the dialog. Cancelling SHALL send nothing. After a delete the room, its composition and the pieces' rooms SHALL be shown updated without a reload, on this page and on the Pieces page. A room that belongs to an apartment SHALL show why it cannot be deleted here instead of a working delete action. A refused delete SHALL show its reason next to the room, and the room SHALL stay listed.

**Compositions.** For each composition the page SHALL show:
- its scope, its latest version and that version's build status;
- its items by name and type, with each piece's version and approval state ("no longer approved" shown plainly), or "The room only, no furniture" when it has no items;
- the latest screenshot or still, and a link to the viewer when a turntable exists;
- for the latest built version that has `model.glb`, a 3D view of the composition, loaded only when the owner opens it. It SHALL use the piece inspector's camera controls (free rotate and zoom, Iso, Front, Side and Plan) and its Workshop and Blueprint modes. It SHALL offer one switch per surface of the version's surface map: each wall, the floor, the ceiling and the items, plus "All walls". Switching a surface off SHALL hide exactly the meshes the map lists under it, and a mesh the map does not name stays visible. All surfaces SHALL start switched on, except the ceiling, which starts off so the room can be seen from above. A version without `model.glb` SHALL show its screenshot or still and say that composing the room again adds the 3D view.

**Model library.** The page SHALL show the library with each model's name, stated size and check state (`checking`, `ready`, or `refused` with its reason). It SHALL offer an upload form taking a file, a name and the three dimensions, and a delete action. A refused upload or delete SHALL show its reason next to the form.

The page SHALL NOT show model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Measured room listed
- **WHEN** the house file holds `Hall` with `shoe-bench` in it and no composition
- **THEN** the Rooms page lists `Hall` with its size, ceiling height, openings and `shoe-bench`, and says it has no composition

#### Scenario: Delete warns first
- **WHEN** the owner chooses delete on `Hall`, which holds `shoe-bench`, was confirmed in one conversation and has composition `Hall` with two versions
- **THEN** a dialog names `shoe-bench` as becoming "No room", one conversation losing its confirmed room, and composition `Hall` with two versions removed, and nothing has been deleted

#### Scenario: Delete cancelled
- **WHEN** the owner cancels that dialog
- **THEN** no request is sent and `Hall` is still listed

#### Scenario: Delete confirmed
- **WHEN** the owner confirms that dialog
- **THEN** `Hall` and composition `Hall` are no longer listed without a reload, and the Pieces page shows `shoe-bench` with "No room"

#### Scenario: Room in an apartment
- **WHEN** `Küche` belongs to apartment `Wohnung`
- **THEN** the Rooms page shows that `Küche` cannot be deleted here because it belongs to `Wohnung`

#### Scenario: Delete refused
- **WHEN** the delete route refuses because the room's composition is building
- **THEN** the reason is shown next to the room and the room is still listed

#### Scenario: Empty composition shown
- **WHEN** composition `Hall` v1 has no items and its build succeeded
- **THEN** the Rooms page lists `Hall` with "The room only, no furniture" and its screenshot

#### Scenario: Unapproved piece shown
- **WHEN** a composition places a piece version that has since been unapproved
- **THEN** the Rooms page lists that item with "no longer approved" beside it

#### Scenario: Upload refused
- **WHEN** the owner uploads a `.blend` file
- **THEN** the page shows the refusal reason and the library is unchanged

#### Scenario: Check finishes
- **WHEN** an uploaded model's check finishes while the page is open
- **THEN** its state changes from `checking` to `ready` without a reload

#### Scenario: Room shown in 3D
- **WHEN** composition `Wohnen` v2 has `model.glb` and the owner opens its 3D view
- **THEN** the composition is shown from the Iso camera with switches for each wall, the floor, the ceiling, the items and "All walls", and the ceiling is off

#### Scenario: Wall switched off
- **WHEN** the owner switches wall 2 off
- **THEN** every mesh the surface map lists under wall 2 is hidden and the pieces behind it can be seen, and all other surfaces stay as they were

#### Scenario: Older composition without a model
- **WHEN** composition `Hall` v1 was built before this change and has no `model.glb`
- **THEN** the Rooms page shows its screenshot and says that composing `Hall` again adds the 3D view

## ADDED Requirements

### Requirement: The inspector switches and follows versions
The inspector, both its page and the conversation's split view, SHALL offer a version switcher. The switcher SHALL list every version of the piece with its number and build state, the approved one marked. Choosing a version SHALL show that version and update the URL: the page path, or the split view's `inspect` parameter. While the inspector is open, it SHALL notice within five seconds when a newer version of the piece is created, switch to the newest version, update the URL, and say "Showing version N, the newest". It SHALL then show that version's build state until the build succeeds, and then its model. A version the owner chose that is older than the newest SHALL be left alone until a version newer than the newest one at that time is created.

#### Scenario: Older version chosen
- **WHEN** the owner inspects `murphy-bed` v3 and chooses v1 in the switcher
- **THEN** v1's model and cut list are shown and the URL names version 1

#### Scenario: Revision created while inspecting
- **WHEN** the split view shows `murphy-bed` v3 and the owner confirms a revision that creates v4
- **THEN** within five seconds the split view shows v4's build state, the `inspect` parameter names v4, and once the build succeeds v4's model is shown

### Requirement: The chat can stop a turn and edit the latest message
While a turn runs, the conversation view SHALL show a Stop button in place of Send. Pressing it SHALL stop the turn and show the `stopped` message in plain words, and the composer SHALL take input again. The owner's latest message SHALL offer an Edit action when no turn is running and no confirmation is pending. Edit SHALL put the message's text into the composer. Before it sends, it SHALL say that the message and the replies after it are replaced, and that builds or versions already made stay. Sending SHALL replace the message and run it again. Cancelling SHALL change nothing. Older messages SHALL NOT offer Edit. The view SHALL pass a recorded browser check before it counts as done.

#### Scenario: Stop pressed
- **WHEN** a turn is running and the owner presses Stop
- **THEN** the turn ends, the message and its partial progress are gone from the thread, and the composer is ready

#### Scenario: Latest message edited
- **WHEN** the owner chooses Edit on "make it 60 cm deep", changes it to "make it 45 cm deep" and sends
- **THEN** the thread shows the edited message and its new reply, and the old ones are gone

#### Scenario: Only the latest message
- **WHEN** the thread holds three owner messages
- **THEN** only the third offers Edit

### Requirement: The Pieces page shows each approved version's pricing
On the Pieces page, an approved version SHALL offer a "Pricing" dropdown. It SHALL list the version's stored pricings, newest first, by date, total and whether they are complete. The selected pricing SHALL show:
- its sheets with material and count;
- its cut lines;
- its hardware lines;
- its total in EUR;
- every unpriced part, named, with "Pricing incomplete".

A "Price this version" action SHALL create a new pricing and select it. A refusal SHALL show its reason next to the action. A version that is not approved SHALL say that it must be approved before it can be priced, and SHALL offer no action. The dropdown SHALL NOT show a model name, prompt, token count or a GPU cost. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Priced version
- **WHEN** `bench` v2 is approved and has one complete pricing of 184.20 EUR
- **THEN** its Pricing dropdown lists that pricing and shows its sheets, cuts, hardware and 184.20 EUR

#### Scenario: Incomplete pricing
- **WHEN** a pricing of `bench` v2 has no price for the oak edge banding
- **THEN** the dropdown shows "Pricing incomplete" and names the edge banding

#### Scenario: Price this version
- **WHEN** the owner presses "Price this version" on approved `bench` v2
- **THEN** a new pricing is created, listed first and selected

#### Scenario: Unapproved version
- **WHEN** `bench` v3 is not approved
- **THEN** v3 says it must be approved before it can be priced and offers no action
