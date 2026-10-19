## MODIFIED Requirements

### Requirement: The conversation view is the homeowner's chat
The conversation view SHALL show the owner's messages and the replies in order as chat bubbles: replies aligned to the left, the owner's messages to the right, and forms, confirmations and question sets centred. Reply text SHALL be set in Commissioner and headings and speaker names in Oswald, served with the app, with a line height of at least 1.6 and space between paragraphs. A reply SHALL be rendered as formatted text — headings, bullet and numbered lists, tables, emphasis, inline code — with raw HTML shown as text and never rendered, and an image shown only when it points at one of the app's own routes. A fenced block marked `calc` SHALL be shown in a framed box set apart from the reply's text. A file route of a piece, a composition or an apartment shell in a reply, written bare or as a link, SHALL be shown as a link that opens in a new tab; no other address in a reply SHALL be linked. A composer SHALL send one message as one turn, and the turn's refusal SHALL be shown in words next to the composer when the service refuses it. Each reply SHALL be signed with the persona of its speaker: `foreman` (or no speaker) as "Little Homey", `intake` as "Lil' Worm", `designer` as "Lil' Glitty", `builder` as "Muscles", `lighting` as "Bulbs", `reviewer` as "Mr. Lookback", `researcher` as "Money Bags" and `engineering` as "Little Beam"; a reply received from a running turn SHALL be signed as it will be after a reload. While a turn is running the composer SHALL be disabled and a waiting bubble SHALL stand in the reply position: left-aligned, rounded, with a 2 px border and animated dots, naming the specialist currently working by persona ("Lil' Glitty is working…") and updating as the turn moves on, or "Little Homey is working…" before a specialist is chosen. Under each reply the specialists that ran in that turn SHALL be listed by persona only. A reply's title event SHALL update the heading without a reload. The heading SHALL be editable in place; saving sends the new title and an empty title is refused in words.

**Compact chat.** In the "Piece, room and chat above" layout, and only there, the chat SHALL be a compact transcript instead:
- every message, reply, notice, confirmation, question set, the waiting bubble and a pending confirmation card SHALL be aligned to the left;
- each reply and each of the owner's messages SHALL be a light bubble (a thin border, no filled colour) with its speaker inline before the text on the same line — the reply's persona, such as "Lil' Glitty:", before a reply and "You:" before the owner's message — and the text wrapping beside the speaker, not below it;
- the vertical gap between two messages SHALL be at most 8 px;
- the composer's first row SHALL hold, in this order, a "You:" label, the message box with the placeholder "Describe what you want…", and Send (Stop while a turn runs, "Send edit" while editing); the attach control, the edit warning and pending attachments SHALL be on rows below it.

A message's formatting, links, attachments, "Edit", "Add to decisions" and the specialists listed under a reply SHALL be the same in both styles. "Chat and piece", "Chat and room" and the phone view SHALL keep the left and right bubbles.

#### Scenario: Send and read
- **WHEN** the owner types "I want a bench for the hall" and sends it
- **THEN** the message appears at once on the right, the composer is disabled, a waiting bubble on the left names Little Homey and then Lil' Worm, and the reply replaces it on the left signed "Lil' Worm" with "Lil' Worm" listed under it

#### Scenario: Reply signed by its writer
- **WHEN** the conversation holds a reply with the speaker `designer`, one with `engineering` and one with `foreman`
- **THEN** they are signed "Lil' Glitty", "Little Beam" and "Little Homey"

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
- **WHEN** the layout is "Piece, room and chat above" and the conversation holds the owner's "Make it 10 cm narrower" followed by a reply from the Designer
- **THEN** both are on the left, the owner's message reads "You: Make it 10 cm narrower" on one line in a light bubble, the reply starts with "Lil' Glitty:" on its first line, and the gap between them is at most 8 px

#### Scenario: Compact composer
- **WHEN** the layout is "Piece, room and chat above"
- **THEN** "You:", the "Describe what you want…" box and Send are on one row, and "Add a plan, photo, design or note" is below it

#### Scenario: Other layouts unchanged
- **WHEN** the owner switches from "Piece, room and chat above" to "Chat and piece"
- **THEN** the owner's messages are on the right again with "You" above them, and the half-typed message in the composer is kept

## ADDED Requirements

### Requirement: Homeowner pages name the crew by persona
A homeowner page that tells the owner to ask an agent for something SHALL name the agent by its persona, as the conversation view does (for example "Ask Lil' Glitty in a conversation to compose Wohnen."). The developer pages SHALL keep the role names.

#### Scenario: Room without a composition
- **WHEN** the owner opens the Rooms page and the room `Wohnen` has no composition
- **THEN** the page says "No composition yet. Ask Lil' Glitty in a conversation to compose Wohnen."

#### Scenario: Developer pages unchanged
- **WHEN** the developer opens the calls of a conversation whose last turn went Foreman → Designer
- **THEN** the agents are listed as "Foreman" and "Designer"
