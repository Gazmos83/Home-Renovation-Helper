# studio-ui Specification

## Purpose

Defines the Studio pages the owner and developer use: conversation tool toggles, and the developer panel's routing, budgets, plugins and usage screens.

## Requirements

### Requirement: Conversations show their tool toggles
The Studio SHALL list the owner's conversations with their title, the piece each is about when one is bound, and when each last had a turn, newest activity first, and SHALL open a conversation on its own route. The conversation view SHALL show the conversation's toggleable tools by plain name and description with their on/off state, letting the owner switch them; tools that cannot be toggled SHALL be shown as always on. No conversation page SHALL show model names, token counts or costs.

#### Scenario: Toggle a tool
- **WHEN** the owner switches off the room check in one conversation
- **THEN** the page shows it off for that conversation and the next turn there binds no `room_fit`

#### Scenario: List entry
- **WHEN** a conversation is about `hall-bench` and last had a turn today
- **THEN** its list entry shows the title, `hall-bench` and today's time, and clicking it opens the conversation

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

### Requirement: The price list is managed from a page
The price-list page SHALL list entries with label, key, category, unit, effective price, provenance and, when present, the override and the captured price with its date; filter by category; add a manual entry; edit an entry; set and clear an override with a note; refresh a captured entry and show its outcome; and paste a toom URL to create an entry, showing a refusal or parse failure in plain words.

#### Scenario: Paste a URL
- **WHEN** the owner pastes a toom URL with a key and category and submits
- **THEN** the new entry appears with provenance `captured`, or the page shows why it could not be created

### Requirement: Snapshots, remnants and guideline notes have pages
The Studio SHALL let the owner record a snapshot (optionally prefilling an entry), list and delete snapshots; list, add and remove remnants; and list, add, edit and delete guideline notes with their citation. Every form SHALL show the API's refusal reason next to the field it names.

#### Scenario: Future-dated snapshot
- **WHEN** the owner records a snapshot dated tomorrow
- **THEN** the form shows the refusal next to the date

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

Neither view SHALL show a model name, prompt, token count or cost. The import and export flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Design attached
- **WHEN** the owner picks `wall-unit.json` in a conversation
- **THEN** a chip named `wall-unit.json` is shown and is sent with the next message

#### Scenario: Downloads on the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers the design and the bundle downloads, and version 3 offers only the design

#### Scenario: Template offered
- **WHEN** the owner opens the Pieces page
- **THEN** a link downloads the import template, with the line on how to use it

### Requirement: The Rooms page shows compositions and the model library
The Studio SHALL have a Rooms page for the owner, with two parts.

**Compositions.** For each composition the page SHALL show:
- its scope, its latest version and that version's build status;
- its items by name and type, with each piece's version and approval state ("no longer approved" shown plainly);
- the latest screenshot or still, and a link to the viewer when a turntable exists.

**Model library.** The page SHALL show the library with each model's name, stated size and check state (`checking`, `ready`, or `refused` with its reason). It SHALL offer an upload form taking a file, a name and the three dimensions, and a delete action. A refused upload or delete SHALL show its reason next to the form.

The page SHALL NOT show model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Unapproved piece shown
- **WHEN** a composition places a piece version that has since been unapproved
- **THEN** the Rooms page lists that item with "no longer approved" beside it

#### Scenario: Upload refused
- **WHEN** the owner uploads a `.blend` file
- **THEN** the page shows the refusal reason and the library is unchanged

#### Scenario: Check finishes
- **WHEN** an uploaded model's check finishes while the page is open
- **THEN** its state changes from `checking` to `ready` without a reload

### Requirement: The conversation view is the homeowner's chat
The conversation view SHALL show the owner's messages and the replies in order, a composer that sends one message as one turn and shows the reply when it arrives, and the turn's refusal in words next to the composer when the service refuses it. While a turn is running the composer SHALL be disabled and say so. A reply's specialist SHALL be shown by role name only. A file route of a piece, a composition or an apartment shell in a reply SHALL be shown as a link that opens in a new tab; no other address in a reply SHALL be linked.

#### Scenario: Send and read
- **WHEN** the owner types "I want a bench for the hall" and sends it
- **THEN** the message appears at once, the composer is disabled until the reply arrives, and the reply appears under it labelled by the specialist's role

#### Scenario: Refused turn
- **WHEN** the service answers the turn with 503 and the memory reason
- **THEN** the reason is shown next to the composer and the owner's message is not kept in the list

#### Scenario: Render route in a reply
- **WHEN** a reply says the turntable "will be at /packages/hall-bench/versions/1/files/viewer.html."
- **THEN** that route is a link opening in a new tab, without the full stop, and an `https://` address in a reply stays plain text

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
The conversation view SHALL let the owner add PNG or JPEG images to the conversation and attach them to the next message; attached images SHALL be shown as thumbnails on the composer and in the sent message, and a refused upload (type, size, count) SHALL be reported in the service's words.

#### Scenario: Attach a blueprint
- **WHEN** the owner adds `blueprint.jpeg` and sends "This is my flat"
- **THEN** the turn carries the upload and the sent message shows the thumbnail

#### Scenario: Too large
- **WHEN** the owner adds an image over the configured size
- **THEN** the refusal's reason is shown and nothing is attached

### Requirement: The conversation view shows the project's progress
The conversation view SHALL show a project panel with the bound piece, its latest version and build state, the progress steps (brief confirmed, piece created, built, draft or preview rendered, reviewed with open items, detail pass, final) each marked done or not, the next step the owner can ask for, the latest still when one exists and otherwise the screenshot, a link opening the latest turntable viewer in a new tab once that turntable is published, and the piece's open generator-extension requests. The panel SHALL refresh while a build is queued or running and after every turn. It SHALL show nothing when the service's progress read is refused other than the refusal's reason.

#### Scenario: After the first build
- **WHEN** the Builder's build of version 1 finishes while the view is open
- **THEN** the panel shows version 1 built with its screenshot, "built" done, and the next step as a draft render, without a reload

#### Scenario: Open review items
- **WHEN** the latest review of the piece has two open items
- **THEN** the panel shows "reviewed, 2 open" and links to the piece's page

#### Scenario: Turntable finished
- **WHEN** the draft turntable of version 1 has finished
- **THEN** the panel shows the still and an "Open the turntable viewer" link to version 1's viewer

### Requirement: A piece version can be inspected in 3D
The Studio SHALL have an owner-only page per piece version at `/pieces/<package-id>/versions/<n>`. For a built version it SHALL show the version's `model.glb` in a 3D view, with:
- **Camera:** free rotate and zoom with the mouse, and buttons for the Iso, Front, Side and Plan cameras.
- **Modes:** Workshop (lit), Blueprint (flat light with the parts' edges drawn) and Exploded. Exploded has a slider that moves each module away from the piece's centre, with its parts following. The direction comes from the module positions in the version's `spec.json`.
- **Layer switches:** one for each layer the version's `spec.json` names, plus `dimensions`. Switching a layer off hides exactly the meshes the layer map lists under it. A mesh the map does not name stays visible.
- **Overall dimensions:** W, H and D in mm from `spec.json` `overall`, drawn beside the model. Hidden in Exploded mode and when `dimensions` is off.
- **Scale:** a floor grid and a contact shadow.
- **Straight-on views:** `front.png`, `side.png` and `top.png`, when the version has them.

A Cut list tab SHALL show the version's parts (id, name, quantity, length, width, thickness, material, grain, banding, notes, module) and its hardware (id, item, quantity, notes), both read from `spec.json`. When the parts belong to more than one module, the tab SHALL offer a filter with "All" and one choice per module, in the order the parts first name them. Each module is labelled by its name from `spec.json` `module_names`, "Extra parts" for `extras`, and otherwise its id. Choosing a module SHALL show only that module's parts, with their count of rows and pieces. The parts table SHALL name each part's module by that same label. Hardware is not divided by module.

Every measurement on the page SHALL come from the version's own files. The 3D view SHALL be loaded only on this page.

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

### Requirement: The inspector is reachable from the Pieces page and the conversation
The Pieces page SHALL offer an "Inspect" link for every built version. A conversation's project panel SHALL offer an "Inspect" link for the bound piece's latest version once it is built. Both links SHALL open the inspector page for that version in the Studio.

#### Scenario: Inspect from the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers "Inspect" and version 3 does not

#### Scenario: Inspect from the conversation
- **WHEN** the bound piece's version 1 has just been built
- **THEN** the panel shows an "Inspect" link to `/pieces/<package-id>/versions/1`

### Requirement: Conversations are deleted from the list
Each entry on the Conversations page SHALL offer a delete action. It asks for confirmation, naming the conversation and stating that its pieces and renders are kept and that the conversation cannot be restored. A confirmed delete removes the entry without a reload; a cancel changes nothing. A refusal (a reply still being written, or memory unavailable) SHALL be shown in words next to the entry, which stays. The delete flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on "Hall shoe bench" and confirms
- **THEN** the entry disappears from the list and the piece is still on the Pieces page

#### Scenario: Cancel
- **WHEN** the owner chooses delete and then cancels
- **THEN** nothing is sent and the entry stays

#### Scenario: Refused while a reply is written
- **WHEN** the owner confirms a delete while that conversation's turn is running
- **THEN** the entry stays and the refusal is shown next to it
