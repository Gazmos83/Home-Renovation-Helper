## ADDED Requirements

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

## MODIFIED Requirements

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
