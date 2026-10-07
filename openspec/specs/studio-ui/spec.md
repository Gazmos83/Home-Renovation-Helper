# studio-ui Specification

## Purpose

Defines the Studio pages the owner and developer use: conversation tool toggles, and the developer panel's routing, budgets, plugins and usage screens.

## Requirements

### Requirement: Conversations show their tool toggles
The Studio SHALL list the owner's conversations and, for each, its toggleable tools by plain name and description with their on/off state, letting the owner switch them; tools that cannot be toggled SHALL be shown as always on. The page SHALL NOT show model names, token counts or costs.

#### Scenario: Toggle a tool
- **WHEN** the owner switches off the room check in one conversation
- **THEN** the page shows it off for that conversation and the next turn there binds no `room_fit`

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
