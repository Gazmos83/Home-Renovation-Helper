# studio-ui Specification

## Purpose

Defines the Studio pages the owner and developer use: conversation tool toggles, and the developer panel's routing, budgets, plugins and usage screens.

## Requirements

### Requirement: Conversations show their tool toggles
The conversation view SHALL show the conversation's toggleable tools by plain name and description with their on/off state in the Tools flyout, letting the owner switch them; tools that cannot be toggled SHALL be shown as always on. No conversation page SHALL show model names, token counts or costs. Starting a conversation and opening an existing one for navigation SHALL happen from the Pieces page as set out in the Pieces conversation requirements; the Conversations list page is not part of the Studio navigation. Delete of a conversation SHALL be offered on the conversation view as set out in "Conversations are deleted from the list".

#### Scenario: Toggle a tool
- **WHEN** the owner opens the Tools flyout and switches off the room check in one conversation
- **THEN** the flyout shows it off for that conversation and the next turn there binds no `room_fit`

#### Scenario: List entry
- **WHEN** a conversation is about `hall-bench` and last had a turn today
- **THEN** the Pieces page conversation link for `hall-bench` opens that conversation

#### Scenario: Start without a title
- **WHEN** the owner clicks "Create A New Piece"
- **THEN** an untitled conversation opens with the composer ready, and after the first reply its heading shows the generated title

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on the open conversation "Listening wall" and confirms
- **THEN** the conversation is gone and the owner is on the Pieces page; when the owner cancels instead, nothing changes

### Requirement: The developer panel has its own pages
The Studio SHALL show the developer pages — models and routing, generation and token restrictions, plugins with invocations, usage per day — on a separate route tree that is reachable only when the developer API answers, and SHALL show an API refusal (a failed probe, an out-of-range value) next to the field it names. Each page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Panel disabled
- **WHEN** the developer panel is disabled
- **THEN** the developer pages are not reachable and no link to them is shown

### Requirement: The Studio is an owner-only single-page app
The Studio SHALL be a client-rendered single-page app served separately from the API, calling it with the session cookie; an unauthenticated visit SHALL show the sign-in page, and a 401 from any call SHALL return the owner to it. The homeowner pages SHALL NOT show model names, prompts, token counts or costs of model calls.

#### Scenario: Not signed in
- **WHEN** the owner opens the price list without a session
- **THEN** the sign-in page is shown and, after signing in, the price list

### Requirement: Prices, snapshots and remnants are tabs of one Pricing Overview page
The Studio SHALL have a Pricing Overview page for the owner at `/pricing` with the page title "Pricing Overview" and three tabs, in this order: "Prices", "Snapshots" and "Remnants". Each tab SHALL have its own address — `/pricing/prices`, `/pricing/snapshots`, `/pricing/remnants` — and opening that address SHALL show the page with that tab chosen. `/pricing`, and a `/pricing/` address naming no known tab, SHALL show the Prices tab. The tabs SHALL be a rail at the screen's left edge below the header, with the same font, icon style, colour scheme and "Hide labels" switch as the conversation page's panel rail: each tab an icon, with its label beside it while labels are shown, the chosen tab highlighted, and the switch at the rail's foot. The label choice SHALL be remembered in the browser and shared with the conversation page's rail; a browser that cannot store it SHALL show the labels hidden. The tabs SHALL be exposed as a vertical tab list with the chosen tab marked selected, and only the chosen tab's content SHALL be shown. The old addresses `/price-list`, `/snapshots` and `/remnants` SHALL open the matching tab. The Studio navigation SHALL show one "Pricing Overview" entry, marked current on every tab, and SHALL NOT show "Price list", "Snapshots" or "Remnants" entries. The page SHALL NOT show model names, prompts, token counts or costs of model calls. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Prices first
- **WHEN** the owner chooses "Pricing Overview" in the navigation
- **THEN** the Pricing Overview page opens with the Prices tab chosen and the price list shown

#### Scenario: Labels shown and hidden
- **WHEN** the owner chooses "Show labels" on the Pricing Overview rail
- **THEN** each tab shows its label beside its icon, and the conversation page's rail shows its labels too until the owner hides them

#### Scenario: Tab chosen
- **WHEN** the owner chooses the Remnants tab
- **THEN** the address is `/pricing/remnants`, the rack is shown, and the price list and snapshots are not

#### Scenario: Tab address reloaded
- **WHEN** the owner reloads `/pricing/snapshots`
- **THEN** the Pricing Overview page opens with the Snapshots tab chosen

#### Scenario: Old address
- **WHEN** the owner opens a bookmark to `/snapshots`
- **THEN** the Pricing Overview page opens with the Snapshots tab chosen

#### Scenario: Navigation
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** it shows "Pricing Overview" and no "Price list", "Snapshots" or "Remnants" entry

### Requirement: The price list is managed from a page
The Prices tab of the Pricing Overview page SHALL list entries with label, key, category, unit, effective price, provenance and, when present, the override and the captured price with its date; filter by category; add a manual entry; edit an entry; set and clear an override with a note; refresh a captured entry and show its outcome; and paste a toom URL to create an entry, showing a refusal or parse failure in plain words.

#### Scenario: Paste a URL
- **WHEN** the owner pastes a toom URL with a key and category and submits
- **THEN** the new entry appears with provenance `captured`, or the page shows why it could not be created

### Requirement: Snapshots, remnants and guideline notes have pages
The Studio SHALL let the owner record a snapshot (optionally prefilling an entry), list and delete snapshots on the Snapshots tab of the Pricing Overview page; list, add and remove remnants on its Remnants tab; and list, add, edit and delete guideline notes with their citation on a page of their own. Every form SHALL show the API's refusal reason next to the field it names.

#### Scenario: Future-dated snapshot
- **WHEN** the owner records a snapshot dated tomorrow
- **THEN** the form shows the refusal next to the date

#### Scenario: Prefilled entry reaches the Prices tab
- **WHEN** the owner records a snapshot that prefills an entry and then chooses the Prices tab
- **THEN** the new entry is listed there without a reload

### Requirement: Each page passes a browser check before it counts as done
Each page SHALL be exercised in a real browser against a running service — create, edit and delete paths and one refusal per form — before its task is marked done, and the check SHALL be recorded with the date and what was exercised.

#### Scenario: Browser pass recorded
- **WHEN** the price-list page is marked done
- **THEN** the change records the browser pass that exercised adding, overriding, refreshing and a refused URL

### Requirement: Approval is shown and set from the Studio
The Studio SHALL show, on the Pieces page for each version and in a conversation's project panel for the bound piece, whether a version is approved, and SHALL let the owner approve a built version and unapprove an approved one there. The control SHALL be offered only for a version whose build succeeded; an API refusal SHALL be shown next to the version it names. After a change the page and the panel SHALL show the new state without a reload. Neither SHALL show a model name, prompt, token count or cost. The approve and unapprove flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approve from the Pieces page
- **WHEN** the owner opens `listening-wall` on the Pieces page and approves version 4
- **THEN** version 4 shows "Approved" and a reload shows the same

#### Scenario: Approval in the project panel
- **WHEN** the conversation is bound to `listening-wall`, version 4 is approved and version 5 is the latest
- **THEN** the project panel shows version 5 as latest and version 4 as approved, with a control to approve version 5 once it is built

#### Scenario: Unapprove
- **WHEN** the owner unapproves version 4 from the panel
- **THEN** the panel and the Pieces page show no approved version

### Requirement: Designs are imported and exported from the Studio
The conversation view SHALL let the owner attach a design file (`.json`) as well as images. An attached design SHALL be shown by its file name, not as a thumbnail. A refusal of the file SHALL be shown in plain words.

The Pieces page SHALL offer:
- a download of the import template, with one line saying to give it to another AI chat and attach the returned file in a conversation;
- for each version, a design download;
- for a built version, a bundle download.

The version downloads SHALL stand on a line of their own, reading "Downloads:" followed by "Design (JSON)" and, for a built version, "Bundle (ZIP)". That line SHALL NOT hold the Inspect button or any other action.

Neither view SHALL show a model name, prompt, token count or cost. The import and export flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Design attached
- **WHEN** the owner picks `wall-unit.json` in a conversation
- **THEN** a chip named `wall-unit.json` is shown and is sent with the next message

#### Scenario: Downloads on the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers the design and the bundle downloads, and version 3 offers only the design

#### Scenario: Downloads on their own line
- **WHEN** the owner shows a built version 2 on the Pieces page
- **THEN** a line reads "Downloads: Design (JSON) · Bundle (ZIP)", and "Inspect version 2" is not on that line

#### Scenario: Template offered
- **WHEN** the owner opens the Pieces page
- **THEN** a link downloads the import template, with the line on how to use it

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

**Compositions.** For each composition the page SHALL offer a version dropdown listing its newest five versions, newest first, with the latest chosen. Older versions SHALL be kept and SHALL NOT be listed. Everything below SHALL show the chosen version. For the chosen version the page SHALL show:
- its scope, its version number and that version's build status;
- its items by name and type, with each piece's version and approval state ("no longer approved" shown plainly), or "The room only, no furniture" when it has no items;
- its screenshot or still, and a link to the viewer when a turntable exists;
- when the version has `model.glb`, a 3D view of the composition, loaded only when the owner opens it; choosing another version in the dropdown SHALL show that version in the open view. It SHALL use the piece inspector's camera controls (free rotate and zoom, Iso, Front, Side and Plan) and its Workshop and Blueprint modes. It SHALL offer one switch per surface of the version's surface map: each wall, the floor, the ceiling and the items, plus "All walls". Switching a surface off SHALL hide exactly the meshes the map lists under it, and a mesh the map does not name stays visible. All surfaces SHALL start switched on, except the ceiling, which starts off so the room can be seen from above. The view SHALL offer a "dimensions" switch, off at first. Switched on, it SHALL label every unique wall of the version's room plan with its length in millimetres, on that wall (a wall two rooms of an apartment share is labelled once), and each room's ceiling height in millimetres once per room (so an apartment whose rooms differ shows each height). The figures SHALL be the chosen version's own. A version without `model.glb` SHALL show its screenshot or still and say that composing the room again adds the 3D view.

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

#### Scenario: Newest five versions offered
- **WHEN** composition `Wohnen` has versions 1 to 7
- **THEN** its version dropdown lists versions 7, 6, 5, 4 and 3, version 7 is shown, and versions 1 and 2 are still kept

#### Scenario: Older version chosen
- **WHEN** the owner chooses version 5 of `Wohnen` in the dropdown while its 3D view is open
- **THEN** the card shows version 5's status, items and picture, and the 3D view shows version 5's model

#### Scenario: Wall and ceiling dimensions
- **WHEN** the owner switches dimensions on in the 3D view of a five-walled room `Wohnen` with a 2500 mm ceiling
- **THEN** each of the five walls is labelled with its own length in mm and the ceiling height reads 2500 mm once

#### Scenario: Apartment heights differ
- **WHEN** the owner switches dimensions on in the 3D view of an apartment whose `Bad` is 2400 mm high and whose other rooms are 2550 mm, with one wall shared by `Bad` and `Flur`
- **THEN** `Bad` shows 2400 mm, each other room shows 2550 mm, and the shared wall carries one length label

### Requirement: The conversation view is the homeowner's chat
The conversation view SHALL show the owner's messages and the replies in order as chat bubbles: replies aligned to the left, the owner's messages to the right, and forms, confirmations and question sets centred. Reply text SHALL be set in Commissioner and headings and speaker names in Oswald, served with the app, with a line height of at least 1.6 and space between paragraphs. A reply SHALL be rendered as formatted text — headings, bullet and numbered lists, tables, emphasis, inline code — with raw HTML shown as text and never rendered, and an image shown only when it points at one of the app's own routes. A fenced block marked `calc` SHALL be shown in a framed box set apart from the reply's text. A file route of a piece, a composition or an apartment shell in a reply, written bare or as a link, SHALL be shown as a link that opens in a new tab; no other address in a reply SHALL be linked. A composer SHALL send one message as one turn, and the turn's refusal SHALL be shown in words next to the composer when the service refuses it. While a turn is running the composer SHALL be disabled and a waiting bubble SHALL stand in the reply position: left-aligned, rounded, with a 2 px border and animated dots, naming the specialist currently working ("Designer is working…") and updating as the turn moves on, or "The Foreman is working…" before a specialist is chosen. Under each reply the specialists that ran in that turn SHALL be listed by role name only. A reply's title event SHALL update the heading without a reload. The heading SHALL be editable in place; saving sends the new title and an empty title is refused in words.

#### Scenario: Send and read
- **WHEN** the owner types "I want a bench for the hall" and sends it
- **THEN** the message appears at once on the right, the composer is disabled, a waiting bubble on the left names the Foreman and then Intake, and the reply replaces it on the left with "Intake" listed under it

#### Scenario: Refused turn
- **WHEN** the service answers the turn with 503 and the memory reason
- **THEN** the reason is shown next to the composer, the waiting bubble is gone and the owner's message is not kept in the list

#### Scenario: Table in a reply
- **WHEN** a reply contains a Markdown table of five cut-list rows
- **THEN** it is shown as a table with a header row and five rows, not as text with `|` characters

#### Scenario: Calculation box
- **WHEN** a reply contains a `calc` block "430 + 430 + 400 + 100 + 100 = 1460"
- **THEN** the calculation is shown in a framed box between the paragraphs around it

#### Scenario: HTML in a reply
- **WHEN** a reply contains `<img src=x onerror=alert(1)>`
- **THEN** the text is shown literally and no element is created from it

#### Scenario: Render route in a reply
- **WHEN** a reply says the turntable "will be at /packages/hall-bench/versions/1/files/viewer.html."
- **THEN** that route is a link opening in a new tab, without the full stop, and an `https://` address in a reply stays plain text

#### Scenario: Rename in place
- **WHEN** the owner edits the heading to "Listening wall" and saves
- **THEN** the heading and the conversation list show "Listening wall"

### Requirement: A pending confirmation is answered in the view
When a reply carries a pending confirmation the view SHALL show it as a card with its subject, summary and proposal, a **Yes** and a **No** button and an optional reason, and SHALL hide the composer until it is answered. Answering SHALL send the owner's answer on the thread and show the reply that follows. Reopening a conversation with a confirmation still pending SHALL show the card again.

#### Scenario: Yes
- **WHEN** the Designer proposes a revision and the owner clicks Yes
- **THEN** the view shows the reply that reports the new version and the composer returns

#### Scenario: No with a reason
- **WHEN** the owner clicks No with "make it 4 shelves"
- **THEN** the reason is sent with the answer and the next reply is shown

#### Scenario: Reopened while pending
- **WHEN** the owner reloads a conversation that has a pending brief confirmation
- **THEN** the card is shown and the composer is hidden

### Requirement: Plans and photos are attached from the view
The conversation view SHALL let the owner add PNG or JPEG images and text notes to the conversation and attach them to the next message; attached images SHALL be shown as thumbnails and notes as their file name, on the composer and in the sent message, and a refused upload (type, size, count) SHALL be reported in the service's words. Each attachment on the composer SHALL have a remove control that takes it off the next message before sending.

#### Scenario: Attach a blueprint
- **WHEN** the owner adds `blueprint.jpeg` and sends "This is my flat"
- **THEN** the turn carries the upload and the sent message shows the thumbnail

#### Scenario: Too large
- **WHEN** the owner adds an image over the configured size
- **THEN** the refusal's reason is shown and nothing is attached

#### Scenario: Removed before sending
- **WHEN** the owner attaches `blueprint.jpeg` and `notes.md`, removes `blueprint.jpeg` and sends
- **THEN** the turn carries only the note's upload id and the sent message shows only `notes.md`

### Requirement: The conversation view shows the project's progress
The conversation view SHALL show a project panel with the bound piece, its latest version and build state, the progress steps (brief confirmed, piece created, built, draft or preview rendered, reviewed with open items, detail pass, final) each marked done or not, the next step the owner can ask for, the latest still when one exists and otherwise the screenshot, and the piece's open generator-extension requests. The panel SHALL NOT offer a link to a turntable viewer. The panel SHALL refresh while a build is queued or running, while a render of the latest version is queued or running, and after every turn. It SHALL show nothing when the service's progress read is refused other than the refusal's reason.

#### Scenario: After the first build
- **WHEN** the Builder's build of version 1 finishes while the view is open
- **THEN** the panel shows version 1 built with its screenshot, "built" done, and the next step as a draft render, without a reload

#### Scenario: Open review items
- **WHEN** the latest review of the piece has two open items
- **THEN** the panel shows "reviewed, 2 open" and links to the piece's page

#### Scenario: Turntable finished
- **WHEN** the draft turntable of version 1 finishes while the view is open
- **THEN** the panel shows the still and "draft" rendered without a reload, and shows no "Open the turntable viewer" link

### Requirement: A piece version can be inspected in 3D
The Studio SHALL have an owner-only page per piece version at `/pieces/<package-id>/versions/<n>`. For a built version it SHALL show the version's `model.glb` in a 3D view, with:
- **Camera:** free rotate and zoom with the mouse, and buttons for the Iso, Front, Side and Plan cameras.
- **Modes:** Workshop (lit), Blueprint (flat light with the parts' edges drawn) and Exploded. Exploded has a slider that moves each module away from the piece's centre, with its parts following. The direction comes from the module positions in the version's `spec.json`.
- **Layer switches:** one for each layer the version's `spec.json` names, plus `dimensions`. Switching a layer off hides exactly the meshes the layer map lists under it. A mesh the map does not name stays visible.
- **Overall dimensions:** W, H and D in mm from `spec.json` `overall`, drawn beside the model. Hidden in Exploded mode and when `dimensions` is off.
- **Scale:** a floor grid and a contact shadow.
- **Straight-on views:** `front.png`, `side.png` and `top.png`, when the version has them.

A Cut list tab SHALL show the version's parts (id, name, quantity, length, width, thickness, material, grain, banding, notes, module) and its hardware (id, item, quantity, notes), both read from `spec.json`. When the parts belong to more than one module, the tab SHALL offer a filter with "All" and one choice per module, in the order the parts first name them. Each module is labelled by its name from `spec.json` `module_names`, "Extra parts" for `extras`, and otherwise its id. Choosing a module SHALL show only that module's parts, with their count of rows and pieces. The parts table SHALL name each part's module by that same label. Hardware is not divided by module.

Every measurement on the page SHALL come from the version's own files. The 3D view SHALL be loaded only on this page and in a conversation's split view, and only once one of them is shown. The split view SHALL show the same inspector with the same controls and tabs.

A version that is not built SHALL show its build state instead of the 3D view. A version, or a file it lacks, SHALL be named in plain words rather than shown as an error code. The page SHALL NOT show a model name, prompt, token count or cost, and it SHALL pass a recorded browser check before it counts as done.

#### Scenario: Built version inspected
- **WHEN** the owner opens `/pieces/murphy-bed/versions/1`
- **THEN** the model is shown from the Iso camera with W 3000 mm, H 2900 mm and D 450 mm beside it, and the layer switches carcass, backs, shelves, fronts, extras and dimensions

#### Scenario: Front camera
- **WHEN** the owner presses Front
- **THEN** the view looks straight at the piece's front

#### Scenario: Exploded
- **WHEN** the owner chooses Exploded and moves the slider to its end
- **THEN** each module moves away from the centre along its own direction, and the dimension overlay is hidden

#### Scenario: Layer off
- **WHEN** the owner switches `fronts` off
- **THEN** every mesh the layer map lists under `fronts` is hidden and all others stay visible

#### Scenario: Cut list
- **WHEN** the owner opens the Cut list tab
- **THEN** every row of `spec.json` `parts` and `hardware` is listed with its figures

#### Scenario: Cut list filtered by module
- **WHEN** the owner opens the Cut list of `murphy-bed` version 2 and chooses "Left lower cabinet"
- **THEN** only the parts of module `left-base` are listed, with their row and piece counts, and choosing "All" lists every part again

#### Scenario: Version built before the views
- **WHEN** the owner inspects a version that has no `front.png`
- **THEN** the 3D view, the overlay and the cut list are shown and the straight-on views are left out

#### Scenario: Not built yet
- **WHEN** the owner opens a version whose build is running
- **THEN** the page says the version is building and shows no 3D view

#### Scenario: Conversation without the split view
- **WHEN** the owner opens a conversation and does not open the inspector
- **THEN** the 3D view is not loaded

### Requirement: The inspector is reachable from the Pieces page and the conversation
The Pieces page SHALL offer an "Inspect version N" button for the version shown once it is built, opening the inspector page for that version. It SHALL be a framed button with rounded corners in the Studio's button style, not a text link, and SHALL stand with the approval control, apart from the downloads. A conversation's project panel SHALL offer an "Inspect version N" button for the bound piece's latest version once it is built, in the same style. It SHALL open the inspector for that version in the conversation's split view. A render notice's Review button SHALL open the same split view.

#### Scenario: Inspect from the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers an "Inspect version 2" button and version 3 does not

#### Scenario: Inspect button opens the inspector
- **WHEN** the owner presses "Inspect version 2" on the Pieces page
- **THEN** the inspector page for version 2 is shown

#### Scenario: Inspect from the conversation
- **WHEN** the bound piece's version 1 has just been built
- **THEN** the panel shows an "Inspect version 1" button, and pressing it shows the inspector for version 1 beside the chat

### Requirement: Conversations are deleted from the list
The conversation view SHALL offer a delete action. It asks for confirmation, naming the conversation and stating that its pieces and renders are kept and that the conversation cannot be restored. A confirmed delete SHALL remove the conversation and return the owner to the Pieces page; a cancel changes nothing. A refusal (a reply still being written, or memory unavailable) SHALL be shown in words on the conversation view, which stays open. The delete flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on the open conversation "Hall shoe bench" and confirms
- **THEN** the conversation is gone, the owner is on the Pieces page, and the piece is still listed there

#### Scenario: Cancel
- **WHEN** the owner chooses delete and then cancels
- **THEN** nothing is sent and the conversation stays open

#### Scenario: Refused while a reply is written
- **WHEN** the owner confirms a delete while that conversation's turn is running
- **THEN** the conversation stays open and the refusal is shown on the view

### Requirement: The Pieces page shows renders and takes feedback
The Studio SHALL show the owner a Pieces page that lists the pieces, then each piece's versions, then each version's published renders, showing for each:
- its kind and tier;
- a preview image (the still, or the first frame);
- its current rating and comment, with controls to rate up, rate down, edit the comment and clear.

The page SHALL NOT offer a link to a render's viewer. The page SHALL show an API refusal next to the render it names. It SHALL NOT show model names, prompts, token counts or costs. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Rate a turntable
- **WHEN** the owner opens `hall-bench` v2 on the Pieces page and rates the `draft` turntable down with "too dark"
- **THEN** the page shows the down rating and the comment, and a reload shows the same

#### Scenario: No internals
- **WHEN** the Pieces page shows a render the Builder started
- **THEN** no model slug, prompt text or token figure appears on the page

#### Scenario: No viewer link
- **WHEN** a version has a published draft turntable
- **THEN** its render entry shows the preview image and the rating controls, and no "Open the turntable viewer" link

### Requirement: The developer panel shows feedback
The developer route tree SHALL include a Feedback page listing the per slot, model and tier rating counts, and the comments of a selected group. Like the other developer pages, it SHALL be reachable only when the developer API answers, and SHALL pass a recorded browser check before it counts as done.

#### Scenario: Feedback page
- **WHEN** the developer opens the Feedback page after ratings exist
- **THEN** each slot and model row shows its up and down counts per tier, and selecting a row lists its comments newest first

### Requirement: The developer panel has an Offload page
The developer route tree SHALL include an Offload page showing the configuration summary, a connection-test button with its result, the remote benchmark with its last value and time, the final-target switch, the hourly rate, and the recent remote jobs. Like the other developer pages, it SHALL be reachable only when the developer API answers, SHALL show an API refusal next to the field it names, and SHALL pass a recorded browser check before it counts as done. No homeowner page SHALL show the host, the target setting or a euro figure.

#### Scenario: Target refused on the page
- **WHEN** the developer switches finals to `remote` while offload is not configured
- **THEN** the page shows the refusal next to the target switch and the switch stays on `local`

### Requirement: Tools and Project open from a rail
The conversation view SHALL show a narrow rail with a Tools icon and a Project icon, each with an accessible name. The rail SHALL sit at the left edge of the screen, below the header, outside the centred page, and SHALL stay visible while the page scrolls. The rail SHALL have an expand control: expanded, each icon is shown with its label ("Tools", "Project"); collapsed, only the icons are shown. The control SHALL say which it does and whether the rail is expanded. Choosing an icon SHALL open its panel as a flyout beside the rail, over the chat; choosing it again, choosing the other, pressing Escape or closing the flyout SHALL close or switch it. The chat SHALL use the full width beside the rail when no flyout is open. The Project flyout SHALL carry the project panel unchanged, including its refresh while a build or render is queued or running.

#### Scenario: Open and close
- **WHEN** the owner clicks the Project icon and then presses Escape
- **THEN** the project panel opens over the chat and then closes, and the messages were not reflowed

#### Scenario: Switch
- **WHEN** the Tools flyout is open and the owner clicks the Project icon
- **THEN** the Tools flyout closes and the project panel opens

#### Scenario: Scrolled conversation
- **WHEN** the owner scrolls a long conversation to its end
- **THEN** the rail is still shown at the left edge of the screen and its icons still open their panels

#### Scenario: Expanded
- **WHEN** the owner presses the expand control
- **THEN** the rail shows "Tools" and "Project" beside their icons; pressing it again shows the icons only

### Requirement: Questions are answered one at a time
When a reply carries a pending question set the view SHALL show it centred in place of the composer, one question at a time with its unit and, when given, its choices as buttons (a free answer remains possible). The next question SHALL appear only after the current one has an answer; the owner SHALL be able to go back to an earlier question before sending. After the last answer the owner sends all answers in one step. A "Answer in my own words" action SHALL decline the set with a message instead. Answered sets SHALL be shown in the conversation as a table with a Question and an Answer column.

#### Scenario: Two questions
- **WHEN** Intake asks "Ceiling height?" (mm) and "Budget?" (EUR)
- **THEN** only the first is shown; after the owner enters 2500 the second appears; after 900 the owner sends, and the conversation shows a Question | Answer table with both rows

#### Scenario: Choice
- **WHEN** a question offers the choices "oak" and "birch"
- **THEN** both are shown as buttons and choosing one answers the question

#### Scenario: Reopened while pending
- **WHEN** the owner reloads a conversation with a question set pending
- **THEN** the form is shown again from its first question and the composer is hidden

### Requirement: A help page explains how to prepare a blueprint
The Studio SHALL have a help page, linked from the navigation, that explains how to prepare a blueprint or a hand sketch for Intake and lists the measurements Intake needs: each room's name; the length of every wall, edge by edge in one direction around the room; every corner angle that is not 90°; the ceiling height; the wall thickness; every door and window with the wall it is on, its offset from that wall's starting corner, its width, its height and (for a window) its sill height; a scale reference (a dimension line, a printed area or a known door width); and that all rooms of one apartment are drawn in one plan frame. It SHALL say which file types the conversation accepts.

#### Scenario: Help reached
- **WHEN** the owner opens Help from the navigation
- **THEN** the page lists the measurements above and says plans and photos are PNG or JPEG and notes are Markdown or plain text

### Requirement: Page headings use Oswald on every page
Every Studio page, homeowner and developer alike, SHALL set its headings in Oswald, served with the app and never fetched from a third-party host. Body text outside the conversation view SHALL keep its current font.

#### Scenario: Heading on a page outside the chat
- **WHEN** the owner opens the Pieces page, or the developer opens a page under `/admin`
- **THEN** the page's headings are set in Oswald and no font is requested from a third-party host

### Requirement: The developer sees one conversation's model calls
The developer pages SHALL include, for a chosen conversation, the list of its model calls — time, specialist, model slug, input and output tokens — newest first, reachable only through the developer route tree. No homeowner page SHALL link to it.

#### Scenario: Calls of a turn
- **WHEN** the developer opens the calls of a conversation whose last turn went Foreman → Designer
- **THEN** both calls are listed with their slots, model slugs and token figures

### Requirement: The Pieces page shows and sets each piece's room
The Pieces page SHALL show each piece's room, or "No room" for an unassigned piece, and a room selector listing the house file's rooms and "No room". Choosing an entry SHALL set or clear the piece's room through the owner's room route and show the new room without a reload. An API refusal SHALL be shown next to the piece it names. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Attach an unassigned piece
- **WHEN** the owner opens the Pieces page, `murphy-bed` shows "No room", and the owner chooses `Schlafzimmer`
- **THEN** the page shows `murphy-bed` in `Schlafzimmer`, and a reload shows the same

#### Scenario: Refusal shown
- **WHEN** the room route refuses the change
- **THEN** the refusal is shown next to that piece and its room is unchanged

### Requirement: The Studio header stays at the top
The Studio's top header, with its navigation, SHALL stay at the top of the screen while any page scrolls, and SHALL not cover the content below it when the page is scrolled to its top.

#### Scenario: Long page
- **WHEN** the owner scrolls a long conversation down
- **THEN** the header and its links stay visible at the top of the screen

### Requirement: A render notice is shown in the conversation
The conversation view SHALL show each notice in the thread's history in its place among the messages, centred and framed like a confirmation, with its text. A finished render of a piece version SHALL show a Review button that names the render's tier: "Review <tier> v1" when the version is 1, and "Review <tier> revision <n>" for version n above 1, where the tier is `draft`, `preview` or `final`. Pressing it SHALL open the inspector for that piece version in the split view. A failed render's notice, and a notice for a shell or composition, SHALL show no button. A notice posted while the view is open SHALL appear without a reload while the project panel is following a render. A notice SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: First draft ready
- **WHEN** the draft turntable of `hall-bench` version 1 finishes while the conversation is open
- **THEN** a notice appears without a reload, saying it is ready and can also be checked in the Project panel, with a "Review draft v1" button

#### Scenario: Later version
- **WHEN** a notice is shown for a finished draft render of `hall-bench` version 3
- **THEN** its button reads "Review draft revision 3"

#### Scenario: Preview and final
- **WHEN** notices are shown for a finished preview of `hall-bench` version 1 and a finished final of version 4
- **THEN** their buttons read "Review preview v1" and "Review final revision 4"

#### Scenario: Failed render
- **WHEN** a preview turntable of `hall-bench` version 2 fails
- **THEN** a notice says it did not finish and shows no button

### Requirement: A piece version is reviewed beside the conversation
The conversation view SHALL be able to show the inspector for one piece version beside the chat: on a wide screen the chat on one side and the inspector on the other, both visible at once; on a narrow screen the inspector below the chat. The conversation route SHALL use the full width of the screen for this. While the inspector is shown the owner SHALL still be able to read, scroll and send messages, and opening the inspector SHALL NOT start a turn. The inspector SHALL have a control to close it, after which the chat takes the width again. Opening another version SHALL replace the shown one. The open inspector SHALL be part of the page's address, so a reload shows it again. A version that is not built, or a file it lacks, SHALL be named in plain words as on the inspector page.

#### Scenario: Review from a notice
- **WHEN** the owner presses "Review draft v1" on a notice for `hall-bench` version 1
- **THEN** the inspector for `hall-bench` version 1 is shown beside the chat and the composer is still usable

#### Scenario: Ask about a detail
- **WHEN** the inspector is open and the owner sends "the left shelf looks too thin"
- **THEN** the message is sent as a normal turn and the inspector stays open

#### Scenario: Close
- **WHEN** the owner closes the inspector
- **THEN** the chat takes the full width beside the rail again

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the inspector shows `hall-bench` version 2
- **THEN** the conversation and the inspector for version 2 are shown again

### Requirement: Hardware data sheets are managed on the guidelines page
The guidelines page SHALL have a Hardware data section. In it the owner can list, add, edit and delete data sheets, with each sheet's key, kind, maker, model, values and source. A value left empty SHALL be shown as missing, never as zero. Each measured value SHALL be entered as one number or as a minimum and maximum, and a range SHALL be shown as a range. Every form SHALL show the API's refusal reason next to the field it names. The section SHALL pass a recorded browser check before it counts as done.

#### Scenario: Data sheet added
- **WHEN** the owner adds a hinge data sheet with a toom page and two of its values
- **THEN** the list shows the sheet with its source, the two values, and the other values as missing

#### Scenario: Refused source
- **WHEN** the owner gives a `toom` source on another host
- **THEN** the form shows the refusal next to the page URL

### Requirement: The Cut list tab shows the drilling list
The inspector's Cut list tab SHALL show the version's drilling list from `spec.json` `drilling`:
- each part's positions, with the values and sources used; an exact position as its value, a ranged one as its range, and one given as a rule as its words;
- the drilling-work counts.

When the list is incomplete, the tab SHALL show a banner, above the tables, that names every missing value. A version with no `drilling` SHALL say that drilling was not calculated for it. The tab SHALL pass a recorded browser check before it counts as done.

#### Scenario: Drilling shown
- **WHEN** the owner opens the Cut list of a version with adjustable shelves and complete data
- **THEN** the drilling table lists the side rows' hole heights and setbacks with their sources, and no banner is shown

#### Scenario: Ranged bracket ends shown
- **WHEN** the owner opens the Cut list of a version with a 1500 mm wall shelf and calculated brackets
- **THEN** the drilling table shows the outer brackets as "100–200 mm from each end" and the middle one as "evenly spaced between them", and no banner is shown

#### Scenario: Incomplete banner
- **WHEN** the owner opens the Cut list of a version whose hinge data sheet lacks the cup edge distance
- **THEN** a banner says the drilling list is incomplete and names "cup edge distance"

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

### Requirement: A version is deleted from the Pieces page and the Project panel after "Are you sure?"
The Pieces page SHALL offer "Delete version N" for the version shown. The Project panel SHALL offer "Delete version N" for the latest version. Neither SHALL offer it for an approved version.

Pressing it SHALL NOT delete anything yet. It SHALL show, in place, "Are you sure? Version N and its renders, reviews and pricings will be deleted. This cannot be undone." with "Yes, delete version N" and "Cancel" buttons. When N is the piece's only version, the question SHALL say that the whole piece will be deleted.

Only "Yes" SHALL send the delete. Afterwards:
- the Pieces page SHALL show the piece's remaining versions, or drop the piece when it has none left;
- the Project panel SHALL refresh;
- an inspector showing the deleted version SHALL close.

A refusal SHALL be shown with its reason next to the control. The Project panel SHALL show "N of 15 versions" once the piece holds 13 or more.

#### Scenario: Confirmed delete on the Pieces page
- **WHEN** the owner shows `hall-bench` version 2, presses "Delete version 2", then "Yes, delete version 2"
- **THEN** version 2 is no longer in the piece's version dropdown and the page shows another version

#### Scenario: Cancelled
- **WHEN** the owner presses "Delete version 2" and then "Cancel"
- **THEN** nothing is deleted and the delete control is shown again

#### Scenario: Approved version has no delete
- **WHEN** the owner shows `hall-bench` version 4, which is approved
- **THEN** no "Delete version 4" control is shown

#### Scenario: Refusal shown
- **WHEN** the owner confirms deleting a version that a composition places
- **THEN** the refusal naming the composition is shown next to the control and the version stays listed

#### Scenario: Near the limit
- **WHEN** the conversation's piece holds 14 versions
- **THEN** the Project panel shows "14 of 15 versions"

### Requirement: Piece titles do not carry the version
The Project panel's header line SHALL show the piece's name, its id and its build state, without "version N". The heading of the inspector beside the chat SHALL show the piece's name, or its id when the name cannot be read, without the version. Its version buttons already show which version is open. Lines and buttons that act on one version SHALL keep its number, such as "Approve version 14", "Inspect version 14" and "Delete version 14".

#### Scenario: Project panel header
- **WHEN** the conversation's piece is `listening-wall`, named "Listening wall", at version 14
- **THEN** the panel's header reads "Listening wall" with the id `listening-wall` and contains no "version 14"

#### Scenario: Inspector heading
- **WHEN** the inspector beside the chat shows `listening-wall` version 14
- **THEN** its heading reads "Listening wall" and the version buttons mark version 14 as shown

### Requirement: A build notice is shown with an Inspect button
The conversation view SHALL show each build notice in its place among the messages, framed like a render notice. A finished build's notice SHALL show an "Inspect version N" button that opens the inspector for that piece version beside the chat. A failed build's notice, and a notice whose version was deleted, SHALL show no button. A build notice posted while the view is open SHALL appear without a reload while the Project panel is following a build. It SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: Built while open
- **WHEN** `hall-bench` version 2 finishes building while its conversation is open
- **THEN** a notice saying version 2 is built appears without a reload, with an "Inspect version 2" button

#### Scenario: Inspect from the notice
- **WHEN** the owner presses "Inspect version 2" on that notice
- **THEN** the inspector for `hall-bench` version 2 is shown beside the chat and the composer is still usable

#### Scenario: Failed build
- **WHEN** the build of `hall-bench` version 3 fails
- **THEN** its notice says it did not build and shows no button

### Requirement: The exploded view labels each module's size
In Exploded mode, the inspector SHALL show one label per module that `spec.json` `modules` names. Each label SHALL give the module's name from `module_names`, or its id when it has no name, and its width × height × depth in mm, for example "Left lower cabinet 600 × 720 × 560 mm". The figures SHALL come from the version's own `spec.json`. Each label SHALL sit at its module and move with it as the explode slider moves. The labels SHALL follow the `dimensions` layer switch. The overall dimensions SHALL stay hidden in Exploded mode. A version whose `spec.json` has no `modules` SHALL show no labels and SHALL NOT show an error.

#### Scenario: Labels when exploded
- **WHEN** the owner inspects `murphy-bed` version 2 and chooses Exploded
- **THEN** every module shows a label with its name and W × H × D in mm, and the overall dimensions are hidden

#### Scenario: Labels follow the slider
- **WHEN** the owner moves the explode slider
- **THEN** each label moves with its module

#### Scenario: Dimensions off
- **WHEN** the owner switches `dimensions` off in Exploded mode
- **THEN** no module labels are shown

#### Scenario: Not exploded
- **WHEN** the owner chooses Workshop
- **THEN** no module labels are shown and the overall dimensions are drawn as before

### Requirement: The Pieces page lists a piece's versions in a dropdown
The Pieces page SHALL show a piece's versions in one dropdown, not as a row of buttons, newest first. Each entry SHALL read "Version N", followed by the version's state when it has one:
- "(approved)" for the approved version;
- "(failed)" for a version whose build failed;
- "(building)" for a version whose build is queued or running.

A built version that is not approved SHALL show no state. The page SHALL open each piece on its newest version. Choosing an entry SHALL show that version's approval, Inspect button, downloads, pricing, delete control and renders, without a reload. After the version shown is deleted, the dropdown SHALL show the newest version left.

#### Scenario: Entries with their state
- **WHEN** `listening-wall` has versions 11 to 14, version 14 is approved, version 12 failed and version 13 is built
- **THEN** the dropdown lists "Version 14 (approved)", "Version 13", "Version 12 (failed)" and "Version 11", in that order

#### Scenario: Opens on the newest
- **WHEN** the owner opens the Pieces page and `listening-wall`'s newest version is 14
- **THEN** the dropdown shows "Version 14" and the card shows version 14

#### Scenario: Choose another version
- **WHEN** the owner chooses "Version 11" in the dropdown
- **THEN** the card shows version 11's approval, downloads and renders without a reload

#### Scenario: Building
- **WHEN** version 15 of `listening-wall` is still building
- **THEN** its entry reads "Version 15 (building)"

### Requirement: Each piece card shows a picture of the piece
At the top of each piece card, the Pieces page SHALL show the build screenshot of one version:
- the approved version, when it has a screenshot;
- otherwise the newest version that has a screenshot.

A caption under the picture SHALL name the version, followed by "(approved)" when it is the approved one, e.g. "Version 14 (approved)". The picture SHALL NOT follow the dropdown. It SHALL be the build screenshot only, never a render. A piece with no screenshot in any version SHALL show no picture and no error. After an approval changes or a version is deleted, the picture SHALL show the version these rules now choose, without a reload.

#### Scenario: Approved version shown
- **WHEN** `listening-wall` has versions 1 to 14, all built, and version 9 is approved
- **THEN** the card shows version 9's screenshot captioned "Version 9 (approved)", whichever version the dropdown shows

#### Scenario: None approved
- **WHEN** no version of `murphy-bed` is approved and versions 1 to 4 are built
- **THEN** the card shows version 4's screenshot captioned "Version 4"

#### Scenario: Newest has not built
- **WHEN** no version of `murphy-bed` is approved, version 5 failed and version 4 is built
- **THEN** the card shows version 4's screenshot captioned "Version 4"

#### Scenario: No screenshot at all
- **WHEN** `hall-bench` has only version 1 and it is still building
- **THEN** the card shows no picture and no error

#### Scenario: Render not used
- **WHEN** the approved version has a rendered still and a build screenshot
- **THEN** the card shows the build screenshot

### Requirement: The conversation's messages scroll in their own box and open at the last message
The conversation view SHALL show the messages in a box that takes the window height left under the header and the title, with its own scroll bar. The composer, a pending confirmation card or a question form SHALL stay visible below the box without scrolling the page. When the inspector is open beside the chat, the same SHALL hold for the chat column.

Opening a conversation SHALL show the last message, scrolled to the bottom of the box. When a message, a reply, a notice or the waiting bubble is added:
- the box SHALL scroll to the bottom when the owner was already at the bottom;
- the box SHALL stay where it is when the owner had scrolled up.

Sending a message, or answering a confirmation or question form, SHALL always scroll the box to the bottom. An empty conversation SHALL show its "Nothing said yet" line in the box.

#### Scenario: Opens at the last message
- **WHEN** the owner opens a conversation with 60 messages
- **THEN** the last message is visible at the bottom of the box, the box has a scroll bar, and the composer is visible below it

#### Scenario: Follows while at the bottom
- **WHEN** the owner is at the bottom of the box and a reply arrives
- **THEN** the box scrolls so the reply is visible

#### Scenario: Stays while reading older messages
- **WHEN** the owner has scrolled up to read an older message and a build notice arrives
- **THEN** the box stays at the message the owner is reading

#### Scenario: Sending jumps to the bottom
- **WHEN** the owner has scrolled up and sends a message
- **THEN** the box scrolls to the bottom and shows the message and the waiting bubble

### Requirement: Room-version approval is shown and set from the Studio
The Studio SHALL show, on the Rooms page for the chosen composition version and in a conversation's Project panel for the confirmed room's composition, whether a version is approved, and SHALL let the owner approve a built version and unapprove an approved one there. The control SHALL be offered only for a version whose build succeeded; an API refusal SHALL be shown next to the version it names. After a change the page and the panel SHALL show the new state without a reload. Neither SHALL show a model name, prompt, token count or cost. The approve and unapprove flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approve from the Rooms page
- **WHEN** the owner opens composition `Wohnen` on the Rooms page, chooses version 2, and approves it
- **THEN** version 2 shows "Approved" and a reload shows the same

#### Scenario: Approval in the project panel
- **WHEN** the conversation's confirmed room is `Hall`, version 1 is approved and version 2 is the latest built version
- **THEN** the Project panel shows version 2 as latest and version 1 as approved, with a control to approve version 2

#### Scenario: Unapprove
- **WHEN** the owner unapproves `Wohnen` version 2 from the Rooms page
- **THEN** the page and the Project panel show no approved version of `Wohnen`

#### Scenario: Unapprove of a placed piece is explained
- **WHEN** the owner unapproves `listening-wall` v4 from the Pieces page or the Project panel while approved `Wohnen` version 2 places it
- **THEN** the refusal naming `Wohnen` version 2 is shown next to the control and v4 stays approved

### Requirement: A composition version is deleted from the Rooms page and the Project panel after "Are you sure?"
The Rooms page SHALL offer "Delete version N" for the version shown. The Project panel SHALL offer "Delete version N" for the latest composition version. Neither SHALL offer it for an approved version.

Pressing it SHALL NOT delete anything yet. It SHALL show, in place, "Are you sure? Version N and its model and renders will be deleted. This cannot be undone." with "Yes, delete version N" and "Cancel" buttons. When N is the composition's only version, the question SHALL say that the composition will be deleted and the measured room kept.

Only "Yes" SHALL send the delete. Afterwards the Rooms page SHALL show the remaining versions, or drop the composition when it has none left, and the Project panel SHALL refresh. A refusal SHALL be shown with its reason next to the control.

#### Scenario: Confirmed delete on the Rooms page
- **WHEN** the owner shows `Wohnen` version 2, presses "Delete version 2", then "Yes, delete version 2"
- **THEN** version 2 is no longer among the composition's versions and the page shows another version

#### Scenario: Cancelled
- **WHEN** the owner presses "Delete version 2" and then "Cancel"
- **THEN** nothing is deleted and the delete control is shown again

#### Scenario: Approved version has no delete
- **WHEN** the owner shows `Wohnen` version 4, which is approved
- **THEN** no "Delete version 4" control is shown

#### Scenario: Refusal shown
- **WHEN** the owner confirms deleting a composition version that is still building
- **THEN** the refusal is shown next to the control and the version stays listed

### Requirement: The Project panel opens the conversation's room in 3D beside the chat
The Project panel SHALL show, under the piece, a "Selected room" heading and below it the conversation's confirmed room or apartment by name. When its composition has a 3D model the panel SHALL offer a button to inspect it. Pressing it SHALL show the room's 3D view beside the chat in the same split screen as the piece inspector: on a wide screen the chat on one side and the room on the other, on a narrow screen the room below the chat. The view SHALL be the Rooms page's 3D view of the composition, with the same cameras, modes, surface switches and dimensions switch, the ceiling starting off. The pane SHALL offer the same version dropdown as the Rooms page (the newest five versions, the latest chosen); choosing a version SHALL show it, and a version without a 3D model SHALL be named in plain words. Opening it SHALL NOT start a turn, and the owner SHALL still be able to read, scroll and send messages. The pane SHALL show the room's name and a control to close it, after which the chat takes the width again. The open room view and its chosen version SHALL be part of the page's address, so a reload shows them again.

When the room or apartment has no composition, the panel SHALL say in plain words that it has no 3D view yet and that the Designer can compose it. When the composition's latest version has no 3D model, the panel SHALL say that composing it again adds the 3D view. When the conversation has confirmed no room or apartment, the panel SHALL show no room section. An address naming a room view that is not the conversation's current room SHALL show no room pane.

Only one side pane SHALL be shown at a time: opening the room view SHALL close an open piece inspector, and opening a piece version (from the panel or a notice) SHALL close an open room view.

The panel and the pane SHALL NOT show model names of language models, prompts, token counts or costs. The room section SHALL pass a recorded browser check before it counts as done.

#### Scenario: Inspect the room
- **WHEN** the conversation has confirmed `Hall`, composition `Hall` has a 3D model, and the owner presses "Inspect Hall" in the Project panel under "Selected room"
- **THEN** the 3D view of `Hall` is shown beside the chat with its surface switches and the ceiling off, and the composer is still usable

#### Scenario: Another version beside the chat
- **WHEN** the room view of `Hall` shows version 3 and the owner chooses version 2 in its dropdown
- **THEN** version 2's model is shown, and a reload shows version 2 again

#### Scenario: Dimensions beside the chat
- **WHEN** the owner switches dimensions on in the room view of `Hall`
- **THEN** each wall of `Hall` is labelled with its length and the ceiling height is shown once

#### Scenario: No 3D view yet
- **WHEN** the conversation has confirmed `Hall` and `Hall` has no composition
- **THEN** the Project panel says `Hall` has no 3D view yet and that the Designer can compose the room, and offers no inspect button

#### Scenario: No room confirmed
- **WHEN** the conversation has confirmed no room or apartment
- **THEN** the Project panel shows no room section

#### Scenario: Close the room view
- **WHEN** the owner closes the room pane
- **THEN** the chat takes the full width beside the rail again

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the room view of `Hall` is shown
- **THEN** the conversation and the room view of `Hall` are shown again

#### Scenario: One pane at a time
- **WHEN** the room view of `Hall` is shown and the owner presses "Inspect version 2" in the Project panel
- **THEN** the piece inspector for version 2 is shown beside the chat and the room view is closed; pressing "Inspect Hall" then shows the room and closes the inspector

### Requirement: The Pieces page opens or starts each piece's conversation
The Pieces page SHALL place a conversation link directly under each piece card's header (the piece's id or name). When that piece already has a conversation, the link SHALL open it. When it has none, the link SHALL start a conversation bound to that piece and open it. The link SHALL NOT show a model name, prompt, token count or cost. The flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Open the existing conversation
- **WHEN** `hall-bench` has a conversation and the owner chooses the conversation link under its header
- **THEN** that conversation opens

#### Scenario: Start when the piece has none
- **WHEN** `shoe-rack` has no conversation and the owner chooses the conversation link under its header
- **THEN** a conversation bound to `shoe-rack` is started and opens with the composer ready

### Requirement: The Pieces page starts a conversation for a new piece
The Pieces page SHALL show a "Create A New Piece" button at the top of the page. Choosing it SHALL start an unbound conversation and open it so the owner can describe a new piece. The button SHALL NOT show a model name, prompt, token count or cost. The flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Create A New Piece
- **WHEN** the owner clicks "Create A New Piece"
- **THEN** an untitled conversation with no bound piece opens with the composer ready

#### Scenario: Button at the top
- **WHEN** the owner opens the Pieces page with two pieces listed
- **THEN** "Create A New Piece" is shown above the piece cards

### Requirement: Conversations are not listed in the Studio navigation
The Studio navigation SHALL NOT include a Conversations item. Routes `/conversations` and `/conversations/:threadId` SHALL remain reachable by deep link and from the Pieces page conversation links. After sign-in the owner SHALL land on the Pieces page.

#### Scenario: Nav without Conversations
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** there is no Conversations item, and Pieces is present

#### Scenario: Sign-in lands on Pieces
- **WHEN** the owner signs in successfully
- **THEN** the Studio opens on the Pieces page

#### Scenario: Deep link still works
- **WHEN** the owner opens `/conversations/<thread-id>` for an existing conversation
- **THEN** that conversation view opens

### Requirement: Opening an inspector from the Project flyout closes the flyout
When the owner chooses "Inspect version N" or "Inspect <room>" in the Project flyout, the conversation view SHALL close the flyout and show the inspector beside the chat. Other actions in the flyout (approve, unapprove, delete, using a look) SHALL leave it open, and the Tools and Decisions so far flyouts SHALL not be affected. Reopening the Project icon SHALL open the flyout again with the inspector still shown.

#### Scenario: Inspecting a version closes the flyout
- **WHEN** the owner opens the Project flyout and presses "Inspect version 1"
- **THEN** the flyout is closed and the inspector for version 1 is shown beside the chat

#### Scenario: Inspecting the room closes the flyout
- **WHEN** the owner presses "Inspect Hall" in the Project flyout
- **THEN** the flyout is closed and the room view is shown beside the chat

#### Scenario: Other actions keep it open
- **WHEN** the owner approves a version in the Project flyout
- **THEN** the flyout stays open
