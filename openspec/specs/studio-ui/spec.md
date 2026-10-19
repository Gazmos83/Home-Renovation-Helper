# studio-ui Specification

## Purpose

Defines the Studio pages the owner and developer use: conversation tool toggles, and the developer panel's routing, budgets, plugins and usage screens.

## Requirements

### Requirement: The developer panel has its own pages
The Studio SHALL show the developer pages — models and routing, generation and token restrictions, plugins with invocations, usage per day — on a separate route tree that is reachable only when the developer API answers, and SHALL show an API refusal (a failed probe, an out-of-range value) next to the field it names. Each page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Panel disabled
- **WHEN** the developer panel is disabled
- **THEN** the developer pages are not reachable and no link to them is shown

### Requirement: The Studio is an owner-only single-page app
The Studio SHALL be a client-rendered single-page app served separately from the API, calling it with the session cookie; an unauthenticated visit SHALL show the sign-in page, except a visit to `/`, which SHALL show the marketing page, and a visit to `/crew`, which SHALL show the crew page, and a 401 from any call SHALL return the owner to the sign-in page. The homeowner pages SHALL NOT show model names, prompts, token counts or costs of model calls.

#### Scenario: Not signed in
- **WHEN** the owner opens the price list without a session
- **THEN** the sign-in page is shown and, after signing in, the price list

#### Scenario: Root address signed out
- **WHEN** someone who is not signed in opens `/`
- **THEN** the marketing page is shown, not the sign-in page

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

### Requirement: The conversation view is the homeowner's chat
The conversation view SHALL show the owner's messages and the replies in order as chat bubbles: replies aligned to the left, the owner's messages to the right, and forms, confirmations and question sets centred. Reply text SHALL be set in Commissioner and headings and speaker names in Oswald, served with the app, with a line height of at least 1.6 and space between paragraphs. A reply SHALL be rendered as formatted text — headings, bullet and numbered lists, tables, emphasis, inline code — with raw HTML shown as text and never rendered, and an image shown only when it points at one of the app's own routes. A fenced block marked `calc` SHALL be shown in a framed box set apart from the reply's text. A file route of a piece, a composition or an apartment shell in a reply, written bare or as a link, SHALL be shown as a link that opens in a new tab; no other address in a reply SHALL be linked. A composer SHALL send one message as one turn, and the turn's refusal SHALL be shown in words next to the composer when the service refuses it. While a turn is running the composer SHALL be disabled and a waiting bubble SHALL stand in the reply position: left-aligned, rounded, with a 2 px border and animated dots, naming the specialist currently working ("Designer is working…") and updating as the turn moves on, or "The Foreman is working…" before a specialist is chosen. Under each reply the specialists that ran in that turn SHALL be listed by role name only. A reply's title event SHALL update the heading without a reload. The heading SHALL be editable in place; saving sends the new title and an empty title is refused in words.

**Compact chat.** In the "Piece, room and chat above" layout, and only there, the chat SHALL be a compact transcript instead:
- every message, reply, notice, confirmation, question set, the waiting bubble and a pending confirmation card SHALL be aligned to the left;
- each reply and each of the owner's messages SHALL be a light bubble (a thin border, no filled colour) with its speaker inline before the text on the same line — "Foreman:" before a reply and "You:" before the owner's message — and the text wrapping beside the speaker, not below it;
- the vertical gap between two messages SHALL be at most 8 px;
- the composer's first row SHALL hold, in this order, a "You:" label, the message box with the placeholder "Describe what you want…", and Send (Stop while a turn runs, "Send edit" while editing); the attach control, the edit warning and pending attachments SHALL be on rows below it.

A message's formatting, links, attachments, "Edit", "Add to decisions" and the specialists listed under a reply SHALL be the same in both styles. "Chat and piece", "Chat and room" and the phone view SHALL keep the left and right bubbles.

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

#### Scenario: Compact transcript
- **WHEN** the layout is "Piece, room and chat above" and the conversation holds the owner's "Make it 10 cm narrower" followed by a reply
- **THEN** both are on the left, the owner's message reads "You: Make it 10 cm narrower" on one line in a light bubble, the reply starts with "Foreman:" on its first line, and the gap between them is at most 8 px

#### Scenario: Compact composer
- **WHEN** the layout is "Piece, room and chat above"
- **THEN** "You:", the "Describe what you want…" box and Send are on one row, and "Add a plan, photo, design or note" is below it

#### Scenario: Other layouts unchanged
- **WHEN** the owner switches from "Piece, room and chat above" to "Chat and piece"
- **THEN** the owner's messages are on the right again with "You" above them, and the half-typed message in the composer is kept

### Requirement: A pending confirmation is answered in the view
When a reply carries a pending confirmation, the view SHALL show it as a card headed "Confirm: <title>", where the title is the confirmation's plain title and never its internal subject. The card SHALL show the summary and proposal, the table of calculations when the confirmation has one, a **Yes** and a **No** button and an optional reason, and SHALL hide the composer until it is answered. Answering SHALL send the owner's answer on the thread and show the reply that follows. Reopening a conversation with a confirmation still pending SHALL show the card again.

#### Scenario: Yes
- **WHEN** the Designer proposes a revision and the owner clicks Yes
- **THEN** the view shows the reply that reports the new version and the composer returns

#### Scenario: No with a reason
- **WHEN** the owner clicks No with "make it 4 shelves"
- **THEN** the reason is sent with the answer and the next reply is shown

#### Scenario: Reopened while pending
- **WHEN** the owner reloads a conversation that has a pending brief confirmation
- **THEN** the card is shown and the composer is hidden

#### Scenario: Plain heading for a room change
- **WHEN** the Designer proposes a room change in `Wohnen`
- **THEN** the card is headed "Confirm: Composing room", shows one table row per placed item, and the text `compose_room` appears nowhere in the view

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
The conversation view SHALL show a project panel with the bound piece, its latest version and build state, the progress steps (brief confirmed, piece created, built, draft rendered, reviewed with open items, detail pass, final) each marked done or not, the next step the owner can ask for, the latest still when one exists and otherwise the screenshot, and the piece's open generator-extension requests. The panel SHALL NOT offer a link to a turntable viewer. The panel SHALL refresh while a build is queued or running, while a render of the latest version is queued or running, and after every turn. It SHALL show nothing when the service's progress read is refused other than the refusal's reason.

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
The Studio SHALL show the owner a Pieces page that lists the pieces, then each piece's versions, then each version's published stills (the version's own, in the room, and detailed), showing for each:
- its kind and tier;
- its picture;
- its current rating and comment, with controls to rate up, rate down, edit the comment and clear.

Turntables and restyle variants SHALL NOT be listed on the Pieces page; they are viewed and rated on the inspector's Renders tab, which the version's "Inspect version N" button opens. The page SHALL NOT offer a link to a render's viewer. The page SHALL show an API refusal next to the render it names. It SHALL NOT show model names, prompts, token counts or costs. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Rate a turntable
- **WHEN** the owner opens `hall-bench` v2 from the Pieces page in the inspector, chooses the Renders tab and rates the `draft` turntable down with "too dark"
- **THEN** the tab shows the down rating and the comment, and a reload shows the same

#### Scenario: No internals
- **WHEN** the Pieces page shows a render the Builder started
- **THEN** no model slug, prompt text or token figure appears on the page

#### Scenario: No viewer link
- **WHEN** a version has a published draft turntable and a still
- **THEN** the Pieces page shows the still with its rating controls, no card for the turntable, and no "Open the turntable viewer" link

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
In the Workspace, the chat pane SHALL show one header row with, from the left, the conversation's title, its rename button, its delete action ("Delete <title>") directly to the right of the title, and at the right end a row of panel icons followed by the "Layout" button: "Decisions so far", "Brief", "Project", "Piece" and "Room", each with an accessible name and a tooltip naming it. The header SHALL NOT offer a "Tools" icon, and no conversation view SHALL offer per-conversation tool switches. While the Design Studio rail shows its labels, each icon SHALL show its label beside it. Choosing the Decisions so far, Brief or Project icon SHALL open its panel as a flyout over the chat pane. Choosing it again, choosing another flyout icon, pressing Escape or closing the flyout SHALL close it or switch to the other panel. The Piece and Room icons SHALL NOT open a flyout: choosing one SHALL close any open flyout and show the Workspace's piece pane or room pane, as the requirement "The Workspace's Piece and Room icons open their panes" sets out. The messages SHALL NOT reflow when a flyout opens. The header row SHALL stay visible while the messages scroll. Asking to delete SHALL show the confirmation on its own line below the header row. The Project flyout SHALL show the progress steps, the next step and the open review items, and SHALL refresh while a build or render is queued or running.

#### Scenario: Open and close
- **WHEN** the owner clicks the Project icon in the chat pane header and then presses Escape
- **THEN** the project panel opens over the chat and then closes, and the messages were not reflowed

#### Scenario: Switch
- **WHEN** the Brief flyout is open and the owner clicks the Project icon
- **THEN** the Brief flyout closes and the project panel opens

#### Scenario: No Tools icon
- **WHEN** the owner opens a conversation in the Workspace
- **THEN** the chat pane header shows no "Tools" icon and no tool switches are offered anywhere in the conversation view

#### Scenario: Piece icon opens no flyout
- **WHEN** the Brief flyout is open and the owner clicks the Piece icon
- **THEN** the Brief flyout closes, no flyout opens, and the piece pane is shown beside the chat

#### Scenario: Scrolled conversation
- **WHEN** the owner scrolls a long conversation to its end
- **THEN** the chat pane header and its icons are still shown, and the icons still open their panels or panes

#### Scenario: Icons named
- **WHEN** the owner rests the pointer on the Brief icon
- **THEN** a tooltip shows "Brief"

#### Scenario: Expanded
- **WHEN** the owner chooses "Show labels" on the Design Studio rail
- **THEN** the chat pane header shows each panel's label beside its icon, and choosing "Hide labels" shows the icons only

#### Scenario: Delete beside the title
- **WHEN** the owner opens the conversation "Murphy bed" in the Workspace
- **THEN** "Delete Murphy bed" is on the header row directly right of the title and its rename button, and no separate line holds it

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
The Studio SHALL have a help page, linked from the navigation, that shows every topic of the help source in the help source's order. Each topic SHALL show only its title at first, with a control that expands it to reveal the rest and collapses it again; every topic SHALL start collapsed. The text SHALL come from the help source, so that the page and the chat show the same words.

The blueprint topic SHALL explain how to prepare a blueprint or a hand sketch for Intake and list the measurements Intake needs: each room's name; the length of every wall, edge by edge in one direction around the room; every corner angle that is not 90°; the ceiling height; the wall thickness; every door and window with the wall it is on, its offset from that wall's starting corner, its width, its height and (for a window) its sill height; a scale reference (a dimension line, a printed area or a known door width); and that all rooms of one apartment are drawn in one plan frame. It SHALL keep the worked example of one room. The files topic SHALL say which file types the conversation accepts.

The design file template topic SHALL offer the import template as a download, give the steps for using it, and show the default extraction prompt with a Copy button that copies the prompt exactly. The workflow topic SHALL show a diagram of how a piece is made, with the template import as a branch into the Designer, and a text alternative that names every step. The Pieces page SHALL keep its own template download.

#### Scenario: Help reached
- **WHEN** the owner opens Help from the navigation
- **THEN** every topic shows its title only, and none of its text is visible

#### Scenario: Topic expanded
- **WHEN** the owner expands the blueprint topic
- **THEN** it lists the measurements above, and the other topics stay collapsed

#### Scenario: Files topic
- **WHEN** the owner expands the files topic
- **THEN** it says plans and photos are PNG or JPEG, notes are Markdown or plain text, and designs are a `.json` design file

#### Scenario: Template downloaded from Help
- **WHEN** the owner expands the template topic and chooses the download
- **THEN** the import template is downloaded as `import-template.json` from the owner-gated route

#### Scenario: Prompt copied
- **WHEN** the owner chooses Copy beside the default extraction prompt
- **THEN** the clipboard holds the prompt exactly as the help source states it, and the button confirms the copy

#### Scenario: Workflow diagram
- **WHEN** the owner expands the workflow topic
- **THEN** a diagram shows wish → Intake confirms → Designer drafts → owner confirms → Builder blockout → draft turntable → Reviewer → revise → optional detail pass → final after a typed "yes", with the template import joining at the Designer, and a screen reader reads the same steps

#### Scenario: Help unavailable
- **WHEN** the help source cannot be loaded
- **THEN** the page says the help could not be loaded, and no topic is shown

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
The conversation view SHALL show each notice in the thread's history in its place among the messages, centred and framed like a confirmation, with its text. A finished render of a piece version SHALL show a Review button that names the render's tier: "Review <tier> v1" when the version is 1, and "Review <tier> revision <n>" for version n above 1, where the tier is `draft` or `final`. Pressing it SHALL open the inspector for that piece version in the split view, on its Renders tab, with the most recently finished render of that tier selected. A finished room render's notice SHALL show its link ("Open the turntable viewer" or "Open the still"), opening the result in a new tab. A failed render's notice, a shell's notice, and a room notice without a link SHALL show no button or link. A notice posted while the view is open SHALL appear without a reload while the thread's progress is following a render, including a room render started in the thread. A notice SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: First draft ready
- **WHEN** the draft turntable of `hall-bench` version 1 finishes while the conversation is open
- **THEN** a notice appears without a reload, saying it is ready and can also be checked in the Project panel, with a "Review draft v1" button

#### Scenario: Review opens the render
- **WHEN** the owner presses "Review final revision 4" after a final detail turntable of version 4 finished
- **THEN** the inspector for version 4 opens beside the chat on its Renders tab with the detailed turntable selected and playable

#### Scenario: Later version
- **WHEN** a notice is shown for a finished draft render of `hall-bench` version 3
- **THEN** its button reads "Review draft revision 3"

#### Scenario: Preview and final
- **WHEN** notices are shown for a finished final of `hall-bench` version 4 and for a version-1 render recorded at the removed tier `preview`
- **THEN** their buttons read "Review final revision 4" and "Review draft v1"

#### Scenario: Failed render
- **WHEN** a draft turntable of `hall-bench` version 2 fails
- **THEN** a notice says it did not finish and shows no button

#### Scenario: Room render link
- **WHEN** the draft turntable of `wohnen` version 11 finishes while the Murphy bed conversation is open
- **THEN** its notice appears without a reload, with an "Open the turntable viewer" link that opens the viewer in a new tab and no Review button

### Requirement: A piece version is reviewed beside the conversation
The Workspace's piece pane SHALL show the inspector for one piece version, with its version dropdown, in every layout that has a piece pane. It SHALL show the version named in the address (`?inspect=<package-id>/<n>`), or otherwise the latest version of the conversation's bound piece. When the conversation has no bound piece, the pane SHALL say in plain words that no piece has been designed yet in this conversation. While the inspector is shown, the owner SHALL still be able to read, scroll and send messages, and opening the inspector SHALL NOT start a turn. Opening another version, from the dropdown, a notice or the Project panel, SHALL replace the shown one and write it to the address, so a reload shows it again. When the current layout has no piece pane, opening a version SHALL switch to the "Chat and piece" layout. A version that is not built, or a file it lacks, SHALL be named in plain words as on the inspector page.

#### Scenario: Review from a notice
- **WHEN** the owner presses "Review draft v1" on a notice for `hall-bench` version 1
- **THEN** the piece pane shows the inspector for `hall-bench` version 1 and the composer is still usable

#### Scenario: Ask about a detail
- **WHEN** the piece pane shows a version and the owner sends "the left shelf looks too thin"
- **THEN** the message is sent as a normal turn and the piece pane still shows that version

#### Scenario: Bound piece by default
- **WHEN** the owner opens a conversation bound to `hall-bench`, whose latest version is 3, with no `?inspect=` in the address, in the "Chat and piece" layout
- **THEN** the piece pane shows `hall-bench` version 3

#### Scenario: No piece yet
- **WHEN** the owner opens a new conversation with no bound piece in the "Chat and piece" layout
- **THEN** the piece pane says no piece has been designed yet in this conversation

#### Scenario: Opened from the room layout
- **WHEN** the layout is "Chat and room" and the owner presses "Review draft v2" on a notice
- **THEN** the layout switches to "Chat and piece" and the piece pane shows version 2

#### Scenario: Close
- **WHEN** the piece pane is shown in "Chat and piece" and the owner chooses the "Chat and room" layout
- **THEN** the piece pane is no longer shown, and the room pane takes its place beside the chat

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the piece pane shows `hall-bench` version 2
- **THEN** the conversation and the inspector for version 2 are shown again, in the same layout

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
The conversation view SHALL show each build notice in its place among the messages, framed like a render notice. A finished build's notice SHALL show an "Inspect version N" button that opens the inspector for that piece version beside the chat. A failed build's notice, and a notice whose version was deleted, SHALL show no button. A build notice posted while the view is open SHALL appear without a reload while the Project panel is following a build. A revision SHALL NOT add a second notice with its own button: the build notice and its "Inspect version N" button are the one notice of a revision. A revision notice already in a thread's history SHALL be shown as its text with no button. It SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: Built while open
- **WHEN** `hall-bench` version 2 finishes building while its conversation is open
- **THEN** a notice saying version 2 is built appears without a reload, with an "Inspect version 2" button

#### Scenario: Inspect from the notice
- **WHEN** the owner presses "Inspect version 2" on that notice
- **THEN** the inspector for `hall-bench` version 2 is shown beside the chat and the composer is still usable

#### Scenario: Failed build
- **WHEN** the build of `hall-bench` version 3 fails
- **THEN** its notice says it did not build and shows no button

#### Scenario: One notice per revision
- **WHEN** the owner confirms a revision of `hall-bench` and version 2 builds
- **THEN** the conversation shows one notice for version 2, saying it is built, with an "Inspect version 2" button and no "Open version 2" button

#### Scenario: Old revision notice
- **WHEN** a thread's history holds a revision notice "hall-bench version 2 is created." from before this change
- **THEN** it is shown as text with no button

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
The picture of each piece, on its tile and at the top of its dialog, SHALL be the build screenshot of one version:
- the approved version, when it has a screenshot;
- otherwise the newest version that has a screenshot.

A caption under the picture SHALL name the version, followed by "(approved)" when it is the approved one, e.g. "Version 14 (approved)". On the tile, this caption SHALL be the tile's detail line. The picture SHALL NOT follow the dialog's version dropdown. It SHALL be the build screenshot only, never a render. A piece with no screenshot in any version SHALL show no picture in its dialog, a placeholder icon on its tile, and no error. After an approval changes or a version is deleted, the tile and the dialog SHALL show the version these rules now choose, without a reload.

#### Scenario: Approved version shown
- **WHEN** `listening-wall` has versions 1 to 14, all built, and version 9 is approved
- **THEN** its tile and its dialog show version 9's screenshot captioned "Version 9 (approved)", whichever version the dropdown shows

#### Scenario: None approved
- **WHEN** no version of `murphy-bed` is approved and versions 1 to 4 are built
- **THEN** its tile shows version 4's screenshot captioned "Version 4"

#### Scenario: Newest has not built
- **WHEN** no version of `murphy-bed` is approved, version 5 failed and version 4 is built
- **THEN** its tile shows version 4's screenshot captioned "Version 4"

#### Scenario: No screenshot at all
- **WHEN** `hall-bench` has only version 1 and it is still building
- **THEN** its tile shows a placeholder icon, its dialog shows no picture, and there is no error

#### Scenario: Render not used
- **WHEN** the approved version has a rendered still and a build screenshot
- **THEN** the tile shows the build screenshot

#### Scenario: Approval changes the tile
- **WHEN** the owner approves version 12 of `listening-wall` in its dialog and closes it
- **THEN** the tile shows version 12's screenshot captioned "Version 12 (approved)" without a reload

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
The Project panel SHALL show, under the piece, a "Selected room" heading and below it the conversation's confirmed room or apartment by name. When its composition has a 3D model, the panel SHALL offer a button to inspect it. Pressing it SHALL show the room's 3D view in the Workspace's room pane, and SHALL switch to the "Chat and room" layout when the current layout has no room pane. In every layout with a room pane, the pane SHALL show the room named in the address (`?room=<slug>[/<n>]`), or otherwise the conversation's confirmed room at its composition's latest version. The view SHALL be the Rooms page's 3D view of the composition, with the same cameras, modes, surface switches and dimensions switch, and the ceiling starting off. The pane SHALL show the room's name and offer the same version dropdown as the Rooms page (the newest five versions, the latest chosen). Choosing a version SHALL show it, and a version without a 3D model SHALL be named in plain words. Opening it SHALL NOT start a turn, and the owner SHALL still be able to read, scroll and send messages. The shown room and its chosen version SHALL be part of the page's address, so a reload shows them again.

When the room or apartment has no composition, the panel and the room pane SHALL say in plain words that it has no 3D view yet and that the Designer can compose it. When the composition's latest version has no 3D model, they SHALL say that composing it again adds the 3D view. When the conversation has confirmed no room or apartment, the panel SHALL show no room section and the room pane SHALL say that no room is confirmed yet. An address naming a room that is not the conversation's current room SHALL be ignored, and the pane SHALL show the current room.

The piece pane and the room pane SHALL be shown together in the "Piece, room and chat above" layout. Opening one SHALL NOT close the other.

The panel and the panes SHALL NOT show model names of language models, prompts, token counts or costs. The room section SHALL pass a recorded browser check before it counts as done.

#### Scenario: Inspect the room
- **WHEN** the layout is "Chat and piece", the conversation has confirmed `Hall`, composition `Hall` has a 3D model, and the owner presses "Inspect Hall" in the Project panel under "Selected room"
- **THEN** the layout switches to "Chat and room", the 3D view of `Hall` is shown with its surface switches and the ceiling off, and the composer is still usable

#### Scenario: Another version beside the chat
- **WHEN** the room pane shows `Hall` version 3 and the owner chooses version 2 in its dropdown
- **THEN** version 2's model is shown, and a reload shows version 2 again

#### Scenario: Dimensions beside the chat
- **WHEN** the owner switches dimensions on in the room view of `Hall`
- **THEN** each wall of `Hall` is labelled with its length and the ceiling height is shown once

#### Scenario: No 3D view yet
- **WHEN** the conversation has confirmed `Hall` and `Hall` has no composition
- **THEN** the Project panel and the room pane say `Hall` has no 3D view yet and that the Designer can compose the room, and the panel offers no inspect button

#### Scenario: No room confirmed
- **WHEN** the conversation has confirmed no room or apartment
- **THEN** the Project panel shows no room section and the room pane says no room is confirmed yet

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the room pane shows `Hall`
- **THEN** the conversation and the room view of `Hall` are shown again

#### Scenario: Close the room view
- **WHEN** the room pane is shown in "Chat and room" and the owner chooses the "Chat and piece" layout
- **THEN** the room pane is no longer shown, and the piece pane takes its place beside the chat

#### Scenario: One pane at a time
- **WHEN** the layout is "Chat and room" and the owner presses "Inspect version 2" in the Project panel
- **THEN** the layout switches to "Chat and piece" with version 2 shown; pressing "Inspect Hall" then switches back to "Chat and room" with `Hall` shown

#### Scenario: Piece and room together
- **WHEN** the layout is "Piece, room and chat above" and the owner presses "Inspect version 2" and then "Inspect Hall" in the Project panel
- **THEN** the piece pane shows version 2, the room pane shows `Hall`, and neither closes the other

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

### Requirement: The Measured Rooms page shows each room with its composition
The Studio SHALL have a Measured Rooms page for the owner at `/rooms`: a one-line intro, then one tile per room of the house file in the paged tile grid, each named by the room's name, followed by one tile per standalone composition. Choosing a room's tile SHALL open that room's dialog. When the house file holds no room the page SHALL say that no rooms are measured yet and that one is described in a conversation. Wherever another requirement names the Rooms page, it SHALL mean this page.

**The room.** Each room's dialog SHALL show:
- its name and the apartment it belongs to, or nothing;
- a "Room brief" button that opens a separate dialog titled "<room> brief" showing its size (width × depth in millimetres, and the number of corners when it is not four), its ceiling height and its number of openings on one line, then the pieces in it as a table (piece name and id), or "No pieces in this room." The room's dialog itself SHALL NOT show the size line or the pieces;
- its composition, set out below, or, when it has none, that it has no composition yet and that the Designer can compose it in a conversation.

Each room SHALL have a delete action. Choosing it SHALL open a confirm dialog that names the room and what deleting it does:
- the pieces in it, by name, that become "No room";
- the number of conversations that lose their confirmed room;
- its composition and the number of its versions that are removed, with their renders.

Nothing SHALL be deleted until the owner confirms in the dialog. Cancelling SHALL send nothing. After a delete the room's dialog SHALL close, the room's tile and its composition SHALL be gone, and the pieces' rooms SHALL be shown updated without a reload, on this page and on the Pieces page. A room that belongs to an apartment SHALL show why it cannot be deleted here instead of a working delete action. A refused delete SHALL show its reason in the room's dialog, and the room SHALL stay listed.

**The composition.** A room's composition SHALL be shown inside that room's dialog. An apartment composition, and a room composition whose room is not in the house file, SHALL each have a tile of its own after the room tiles, marked "Apartment" or "Room", opening a dialog titled with its name. For each composition the page SHALL offer a version dropdown listing its newest five versions, newest first, with the latest chosen. Older versions SHALL be kept and SHALL NOT be listed. Everything below SHALL show the chosen version. For the chosen version the page SHALL show:
- its version number and that version's build status;
- its items by name and type, with each piece's version and approval state ("no longer approved" shown plainly), or "The room only, no furniture" when it has no items;
- its screenshot or still. The dialog SHALL NOT show a link to the turntable viewer outside the 3D view;
- when the version has `model.glb`, a 3D view of the composition, loaded only when the owner opens it; choosing another version in the dropdown SHALL show that version in the open view. It SHALL use the piece inspector's camera controls (free rotate and zoom, Iso, Front, Side and Plan) and its Workshop and Blueprint modes. It SHALL offer one switch per surface of the version's surface map: each wall, the floor, the ceiling and the items, plus "All walls". Switching a surface off SHALL hide exactly the meshes the map lists under it, and a mesh the map does not name stays visible. All surfaces SHALL start switched on, except the ceiling, which starts off so the room can be seen from above. The view SHALL offer a "dimensions" switch, off at first. Switched on, it SHALL label every unique wall of the version's room plan with its length in millimetres, on that wall (a wall two rooms of an apartment share is labelled once), and each room's ceiling height in millimetres once per room (so an apartment whose rooms differ shows each height). The figures SHALL be the chosen version's own. While the 3D view is open and the chosen version has a turntable, the view SHALL offer "Open the turntable viewer of <name>", opening the viewer in a new tab; this is the only place on the page that offers it. A version without `model.glb` SHALL show its screenshot or still and say that composing the room again adds the 3D view.

The page SHALL NOT show the model library, model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Measured room listed
- **WHEN** the house file holds `Hall` with `shoe-bench` in it and no composition
- **THEN** the Measured Rooms page shows a tile `Hall` with its size and ceiling height, its dialog says it has no composition yet, and its "Room brief" button opens a dialog with its size, ceiling and openings and a table listing `shoe-bench`

#### Scenario: Composition inside its room
- **WHEN** the house file holds `Wohnen` and composition `Wohnen` has versions 1 and 2
- **THEN** the `Wohnen` dialog shows the composition's version dropdown with version 2 chosen, its items and its picture, and no separate `Wohnen` composition tile is shown

#### Scenario: Apartment composition on its own card
- **WHEN** apartment `Wohnung` has a composition
- **THEN** a tile `Wohnung` marked "Apartment" is shown after the room tiles

#### Scenario: No rooms
- **WHEN** the house file holds no room
- **THEN** the page says that no rooms are measured yet and that one is described in a conversation

#### Scenario: Delete warns first
- **WHEN** the owner chooses delete on `Hall`, which holds `shoe-bench`, was confirmed in one conversation and has composition `Hall` with two versions
- **THEN** a dialog names `shoe-bench` as becoming "No room", one conversation losing its confirmed room, and composition `Hall` with two versions removed, and nothing has been deleted

#### Scenario: Delete cancelled
- **WHEN** the owner cancels that dialog
- **THEN** no request is sent and `Hall` is still listed

#### Scenario: Delete confirmed
- **WHEN** the owner confirms that dialog
- **THEN** the `Hall` dialog closes, the `Hall` tile is no longer shown without a reload, and the Pieces page shows `shoe-bench` with "No room"

#### Scenario: Room in an apartment
- **WHEN** `Küche` belongs to apartment `Wohnung`
- **THEN** the `Küche` dialog shows that it cannot be deleted here because it belongs to `Wohnung`

#### Scenario: Delete refused
- **WHEN** the delete route refuses because the room's composition is building
- **THEN** the reason is shown in the room's dialog and the room is still listed

#### Scenario: Empty composition shown
- **WHEN** composition `Hall` v1 has no items and its build succeeded
- **THEN** the `Hall` dialog shows "The room only, no furniture" and its screenshot

#### Scenario: Unapproved piece shown
- **WHEN** a composition places a piece version that has since been unapproved
- **THEN** the dialog lists that item with "no longer approved" beside it

#### Scenario: Room shown in 3D
- **WHEN** composition `Wohnen` v2 has `model.glb` and the owner opens its 3D view
- **THEN** the composition is shown from the Iso camera with switches for each wall, the floor, the ceiling, the items and "All walls", and the ceiling is off

#### Scenario: Wall switched off
- **WHEN** the owner switches wall 2 off
- **THEN** every mesh the surface map lists under wall 2 is hidden and the pieces behind it can be seen, and all other surfaces stay as they were

#### Scenario: Older composition without a model
- **WHEN** composition `Hall` v1 was built before the 3D view existed and has no `model.glb`
- **THEN** the `Hall` dialog shows its screenshot and says that composing `Hall` again adds the 3D view

#### Scenario: Newest five versions offered
- **WHEN** composition `Wohnen` has versions 1 to 7
- **THEN** its version dropdown lists versions 7, 6, 5, 4 and 3, version 7 is shown, and versions 1 and 2 are still kept

#### Scenario: Older version chosen
- **WHEN** the owner chooses version 5 of `Wohnen` in the dropdown while its 3D view is open
- **THEN** the dialog shows version 5's status, items and picture, and the 3D view shows version 5's model

#### Scenario: Wall and ceiling dimensions
- **WHEN** the owner switches dimensions on in the 3D view of a five-walled room `Wohnen` with a 2500 mm ceiling
- **THEN** each of the five walls is labelled with its own length in mm and the ceiling height reads 2500 mm once

#### Scenario: Apartment heights differ
- **WHEN** the owner switches dimensions on in the 3D view of an apartment whose `Bad` is 2400 mm high and whose other rooms are 2550 mm, with one wall shared by `Bad` and `Flur`
- **THEN** `Bad` shows 2400 mm, each other room shows 2550 mm, and the shared wall carries one length label

#### Scenario: Turntable viewer only in the 3D view
- **WHEN** composition `Wohnen` version 11 has a turntable and the owner opens the `Wohnen` dialog
- **THEN** no "Open the turntable viewer of Wohnen" link is shown until the owner opens the 3D view, and the open 3D view offers it

### Requirement: The Model Library page lists, uploads and deletes models
The Studio SHALL have a Model Library for the owner at `/models` with two views, chosen from the Design Studio sub-menu: "Uploaded models" and "Upload model".

**Uploaded models** SHALL show a one-line intro saying the library holds bought furniture and decor as 3D models (a GLB file, or a zip with one glTF or OBJ model and its files), then one tile per model in the paged tile grid, each with the model's preview picture, its name, its stated size and its check state. When the library is empty the view SHALL say so and point to "Upload model". Choosing a tile SHALL open the model's dialog showing its name, a larger preview picture, its stated size, its measured size and triangle count once checked, its check state (`checking`, `ready`, or `refused` with its reason), and a delete action. A refused delete SHALL show its reason in the dialog. A model being checked SHALL change state on its tile and in its dialog without a reload.

**Preview pictures.** When a model reads `ready` and has no preview picture, the Uploaded models view SHALL draw the model once in the owner's browser from its own stored files, from a fixed three-quarter view on a plain background, and store the picture with the model. Until a picture exists, and when drawing fails, the tile SHALL show a placeholder icon. A failed drawing SHALL NOT show an error on the tile and SHALL NOT be retried until the view is opened again. No Blender process and no render SHALL be started to make a preview picture.

**Upload model** SHALL open, over the Uploaded models grid, a dialog holding the upload form: a file, a name and the three dimensions. A refused upload SHALL show its reason in the dialog, next to the field it names, and keep what the owner typed. A successful upload SHALL close the dialog and show the page of the grid that holds the new model, as a `checking` tile (the library lists models oldest first, so it is the last page). Closing the dialog without uploading SHALL send nothing. The dialog's address SHALL be `/studio/models/upload`.

The views SHALL NOT show measured rooms, compositions, model names of language models, prompts, token counts or costs. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Models listed
- **WHEN** the library holds `Sofa` (2200 × 950 × 800 mm, ready, with a preview picture)
- **THEN** Uploaded models shows a tile `Sofa` with its picture, "2200 × 950 × 800 mm" and "ready", and its dialog has a delete action

#### Scenario: Upload in a dialog
- **WHEN** the owner chooses "Upload model"
- **THEN** the address is `/studio/models/upload` and the upload form is shown in a dialog over the Uploaded models grid

#### Scenario: Upload refused
- **WHEN** the owner uploads a `.blend` file
- **THEN** the dialog stays open showing the refusal reason, and the library is unchanged

#### Scenario: Upload succeeds
- **WHEN** the owner uploads a GLB armchair named `armchair` at 800 × 700 × 900 mm
- **THEN** the dialog closes and an `armchair` tile reading `checking` is shown with a placeholder icon

#### Scenario: Check finishes
- **WHEN** an uploaded model's check finishes while the view is open
- **THEN** its state changes from `checking` to `ready` without a reload, and its placeholder is replaced by its preview picture

#### Scenario: Preview cannot be drawn
- **WHEN** the browser cannot draw a ready OBJ model
- **THEN** its tile keeps the placeholder icon and shows no error

### Requirement: The workspace, pieces, measured rooms, the model library, pricing and agent settings are tabs of one Design Studio page
The Studio SHALL have a Design Studio page for the owner at `/studio` with no visible page title on any tab (its level-1 heading "Design Studio" is for screen readers only, so the space goes to the tab's content), and five owner tabs, in this order: "Workspace", "Pieces", "Measured Rooms", "Model Library" and "Pricing". When the developer gate answers, a sixth tab, "AI & Agent Settings", SHALL follow them below a divider. Without the developer gate, that tab and the divider SHALL NOT be shown. Each owner tab SHALL have its own address (`/studio/workspace`, `/studio/pieces`, `/studio/rooms`, `/studio/models`, `/studio/pricing`), and opening that address SHALL show the page with that tab chosen. The AI & Agent Settings tab SHALL keep the developer route tree's addresses, as its requirement states. `/studio`, and a `/studio/` address naming no known tab, SHALL show the Workspace tab. The tabs SHALL be a rail at the screen's left edge below the header, with the same font, icon style, colour scheme and "Hide labels" switch as the conversation page's panel rail: each tab an icon, with its label beside it while labels are shown, the chosen tab highlighted, and the switch at the rail's foot. The label choice SHALL be remembered in the browser and shared with the other rails; a browser that cannot store it SHALL show the labels hidden. The tabs SHALL be exposed as a vertical tab list with the chosen tab marked selected, and only the chosen tab's content SHALL be shown.

**Sub-menu.** Beside the rail, the chosen tab SHALL show a sub-menu, each entry with its label always shown:
- Workspace: "New conversation", then the conversations by title, newest first;
- Pieces: the name (id) of every piece, in the order of the Pieces grid;
- Measured Rooms: the name of every measured room, then the name of every composition that has a tile of its own (an apartment composition, or a room composition whose room is not in the house file), in the order of the Measured Rooms grid;
- Model Library: "Uploaded models" and "Upload model";
- Pricing: "Prices", "Snapshots" and "Remnants";
- AI & Agent Settings: "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins" and "Models and Routing".

There SHALL be no "All pieces" or "All rooms" entry. With no dialog open, each tab's address (`/studio/pieces`, `/studio/rooms`) SHALL show its tile grid, and no Pieces or Measured Rooms entry SHALL be highlighted. Choosing a piece's, room's or composition's name SHALL open that item's dialog over the grid, at the same address and with the same behaviour as choosing its tile, keeping `?page`. Closing the dialog SHALL return to the grid as it does for a tile. While an item's dialog is open, its name SHALL be highlighted and marked as the current entry. A list with no item SHALL say "No pieces yet" or "No rooms yet" in the sub-menu. A name too long for the column SHALL be cut short with an ellipsis, and its full name SHALL be shown on hover. A sub-menu longer than the screen SHALL scroll on its own, with the page and the rail staying in place. The names SHALL follow the lists without a reload: a piece or room that is created or deleted SHALL appear in or disappear from the sub-menu as its tile does.

"Uploaded models" SHALL be the Model Library's first view and its address (`/studio/models`), and "Prices" the Pricing tab's (`/studio/pricing`). "Upload model" SHALL open the upload dialog of the Model Library requirement over Uploaded models, and SHALL be highlighted while that dialog is open. In the Workspace sub-menu, "New conversation" SHALL start a conversation and open it, and a conversation's entry SHALL open it at `/studio/workspace/<thread-id>`, highlighted while it is open. On a screen 768 CSS px wide or wider the sub-menu SHALL be a column between the rail and the content, with a close button ("Close <sub-menu name>", an "x") at its top. The column SHALL stay open when the owner chooses one of its entries, including "New conversation", and SHALL close only when the owner presses its close button; the content SHALL then use the freed width. Choosing a tab on the rail, including the tab already chosen, SHALL open the column again. Opening a Design Studio address directly, or reloading it, SHALL show the column open. Narrower, it SHALL be one row across the top of the content, below the page title, that scrolls sideways when the names do not fit, and the rail SHALL stay at the left edge as it is.

Each tab SHALL show what its page showed: wherever another requirement names the Pieces page, the Measured Rooms page (or the Rooms page) or the Model Library page, it SHALL mean that tab, and where it gives that page a heading row with its page title, no title is shown and the tab keeps the rest of its heading row. The old addresses `/pieces`, `/rooms` and `/models` SHALL open the matching tab; a piece version's inspector SHALL keep its address `/pieces/<id>/versions/<n>`. The Studio navigation SHALL NOT show a "Design Studio" entry, nor "Pieces", "Measured Rooms", "Model Library", "Pricing Overview" or "AI & Agent Settings" entries; the Design Studio is reached as the home page. The routes SHALL require sign-in, and a signed-out visit SHALL go to the sign-in page. The owner tabs SHALL NOT show model names, prompts, token counts or costs of model calls. The page SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Pieces first
- **WHEN** the owner chooses "Pieces" on the Design Studio rail
- **THEN** the Pieces tab opens with the piece tiles shown, and the pieces listed by name in the sub-menu with none highlighted

#### Scenario: No page title
- **WHEN** the owner opens any Design Studio tab
- **THEN** no "Design Studio" title is shown above the tab's content, and a screen reader still finds the level-1 heading "Design Studio"

#### Scenario: Labels shown and hidden
- **WHEN** the owner chooses "Show labels" on the Design Studio rail
- **THEN** each tab shows its label beside its icon, and the Workspace chat pane's panel icons show their labels too until the owner hides them

#### Scenario: Tab chosen
- **WHEN** the owner chooses the Model Library tab
- **THEN** the address is `/studio/models`, the sub-menu shows "Uploaded models" (chosen) and "Upload model", the model tiles are shown, and the pieces and measured rooms are not

#### Scenario: Sub-menu on a phone
- **WHEN** the owner opens `/studio/models` on a 360 × 780 screen
- **THEN** "Uploaded models" and "Upload model" are a row of tabs above the tiles, and the rail is still at the left edge

#### Scenario: Tab address reloaded
- **WHEN** the owner reloads `/studio/rooms`
- **THEN** the Design Studio page opens with the Measured Rooms tab chosen

#### Scenario: Old address
- **WHEN** the owner opens a bookmark to `/rooms`
- **THEN** the Design Studio page opens with the Measured Rooms tab chosen

#### Scenario: Inspector address kept
- **WHEN** the owner opens `/pieces/shoe-bench/versions/2`
- **THEN** the inspector for `shoe-bench` version 2 opens, and its "Back to pieces" link opens the Pieces tab

#### Scenario: Navigation
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** it shows no "Design Studio", "Pieces", "Measured Rooms", "Model Library", "Pricing Overview" or "AI & Agent Settings" entry

#### Scenario: Signed out
- **WHEN** a signed-out visitor opens `/studio/pricing/remnants`
- **THEN** they are sent to the sign-in page

#### Scenario: Owner rail
- **WHEN** the owner is signed in without the developer gate and opens the Design Studio
- **THEN** the rail shows "Workspace", "Pieces", "Measured Rooms", "Model Library" and "Pricing", in that order, and no divider and no "AI & Agent Settings" tab

#### Scenario: Developer rail
- **WHEN** the developer is signed in and opens the Design Studio
- **THEN** the rail shows "Workspace", "Pieces", "Measured Rooms", "Model Library" and "Pricing", then a divider and "AI & Agent Settings"

#### Scenario: Pieces listed by name
- **WHEN** the owner opens the Pieces tab and the pieces are `bench`, `hall-bench` and `shelf`
- **THEN** the sub-menu lists `bench`, `hall-bench` and `shelf` in the grid's order, and no "All pieces" entry

#### Scenario: Rooms and apartment listed
- **WHEN** the house file holds `Hall` and `Küche`, and apartment `Wohnung` has a composition
- **THEN** the Measured Rooms sub-menu lists `Hall`, `Küche`, then `Wohnung`, and no "All rooms" entry

#### Scenario: Name opens the dialog
- **WHEN** the owner, on page 2 of Pieces, chooses `shelf` in the sub-menu
- **THEN** the address is `/studio/pieces/shelf?page=2`, the `shelf` dialog opens over the grid, and `shelf` is highlighted in the sub-menu

#### Scenario: Dialog closed
- **WHEN** the owner closes the `shelf` dialog
- **THEN** the address is `/studio/pieces?page=2`, the grid is shown, and no name is highlighted

#### Scenario: Composition name opens its dialog
- **WHEN** the owner chooses `Wohnung` in the Measured Rooms sub-menu
- **THEN** the address is `/studio/rooms/compositions/wohnung` and the `Wohnung` dialog opens

#### Scenario: No pieces
- **WHEN** there are no pieces
- **THEN** the Pieces sub-menu says "No pieces yet"

#### Scenario: Deleted room leaves the sub-menu
- **WHEN** the owner deletes `Hall` from its dialog
- **THEN** `Hall` is gone from the sub-menu and from the grid without a reload

#### Scenario: Names on a phone
- **WHEN** the owner opens Pieces with 18 pieces on a 360 × 780 screen
- **THEN** the names are one row above the grid that scrolls sideways, the page does not scroll sideways, and the rail is still at the left edge

#### Scenario: Sub-menu stays open after a choice
- **WHEN** the screen is 1280 px wide and the owner chooses "Remnants" in the Pricing sub-menu column
- **THEN** the Remnants view is shown and the sub-menu column stays open with "Remnants" highlighted

#### Scenario: Sub-menu closed with its x
- **WHEN** the owner presses "Close Conversations" at the top of the Workspace sub-menu column
- **THEN** the column closes and the conversation uses the freed width

#### Scenario: Sub-menu reopened from the rail
- **WHEN** the Pieces sub-menu column is closed and the owner chooses the Pieces tab on the rail
- **THEN** the Pieces sub-menu column is shown again

#### Scenario: Row unchanged on a phone
- **WHEN** the screen is 360 px wide and the owner chooses a conversation in the Workspace sub-menu row
- **THEN** the conversation opens and the sub-menu row stays shown above the content

### Requirement: Design Studio tabs show a paged grid of picture tiles
The Pieces, Measured Rooms and Uploaded models views SHALL each show their items as a grid of tiles in place of one card per item. Each tile SHALL show:
- a picture filling the tile's top, kept whole (not cropped);
- below it, the item's name on one line (cut short with an ellipsis when too long), and one line of detail in smaller, muted text;
- a state badge in the picture's top-right corner when the item has a state to show.

The tile's content per view is:
- a piece: the picture is the one the piece-picture requirement chooses; the detail line is that picture's caption ("Version 9 (approved)"); the badge reads "Approved" when a version is approved.
- a measured room: the picture is its composition's latest picture; the detail line is width × depth in mm and the ceiling height; the badge names its apartment, if it has one.
- a standalone composition (apartment, or a room no longer in the house file): its latest picture, its name, and an "Apartment" or "Room" badge.
- an uploaded model: its preview picture; its stated width × depth × height in mm; its check state (`checking`, `ready` or `refused`), with `refused` marked as an error.

An item with no picture SHALL show a placeholder icon of its kind in place of the picture, and no error. Each tile SHALL be one control that can be reached by keyboard and named by the item's name. It SHALL show a visible ring on hover and keyboard focus.

**Grid size.** On a screen 1024 CSS px wide or wider, the grid SHALL be 4 tiles across and 4 down. Below 1024 px it SHALL be 2 across and 3 down. The rows SHALL share the height left below the header, the tab heading and the paging controls, so one page of tiles fills the screen without scrolling at 1280 × 800 and at 360 × 780 (Samsung Galaxy S25). On a screen too short for readable tiles, the rows SHALL keep a minimum height and the page SHALL scroll rather than squash them.

**Pages.** A view holding more items than one grid SHALL split them into pages of 16 (4 × 4) or 6 (2 × 3), in the order the view lists them today. Previous and Next buttons and "Page N of M" SHALL show below the grid only when there is more than one page. Previous SHALL be disabled on the first page and Next on the last. The page number SHALL be in the address as `?page=N`. Reloading SHALL show the same page, and a page past the last SHALL show the last page. When the screen width crosses 1024 px, the page SHALL change to the one holding the first tile that was shown. An empty view SHALL keep its existing empty-state message and show no grid or paging controls.

#### Scenario: Laptop grid
- **WHEN** the owner opens Uploaded models with 20 models in a 1280 × 800 window
- **THEN** 16 tiles are shown, 4 across and 4 down, with no vertical scroll, and "Page 1 of 2" with Next enabled and Previous disabled

#### Scenario: Phone grid
- **WHEN** the owner opens Pieces with 8 pieces on a 360 × 780 screen
- **THEN** 6 tiles are shown, 2 across and 3 down, and "Page 1 of 2"

#### Scenario: Page in the address
- **WHEN** the owner chooses Next and then reloads
- **THEN** the address ends in `?page=2` and page 2 is shown again

#### Scenario: One page only
- **WHEN** Measured Rooms holds 3 rooms
- **THEN** 3 tiles are shown and no paging controls

#### Scenario: Width crosses the breakpoint
- **WHEN** the owner is on page 2 of 16-tile pages (tiles 17 to 32) and narrows the window below 1024 px
- **THEN** page 3 of 6-tile pages is shown, holding tile 17

#### Scenario: No picture
- **WHEN** piece `hall-bench` has only version 1, still building
- **THEN** its tile shows a placeholder icon, the name `hall-bench` and no error

#### Scenario: Refused model
- **WHEN** model `Lamp` reads `refused`
- **THEN** its tile shows a `refused` badge marked as an error

### Requirement: A tile opens its detail in an addressable dialog
Choosing a tile SHALL open a dialog over the grid that shows everything the item's card showed before this change, with the same controls, refusals and live updates. Its title SHALL be the item's name. Wherever another requirement gives content to a piece card, a room card or a composition card, it SHALL mean that item's dialog. The "Create A New Piece" button and the import-template link ("Import template") SHALL stay above the Pieces grid, on one row so the grid still fills the screen. Beside the link, an information button SHALL show, until it is pressed again, Escape is pressed or focus leaves it, the Pieces intro and the line on how to use the template (give it to another AI chat, then attach the returned file in a new conversation), without moving the grid.

Each dialog SHALL have its own address under its tab:
- `/studio/pieces/<piece-id>`;
- `/studio/rooms/<room-name>`;
- `/studio/rooms/compositions/<slug>` for a standalone composition;
- `/studio/models/<model-id>`.

The grid's page number SHALL be kept in the address while the dialog is open. Opening a dialog's address directly SHALL show the grid with that dialog open. Browser Back, Esc, the dialog's close button and a click outside the dialog SHALL each close it and return to the grid address, with the grid not reloaded. An address naming an item that does not exist (or no longer exists, for example after a delete from inside the dialog) SHALL show the grid with no dialog. A deleted item's tile SHALL be gone without a reload.

The dialog SHALL keep keyboard focus inside it while open, return focus to the tile that opened it when it closes, and be named by its title. On a screen narrower than 640 CSS px it SHALL fill the screen. Wider, it SHALL be centred, at most 90 % of the screen high, and scroll its own content. Hovering over or focusing a tile SHALL start loading that item's detail, so the dialog usually opens with its content ready. The dialog SHALL NOT show model names of language models, prompts, token counts or costs.

#### Scenario: Pieces header fits
- **WHEN** the owner opens Pieces with 20 pieces on a 360 × 780 screen
- **THEN** "Create A New Piece" and "Import template" share one row above a 2 × 3 grid, and the page does not scroll

#### Scenario: Template how-to
- **WHEN** the owner presses the information button beside "Import template"
- **THEN** the line on giving the template to another AI chat and attaching the returned file is shown over the grid

#### Scenario: Open a piece
- **WHEN** the owner chooses the `listening-wall` tile on page 2 of Pieces
- **THEN** the address is `/studio/pieces/listening-wall?page=2` and a dialog titled `listening-wall` shows its conversation link, picture, room, version dropdown, approval, downloads, pricing, renders and variants

#### Scenario: Back closes
- **WHEN** that dialog is open and the owner presses browser Back
- **THEN** the dialog closes, the address is `/studio/pieces?page=2`, and page 2 of the grid is shown

#### Scenario: Link reopens
- **WHEN** the owner reloads `/studio/rooms/Wohnen`
- **THEN** the Measured Rooms grid is shown with the `Wohnen` dialog open, holding its size, openings, pieces, delete action and composition

#### Scenario: Unknown item
- **WHEN** the owner opens `/studio/models/` followed by the id of a deleted model
- **THEN** the Uploaded models grid is shown and no dialog

#### Scenario: Delete from the dialog
- **WHEN** the owner confirms the delete of `Hall` in its dialog
- **THEN** the dialog closes and the `Hall` tile is gone without a reload

#### Scenario: Phone dialog
- **WHEN** the owner opens a model's dialog on a 360 × 780 screen
- **THEN** the dialog fills the screen and has a close button

#### Scenario: Focus returns
- **WHEN** the owner opens the `Sofa` tile with the keyboard and presses Esc
- **THEN** the dialog closes and the `Sofa` tile has focus

### Requirement: The inspector has a Renders tab
The inspector, both its page and the conversation's split view, SHALL have a Renders tab beside its Model and Cut list tabs. The tab SHALL list every published render of the version, newest first:
- the still and the turntable;
- the still and the turntable in the room;
- the detailed still and the detailed turntable;
- each restyle variant.

Each item SHALL show its label and tier, and its current rating and comment with controls to rate up, rate down, edit the comment and clear, as on the Pieces page.

A selected turntable SHALL play in the tab as a frame scrubber:
- it shows the first frame at once;
- the owner moves through the frames with a slider, by dragging across the picture, and with the arrow keys;
- it wraps at both ends;
- it shows the frame number and the frame count.

A selected still SHALL show its picture. Frames and pictures SHALL be loaded only from the version's file routes and only when the tab is shown. The images SHALL stay files under the render root and SHALL NOT be stored in the database. The open tab and the selected render SHALL be part of the page's address, so a reload shows them again. A version with no renders SHALL say so in plain words. The tab SHALL NOT show a viewer link, a model name, prompt, token count or cost.

#### Scenario: Remote detail turntable played
- **WHEN** an approved `final` detail turntable of `hall-bench` v4 rendered on the render server has been published, and the owner opens the Renders tab and selects "Detailed turntable"
- **THEN** frame 1 of 36 is shown at once, and dragging or pressing the right arrow steps through the frames and wraps from 36 to 1

#### Scenario: Variant played and rated
- **WHEN** the owner selects the `walnut` variant on the Renders tab and rates it up
- **THEN** its 12 draft frames play in the scrubber, and the up rating is shown and kept after a reload

#### Scenario: Address keeps the selection
- **WHEN** the owner reloads while the Renders tab shows the detailed turntable
- **THEN** the Renders tab opens again with the detailed turntable selected

#### Scenario: Tab not opened
- **WHEN** the owner inspects a version and stays on the Model tab
- **THEN** no render frame is fetched

#### Scenario: No renders yet
- **WHEN** the owner opens the Renders tab of a built version with no renders
- **THEN** the tab says there are no renders of this version yet

### Requirement: The Workspace shows a conversation in a chosen layout
The Design Studio's Workspace tab SHALL show one conversation at `/studio/workspace/<thread-id>` in one of three layouts:
- "Chat and piece": the chat pane on the left, the piece pane on the right;
- "Chat and room": the chat pane on the left, the room pane on the right;
- "Piece, room and chat above": the chat pane across the top, with the piece pane on the left and the room pane on the right below it.

A layout button with an accessible name "Layout" SHALL sit in the chat pane's header row, after its panel icons, at the row's right end. It SHALL open a menu of the three layouts, each with a small picture of its arrangement and its name, with the current one marked. Choosing one SHALL switch the layout without reloading the conversation and without starting a turn, and SHALL show the chat scrolled to its last message. The default layout SHALL be "Chat and piece". There SHALL be no "Piece and room, chat below" layout; a browser that remembered it SHALL open in "Piece, room and chat above" at that layout's default sizes.

Between every two neighbouring panes there SHALL be a resize handle: between the chat and the piece or room left and right, between the piece and the room left and right, and between the chat and the panes below it up and down. Dragging a handle SHALL resize the panes on both sides. Double-clicking it SHALL restore that layout's default sizes. With the handle focused, the arrow keys SHALL move it. No pane SHALL be made smaller than 20 % of its group. The default sizes SHALL be half and half for each left and right split, and 40 % for the chat and 60 % for the panes below it in "Piece, room and chat above". The chosen layout and each layout's sizes SHALL be remembered in the browser. A browser that cannot store them SHALL use the defaults. The panes SHALL fill the height of the screen below the header (and, on a phone, the sub-menu row), and each pane SHALL scroll on its own.

`/studio/workspace` SHALL open the newest conversation. When there is none, it SHALL say so in plain words and offer "New conversation". A `/studio/workspace/` address naming an unknown conversation SHALL say the conversation was not found, and SHALL keep the sub-menu.

Below 1024 CSS px wide, the Workspace SHALL show one pane at a time, chosen from a row of "Chat", "Piece" and "Room" tabs above it, and SHALL NOT show the layout button. Opening a piece version or the room from the chat SHALL choose that pane's tab.

Wherever another requirement names the conversation view or the conversation page, it SHALL mean the Workspace with that conversation open. Where it says "beside the chat", it SHALL mean in the piece or room pane. The Workspace SHALL NOT show model names, prompts, token counts or costs of model calls. The tab SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Default layout
- **WHEN** the owner opens a conversation in the Workspace for the first time in this browser
- **THEN** the chat is on the left and the piece pane on the right, each half the width

#### Scenario: Choose a layout
- **WHEN** the owner presses "Layout" and chooses "Piece, room and chat above"
- **THEN** the chat is across the top, the piece pane on the bottom left, the room pane on the bottom right, and no turn starts

#### Scenario: Last message after a switch
- **WHEN** a long conversation is shown scrolled to its end in "Chat and piece" and the owner chooses "Piece, room and chat above"
- **THEN** the chat shows its last message, scrolled to the bottom of the messages box

#### Scenario: Layout button in the chat header
- **WHEN** the owner opens a conversation in the Workspace on a 1280 × 800 screen
- **THEN** the "Layout" button is at the right end of the chat pane's header row, after the Room icon, and no "Design Studio" title is shown above the Workspace

#### Scenario: Old layout remembered
- **WHEN** the browser remembered "Piece and room, chat below" and the owner opens a conversation
- **THEN** the Workspace opens in "Piece, room and chat above" with the chat at 40 % and the piece and room at half and half

#### Scenario: Drag a handle
- **WHEN** in "Chat and piece" the owner drags the handle between the chat and the piece to the right
- **THEN** the chat grows and the piece pane shrinks, and neither becomes smaller than 20 %

#### Scenario: Chat expanded downwards
- **WHEN** in "Piece, room and chat above" the owner drags the handle below the chat downwards
- **THEN** the chat grows taller and the piece and room panes grow shorter

#### Scenario: Chat expanded upwards
- **WHEN** in "Piece, room and chat above" the owner drags the handle below the chat upwards
- **THEN** the chat grows shorter and the piece and room panes grow taller, and the chat never becomes smaller than 20 %

#### Scenario: Double-click resets
- **WHEN** the owner double-clicks a handle after dragging it
- **THEN** the panes on both sides return to that layout's default sizes

#### Scenario: Keyboard
- **WHEN** the owner focuses the handle between the piece and the room and presses the left arrow
- **THEN** the piece pane shrinks and the room pane grows

#### Scenario: Remembered
- **WHEN** the owner chooses "Chat and room", drags its handle, and reloads the page
- **THEN** the layout is "Chat and room" with the dragged sizes

#### Scenario: Storage unavailable
- **WHEN** the browser cannot store the layout
- **THEN** the Workspace opens in "Chat and piece" at the default sizes, and switching and resizing still work until the page is left

#### Scenario: Newest conversation
- **WHEN** the owner chooses "Workspace" on the rail and conversations exist
- **THEN** the newest conversation opens and is highlighted in the sub-menu

#### Scenario: New conversation
- **WHEN** the owner chooses "New conversation" in the Workspace sub-menu
- **THEN** a conversation is started, it opens at its `/studio/workspace/<thread-id>` address, and it is listed first in the sub-menu

#### Scenario: Phone tabs
- **WHEN** the owner opens a conversation on a 360 × 780 screen
- **THEN** "Chat", "Piece" and "Room" tabs are shown with "Chat" chosen, only the chat is shown, and there is no layout button

#### Scenario: Phone review
- **WHEN** on a 360 × 780 screen the owner presses "Review draft v1" on a notice
- **THEN** the "Piece" tab is chosen and shows version 1

### Requirement: Prices, snapshots and remnants are views of the Design Studio's Pricing tab
The Design Studio's Pricing tab SHALL have three views, in this order: "Prices", "Snapshots" and "Remnants", chosen from its sub-menu. Each view SHALL have its own address (`/studio/pricing/prices`, `/studio/pricing/snapshots`, `/studio/pricing/remnants`), and opening that address SHALL show the Design Studio with the Pricing tab and that view chosen. `/studio/pricing`, and a `/studio/pricing/` address naming no known view, SHALL show the Prices view. Only the chosen view's content SHALL be shown. Each view SHALL show what the matching Pricing Overview tab showed: wherever another requirement names the Pricing Overview page or its Prices, Snapshots or Remnants tab, it SHALL mean the Pricing tab or that view. The old addresses `/pricing`, `/pricing/prices`, `/pricing/snapshots`, `/pricing/remnants`, `/price-list`, `/snapshots` and `/remnants` SHALL open the matching view, and a `/pricing/` address naming no known tab SHALL open the Prices view. The tab SHALL NOT show model names, prompts, token counts or costs of model calls. The tab SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Prices first
- **WHEN** the owner chooses "Pricing" on the Design Studio rail
- **THEN** the address is `/studio/pricing`, the sub-menu shows "Prices" (chosen), "Snapshots" and "Remnants", and the price list is shown

#### Scenario: View chosen
- **WHEN** the owner chooses "Remnants" in the Pricing sub-menu
- **THEN** the address is `/studio/pricing/remnants`, the rack is shown, and the price list and snapshots are not

#### Scenario: View address reloaded
- **WHEN** the owner reloads `/studio/pricing/snapshots`
- **THEN** the Design Studio opens with the Pricing tab and its Snapshots view chosen

#### Scenario: Old address
- **WHEN** the owner opens a bookmark to `/snapshots` or to `/pricing/snapshots`
- **THEN** the Design Studio opens at `/studio/pricing/snapshots` with the Snapshots view chosen

#### Scenario: Pricing on a phone
- **WHEN** the owner opens `/studio/pricing/prices` on a 360 × 780 screen
- **THEN** "Prices", "Snapshots" and "Remnants" are a row of tabs above the price list, and the page does not scroll sideways

### Requirement: The Workspace is the home page
After sign-in the owner SHALL land on the Workspace tab, which opens the newest conversation. `/`, `/studio`, any address the Studio does not know, and a developer address opened without the developer gate SHALL open the Workspace for a signed-in owner. The header's "Little Homey" name, shown with the app's house icon, SHALL be a link to the Workspace. The header navigation SHALL NOT include a Conversations item; conversations SHALL be listed in the Workspace tab's sub-menu. `/conversations` SHALL open the Workspace, and `/conversations/<thread-id>` SHALL open `/studio/workspace/<thread-id>`, keeping its `?inspect=` and `?room=` values. The Pieces tab's conversation links SHALL open `/studio/workspace/<thread-id>`.

#### Scenario: Sign-in lands on the Workspace
- **WHEN** the owner signs in successfully and conversations exist
- **THEN** the Design Studio opens with the Workspace tab chosen and the newest conversation open

#### Scenario: Home address
- **WHEN** the signed-in owner opens `/` or `/studio`
- **THEN** the Workspace tab opens

#### Scenario: Name in the header
- **WHEN** the owner is on the Help page and clicks "Little Homey" in the header
- **THEN** the Workspace tab opens

#### Scenario: Nav without Conversations
- **WHEN** the owner is signed in and looks at the Studio navigation
- **THEN** there is no Conversations item and no "Design Studio" item

#### Scenario: Deep link still works
- **WHEN** the owner opens `/conversations/<thread-id>?inspect=hall-bench/2` for an existing conversation
- **THEN** the address becomes `/studio/workspace/<thread-id>?inspect=hall-bench/2`, and that conversation opens with version 2 in the piece pane

### Requirement: The header offers sign-out
While the owner is signed in, the header SHALL show a "Sign out" button at its right end. Pressing it SHALL end the session (the sign-out of the owner-auth capability) and show the sign-in page, with no header. If the sign-out request fails, the owner SHALL stay signed in and the reason SHALL be shown in words beside the button.

#### Scenario: Sign out
- **WHEN** the signed-in owner presses "Sign out"
- **THEN** the session is ended, the sign-in page is shown, and opening `/studio/workspace` afterwards shows the sign-in page

#### Scenario: Sign-out fails
- **WHEN** the owner presses "Sign out" and the service cannot be reached
- **THEN** the owner stays on the page, still signed in, and the reason is shown beside the button

### Requirement: The inspector shows and sets the version's verdict
The inspector, both its page and the conversation's split view, SHALL show the shown version's verdict above its tabs as one compact row, on every tab, whether or not the version is built or rendered. The row SHALL hold a thumbs up ("Matches what I confirmed") and a thumbs down ("Doesn't match what I confirmed"), each with that accessible name and tooltip, the chosen one shown as pressed. With no verdict, only the two thumbs SHALL be shown. A note field SHALL appear only once a thumb is chosen. A thumbs up SHALL be saved at once, with an optional note. A thumbs down SHALL be saved only with a note that is not blank; until then nothing is saved. Pressing the chosen thumb again SHALL clear the verdict. Editing the note and pressing Enter or leaving the field SHALL save it. For a thumbs down, the row SHALL show whether it is open, resolved or dismissed, and offer "Mark resolved" and "Dismiss" while it is open. Switching versions SHALL show that version's verdict. A refusal SHALL be shown with its reason next to the row. The row SHALL NOT show a model name, prompt, token count or cost, and it SHALL pass a recorded browser check before it counts as done.

#### Scenario: Blockout marked wrong in the inspector
- **WHEN** the owner opens `amesbury-wardrobe` v4, presses thumbs down, writes "the side sections lost their 5 drawers" and presses Enter
- **THEN** thumbs down is shown pressed with the note and "open", and a reload shows the same

#### Scenario: Note required
- **WHEN** the owner presses thumbs down and saves with an empty note
- **THEN** nothing is saved and the row asks for what does not match

#### Scenario: No note field before a choice
- **WHEN** the owner opens a version with no verdict
- **THEN** only the two thumbs are shown

#### Scenario: Cleared by pressing again
- **WHEN** the owner presses thumbs up on a version whose verdict is thumbs up
- **THEN** the verdict is cleared and the note field is gone

#### Scenario: Resolved
- **WHEN** the owner marks v4's open thumbs down resolved
- **THEN** the row shows it as resolved and no longer offers resolve or dismiss

### Requirement: The Cut list marks hardware the model does not show
The Cut list tab SHALL mark a hardware row with `*` after its item when its `shown` is less than its quantity, or when its quantity is unknown and its `shown` is 0. A row with some pieces shown SHALL add "(n of m shown)". When any row is marked, a legend under the hardware table SHALL read "* not shown in the model". A version whose `spec.json` hardware has no `shown` SHALL mark no row and show no legend. The tab SHALL pass a recorded browser check before it counts as done.

#### Scenario: Unshown line marked
- **WHEN** the owner opens the Cut list of a version whose `murphy-mechanism` row has quantity 1 and `shown` 0
- **THEN** the row reads "Vertical Murphy bed mechanism … *" and the legend "* not shown in the model" is shown

#### Scenario: Partly shown
- **WHEN** a hinge row has quantity 24 and `shown` 16
- **THEN** the row is marked `*` with "(16 of 24 shown)"

#### Scenario: Fully shown, no mark
- **WHEN** every hardware row's `shown` equals its quantity
- **THEN** no row is marked and no legend is shown

#### Scenario: Older version
- **WHEN** the owner opens a version built before hardware was drawn
- **THEN** no row is marked and no legend is shown

### Requirement: The inspector has a Reading tab
The inspector, both its page and the conversation's split view, SHALL have a Reading tab beside its Model, Cut list and Renders tabs.

For an approved version the tab SHALL show the reading list grouped by wall-hung item, with the fixed notice above it and any gap lines. Each entry SHALL show its citation fields and open its link in a new tab. An entry whose source can be read locally SHALL offer "Read here", which shows that source's blocks with their page references, paged. One whose source cannot be read SHALL show the reason instead.

For a version that is not approved, the tab SHALL say "Approve this version to see recommended reading" and show no list.

Below the list, the tab SHALL show the version's stored engineering reports, newest first. Each report SHALL show its overall outcome, "Conformity not established", whether it is stale with its reasons, and its evidence passages when available. A report whose evidence is unavailable SHALL show that limitation. A version with no stored reports SHALL say so in plain words.

Text SHALL be loaded only when the tab is shown. The open tab SHALL be part of the page's address. The tab SHALL NOT show a model name, prompt, token count or cost. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Reading after approval
- **WHEN** the owner approves `hall-shelf` v3 and opens the Reading tab
- **THEN** the wall shelf's sources are listed under the notice, and "Read here" on a local-use source shows its blocks

#### Scenario: Unapproved version
- **WHEN** the owner switches the inspector to v4, which is not approved
- **THEN** the Reading tab shows "Approve this version to see recommended reading" and no list

#### Scenario: Stale report
- **WHEN** v3 has a stored report and v4 is a newer geometry version
- **THEN** v3's report is shown as stale with "a newer geometry version exists"

### Requirement: The Workspace's piece and room panes approve the version they show
The Workspace's piece pane SHALL show, for the piece version it shows, whether that version is approved, and the room pane SHALL do the same for the composition version it shows. The approval control SHALL sit at the top of the pane, above the 3D view. Each pane SHALL offer "Approve version N" when the shown version's build succeeded and it is not approved, and "Unapprove version N" when the shown version is the approved one. Neither control SHALL be offered for a version that is not built. Approving the shown version SHALL replace any other approved version of the same piece or composition. An API refusal SHALL be shown next to the control in the service's plain words, never as a status code or an internal code, and the version's state SHALL stay as it was. After a change, the pane, its version dropdown, the Pieces page and the Measured Rooms page SHALL show the new state without a reload.

While the room's latest composition version is queued or running, the conversation's progress SHALL be read again every few seconds, as it is for a piece build. Once that version's build succeeds, the room pane SHALL offer "Approve version N" without a reload.

**Piece pane.** Besides approval, the piece pane SHALL show:
- the piece's build state;
- "N of 15 versions" once the piece holds 13 or more;
- "Delete version N" for the shown version when it is neither approved nor queued or building, with the "Are you sure?" flow of "A version is deleted from the Pieces page and the Project panel after 'Are you sure?'";
- the shown version's restyle looks with "Keep this look", which sends the owner's request to the conversation;
- the piece's open generator-extension requests.

**Room pane.** Besides approval, the room pane SHALL show:
- "Delete version N" for the shown composition version when it is not approved, with the "Are you sure?" flow of "A composition version is deleted from the Rooms page and the Project panel after 'Are you sure?'";
- the shown version's restyle looks.

Wherever another requirement gives the Project panel, or the Piece or Room flyout, a piece's or room's approval, delete, looks, version-limit notice, picture or "Inspect" control, it SHALL mean these panes. Neither pane SHALL show a model name, prompt, token count or cost. Approving, unapproving or deleting SHALL NOT start a turn. The flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approve the shown piece version
- **WHEN** the piece pane shows `hall-bench` version 2, which is built and not approved, and the owner presses "Approve version 2"
- **THEN** the pane shows version 2 as approved and the version dropdown labels version 2 "approved"

#### Scenario: Approve an older piece version from the dropdown
- **WHEN** `hall-bench` version 3 is approved, the owner chooses version 2 in the piece pane's dropdown and presses "Approve version 2"
- **THEN** version 2 is approved and version 3 is no longer approved

#### Scenario: Unapprove the shown piece version
- **WHEN** the piece pane shows approved `hall-bench` version 2 and the owner presses "Unapprove version 2"
- **THEN** the pane shows that version 2 is not approved and offers "Approve version 2"

#### Scenario: Unbuilt version offers no control
- **WHEN** the piece pane shows `hall-bench` version 4 while it is still building
- **THEN** the pane offers neither "Approve version 4" nor "Unapprove version 4", and no "Delete version 4"

#### Scenario: Approve the shown room version
- **WHEN** the room pane shows `Hall` version 2, which is built and not approved, and the owner presses "Approve version 2"
- **THEN** the pane shows version 2 as approved and its dropdown labels version 2 "(approved)"

#### Scenario: Room approval refused
- **WHEN** the owner approves `Hall` version 2 from the room pane while it places a piece version that is not approved
- **THEN** the service's reason naming that piece is shown next to the control, with no status code, and version 2 stays unapproved

#### Scenario: Approval does not start a turn
- **WHEN** the owner approves a version from either pane
- **THEN** no message is sent to the conversation and the composer stays usable

#### Scenario: Fresh room version becomes approvable
- **WHEN** the Designer composes `Wohnen` version 3 in the conversation while the room pane shows `Wohnen`, and its build succeeds
- **THEN** the room pane shows version 3 and offers "Approve version 3" without a reload

#### Scenario: Delete from the piece pane
- **WHEN** the piece pane shows unapproved, built `hall-bench` version 3 and the owner presses "Delete version 3", then "Yes, delete version 3"
- **THEN** version 3 is deleted and the pane shows the piece's latest remaining version

#### Scenario: Keep a look from the piece pane
- **WHEN** the piece pane shows `hall-bench` version 2 with a restyle look "Oak" and the owner presses "Keep this look"
- **THEN** the conversation receives the owner's request to keep that look, as the flyout sent it before

#### Scenario: Near the limit
- **WHEN** the conversation's piece holds 14 versions
- **THEN** the piece pane shows "14 of 15 versions"

### Requirement: The Workspace's Piece and Room icons open their panes
In the Workspace's chat pane header, choosing the Piece icon SHALL show the piece pane at the bound piece's latest version, as "Inspect version N" does: the address SHALL name that version, and the layout SHALL switch to "Chat and piece" when the current layout has no piece pane. Choosing the Room icon SHALL show the room pane at the conversation's room, at its composition's latest version, as "Inspect <room>" does: the address SHALL name the room, and the layout SHALL switch to "Chat and room" when the current layout has no room pane. On a screen narrower than the Workspace's wide layout, each icon SHALL choose its pane's tab. In "Piece, room and chat above", choosing one icon SHALL NOT close the other pane.

When the conversation has no piece yet, the Piece icon SHALL show the piece pane, which says in plain words that no piece has been designed yet. When it has no confirmed room, the Room icon SHALL show the room pane, which says that no room is confirmed yet. When the room has no 3D view, the pane SHALL say so as it does today. Choosing an icon SHALL NOT start a turn, and the composer SHALL stay usable.

#### Scenario: Piece icon opens the inspector
- **WHEN** the layout is "Chat and room", the conversation's piece is `hall-bench` at version 3, and the owner clicks the Piece icon
- **THEN** the layout switches to "Chat and piece", the inspector shows `hall-bench` version 3 with its approval control above the 3D view, and no flyout is open

#### Scenario: Room icon opens the room view
- **WHEN** the layout is "Chat and piece", the conversation has confirmed `Hall` whose composition has a 3D model, and the owner clicks the Room icon
- **THEN** the layout switches to "Chat and room" and the room pane shows `Hall` at its latest version with its approval control, and no flyout is open

#### Scenario: No piece yet
- **WHEN** the conversation has no piece and the owner clicks the Piece icon
- **THEN** the piece pane is shown and says that no piece has been designed yet

#### Scenario: No room confirmed
- **WHEN** the conversation has confirmed no room and the owner clicks the Room icon
- **THEN** the room pane is shown and says that no room is confirmed yet

#### Scenario: Phone
- **WHEN** the screen is 360 px wide and the owner clicks the Room icon
- **THEN** the Room tab is chosen and the room pane is shown

### Requirement: Conversation pages show no model internals
No conversation page SHALL show model names, token counts or costs. Delete of a conversation SHALL be offered on the conversation view as set out in "Conversations are deleted from the list". A conversation SHALL use every plugin that is enabled for the whole service on the developer's Plugins page.

#### Scenario: No internals
- **WHEN** the owner opens any conversation
- **THEN** no model name, token count or cost is shown

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on the open conversation "Listening wall" and confirms
- **THEN** the conversation is gone, and when the owner cancels instead, nothing changes

### Requirement: An answered confirmation is shown collapsed
The conversation view SHALL show each answered confirmation in the history in its place, framed and aligned like a confirmation, as one compact row: its plain title and the owner's answer ("Yes" or "No"), followed by the reason when one was given. The row SHALL hold a dropdown button. Pressing it SHALL show the summary the owner was shown and, when the confirmation has one, its table of calculations, and pressing it again SHALL hide them. The row SHALL start collapsed, including after a reload, and opening it SHALL NOT send anything or start a turn. The row SHALL NOT show the confirmation's internal subject, a model name, prompt, token count or cost. The view SHALL pass a recorded browser check before it counts as done.

#### Scenario: Room change collapsed
- **WHEN** the owner confirmed a room change in `Wohnen` with Yes
- **THEN** the conversation shows "Composing room · Yes" with a dropdown, and no item rows are visible

#### Scenario: Calculations opened
- **WHEN** the owner opens the dropdown of "Composing room · Yes"
- **THEN** a table lists each placed item with its kind, size, placement, centre and rotation, and the summary's comparison with the previous version is shown below it

#### Scenario: Declined revision with a reason
- **WHEN** the owner answered a revision No with "make it 4 shelves"
- **THEN** the row reads "Revising piece · No — make it 4 shelves" and the dropdown shows the summary with no table

#### Scenario: Collapsed after a reload
- **WHEN** the owner opens a dropdown and reloads the conversation
- **THEN** every answered confirmation is collapsed again

### Requirement: The app is named Little Homey with a house icon
The app SHALL be named "Little Homey" wherever a name is shown: the header, the browser tab title and the API's published title. The browser tab SHALL show a house icon, and the header SHALL show the same icon beside the name, in the theme's text colour in light and dark mode.

#### Scenario: Tab title and icon
- **WHEN** the owner opens any Studio page
- **THEN** the browser tab is titled "Little Homey" and shows the house icon

#### Scenario: Header in dark mode
- **WHEN** the Studio is shown in dark mode
- **THEN** the header's house icon and name are drawn in the dark theme's text colour

### Requirement: An About page explains the app in plain words
A signed-in owner SHALL reach an About page at `/about` from an "About" link in the header and in the footer. The page SHALL explain, with no technical terms (no model, prompt, token, frame, resolution or engine names):
- that the app makes 3D pictures of furniture and rooms on an ordinary, low-powered computer;
- that pieces are improved by revising them with an AI assistant;
- that a revised piece can be downloaded to add to an existing house model, or placed in a room in the app.

The About page SHALL NOT list the crew; the crew is on the crew page at `/crew`. Opening `/about` signed out SHALL show the same About page under the marketing page's top bar, reached from its "About" link; Help SHALL stay owner-only.

#### Scenario: About from the header
- **WHEN** the signed-in owner clicks "About" in the header
- **THEN** the About page opens and explains the three points in plain words

#### Scenario: Crew moved to its own page
- **WHEN** the signed-in owner reads the About page
- **THEN** it has no "Meet the crew" section; the crew is listed on the crew page

#### Scenario: Header links
- **WHEN** the owner is signed in and looks at the header navigation
- **THEN** its links are "Little Homey", "Help" and "About", in that order, followed by "Sign out"

#### Scenario: Header layout
- **WHEN** the owner is signed in and looks at the header
- **THEN** "Little Homey" with its icon is at the left edge, and "Help", "About" and "Sign out" are together at the right edge

#### Scenario: Signed out
- **WHEN** someone who is not signed in opens `/about`
- **THEN** the About page is shown under the marketing page's top bar, not the sign-in page

### Requirement: Every page has a footer
Every page, the sign-in page included, SHALL end with a footer line showing "© 2026 Little Homey" and the app's version and build, e.g. "v0.1.0 · f08d9cb". The version SHALL be the Studio's package version, and the build SHALL be the short commit the Studio was started or built from, or "dev" when it is unknown. For a signed-in owner the footer SHALL also hold an "About" link. The footer SHALL stay frozen at the bottom of the screen while the page scrolls; page content and full-height panes SHALL end above it, so it SHALL NOT cover page content. It SHALL NOT show a model, prompt, token or cost.

#### Scenario: Footer on the Workspace
- **WHEN** the signed-in owner opens the Workspace
- **THEN** the footer is visible at the bottom of the screen without scrolling and shows "© 2026 Little Homey", the version and build, and an "About" link

#### Scenario: Footer frozen at the bottom
- **WHEN** the owner scrolls a long page such as Help
- **THEN** the footer stays at the bottom of the screen, and the end of the page can be scrolled into view above it

#### Scenario: Footer on the sign-in page
- **WHEN** the sign-in page is shown
- **THEN** the footer shows "© 2026 Little Homey" with the version and build, and no About link

#### Scenario: Unknown build
- **WHEN** the Studio was built where no git commit could be read
- **THEN** the footer shows the version followed by "dev"

### Requirement: The Pieces page shows a built version's assembly steps
On the Pieces page, a built version SHALL offer an "Assembly" dropdown that lists the `assembly` steps of the version's own `spec.json`, in their stored order. Each step SHALL show its number as two digits, its title and its body, exactly as stored. A built version whose `spec.json` holds no steps SHALL say "This version lists no assembly steps." A version that is not built SHALL offer no Assembly dropdown. A failed read of `spec.json` SHALL show its reason inside the dropdown. When the dropdown lists steps, it SHALL offer "Download assembly (PDF)". The PDF SHALL be made in the browser from the listed steps, titled with the piece and version, hold every step's number, title and body in order, and be saved as `<piece>-v<N>-assembly.pdf`. A failure to make the PDF SHALL be shown next to the action. The dropdown SHALL NOT show a model name, prompt, token count or cost. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Built version with steps
- **WHEN** the owner shows built `hall-bench` v2 on the Pieces page, whose `spec.json` holds six assembly steps ending in "Install"
- **THEN** its Assembly dropdown lists steps 01 to 06 in order, with step 06 titled "Install" and its body "Position, level and fix the build in place."

#### Scenario: Built version without steps
- **WHEN** a built version's `spec.json` has no `assembly` field or an empty one
- **THEN** its Assembly dropdown says "This version lists no assembly steps."

#### Scenario: Download the steps as a PDF
- **WHEN** the owner opens the Assembly dropdown of `hall-bench` v2 and presses "Download assembly (PDF)"
- **THEN** a file `hall-bench-v2-assembly.pdf` is saved. It is titled "hall-bench – version 2 – Assembly" and holds steps 01 to 06 with their titles and bodies. No request is sent to the server for it.

#### Scenario: No steps, no download
- **WHEN** a built version's `spec.json` holds no assembly steps
- **THEN** its Assembly dropdown offers no PDF download

#### Scenario: Version not built
- **WHEN** the owner shows `hall-bench` v3, which failed to build
- **THEN** no Assembly dropdown is offered for v3

### Requirement: The inspector's stage controls sit in a grouped column beside the 3D view
Wherever a piece version or a room composition version is shown in 3D (the piece inspector page, the Measured Rooms page, a conversation's split view and the Workspace's piece and room panes), every clickable control of the 3D stage SHALL sit in one column to the right of the 3D view, and the 3D view SHALL take the remaining width. The column SHALL stay to the right at every width, including the split view and the Workspace panes. When its contents are taller than the 3D view, the column SHALL scroll on its own and the 3D view SHALL keep its height.

The column SHALL be divided into sections, each with a heading the owner clicks to fold or unfold it. Within a section the buttons SHALL be listed one above the other, one per line, as thin as their text allows, and all as wide as the column; the column SHALL be as wide as its longest button label (owner, 2026-10-19). Every section SHALL be open when the view is first shown. Folding a section SHALL NOT change the state of any switch in it.

For a room composition the sections SHALL be, in this order:
1. **Views**: Iso, Front, Side, Plan, Workshop and Blueprint.
2. **Room**: All walls, one switch per wall, the floor, the ceiling and, when the version has dimensions, `dimensions`.
3. **Furniture**: All items and one switch per built item, or the single items switch when the build report does not list each item's meshes. A version with no items SHALL show no Furniture section.

For a piece version the sections SHALL be, in this order:
1. **Views**: Iso, Front, Side, Plan, Workshop, Blueprint and Exploded, and the explode slider while Exploded is chosen.
2. **Parts**: one switch per layer the version's `spec.json` names, and `dimensions`.

The switches SHALL keep their names, their starting state and their effect on the model as before; only their place changes. The tabs, the version switcher, the verdict, the overall dimensions line, the straight-on views and the turntable link SHALL stay outside the column.

#### Scenario: Room controls grouped
- **WHEN** the owner opens the 3D view of a room composition version with four walls and two built items
- **THEN** a column right of the view shows a Views section with Iso, Front, Side, Plan, Workshop and Blueprint, a Room section with All walls, wall 1 to wall 4, floor, ceiling and dimensions, and a Furniture section with All items and the two items, all open, and the ceiling is off

#### Scenario: Piece controls grouped
- **WHEN** the owner opens `/pieces/murphy-bed/versions/1`
- **THEN** a column right of the view shows a Views section with Iso, Front, Side, Plan, Workshop, Blueprint and Exploded, and a Parts section with carcass, backs, shelves, fronts, extras and dimensions, all open

#### Scenario: Explode slider in Views
- **WHEN** the owner chooses Exploded
- **THEN** the explode slider appears in the Views section, and it is gone again when the owner chooses Workshop

#### Scenario: Folding keeps switches
- **WHEN** the owner switches wall 2 off, folds the Room section and unfolds it again
- **THEN** wall 2 is still off and its meshes stay hidden while the section is folded

#### Scenario: Split view keeps the column right
- **WHEN** the owner opens a piece version in a conversation's split view
- **THEN** the column is to the right of the 3D view, not below it

#### Scenario: Room without items
- **WHEN** the owner opens the 3D view of a room composition version that places no items
- **THEN** the column shows the Views and Room sections and no Furniture section

### Requirement: A marketing page greets signed-out visitors
A signed-out visit to `/` SHALL show the marketing page. It SHALL have a top bar with the house icon and "Little Homey" at the left and "Meet the crew", "About" and "Sign in" links at the right; a hero section with a line above the headline, the headline "Hello from Little Homey and his crew", a short paragraph, a "Sign in" button and the Little Homey mascot image with descriptive alternative text; and a closing card reading "We help you make your house a home." Both "Sign in" controls SHALL open the sign-in page. The page SHALL use the app's theme in light and dark mode, SHALL end with the footer, and SHALL NOT show a model, prompt, token or cost, nor call any API besides the session check. A signed-in owner opening `/` SHALL get the Workspace, not the marketing page. The "Meet the crew" link SHALL open a crew page at `/crew` with the same top bar, the heading "Meet the crew", one entry per crew member in the order Little Homey, Lil' Worm, Lil' Glitty, Little Beam, Muscles, Bulbs, Mr. Lookback, Money Bags, each with a short, playful job description and no technical terms and the owner's character art for that member beside it, with descriptive alternative text, and the footer; a signed-in owner opening `/crew` SHALL get the same crew page under the owner's header. The sign-in page SHALL hold a "Little Homey" link back to `/`. The page SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Visitor sees the marketing page
- **WHEN** someone who is not signed in opens `/`
- **THEN** the page shows "Little Homey", the headline "Hello from Little Homey and his crew", the mascot image and a "Sign in" button, with the footer at the bottom

#### Scenario: Meet the crew from the marketing page
- **WHEN** the visitor presses "Meet the crew" in the top bar
- **THEN** the crew page opens at `/crew`, listing the eight crew members in order, each with a job description and that member's picture, with "Meet the crew" marked as the current page

#### Scenario: About for a visitor
- **WHEN** the visitor presses "About" in the top bar
- **THEN** the About page opens under the same top bar, with "About" marked as the current page

#### Scenario: Signed-in owner at the crew page
- **WHEN** the signed-in owner opens `/crew`
- **THEN** the crew page opens under the owner's header

#### Scenario: Sign in from the marketing page
- **WHEN** the visitor presses "Sign in" in the hero or the top bar
- **THEN** the sign-in page is shown, and signing in opens the Workspace

#### Scenario: Back from the sign-in page
- **WHEN** the visitor on the sign-in page presses "Little Homey"
- **THEN** the marketing page is shown

#### Scenario: Signed-in owner at the root
- **WHEN** the signed-in owner opens `/`
- **THEN** the Workspace opens and the marketing page is not shown

#### Scenario: Deep link while signed out
- **WHEN** someone who is not signed in opens `/studio/pieces`
- **THEN** the sign-in page is shown, not the marketing page

#### Scenario: Phone width
- **WHEN** the marketing page is shown at 360 × 780
- **THEN** the image sits below the text, nothing scrolls sideways, and the footer covers no content
