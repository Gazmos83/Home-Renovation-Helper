## MODIFIED Requirements

### Requirement: Conversations show their tool toggles
The Studio SHALL list the owner's conversations with their title, the piece each is about when one is bound, and when each last had a turn, newest activity first, and SHALL open a conversation on its own route. A conversation SHALL be started with one action and no title to type; the new conversation opens at once. Each list entry SHALL offer a delete action that asks for confirmation naming the conversation and stating that its pieces are kept; a confirmed delete removes the entry. The conversation view SHALL show the conversation's toggleable tools by plain name and description with their on/off state in the Tools flyout, letting the owner switch them; tools that cannot be toggled SHALL be shown as always on. No conversation page SHALL show model names, token counts or costs.

#### Scenario: Toggle a tool
- **WHEN** the owner opens the Tools flyout and switches off the room check in one conversation
- **THEN** the flyout shows it off for that conversation and the next turn there binds no `room_fit`

#### Scenario: List entry
- **WHEN** a conversation is about `hall-bench` and last had a turn today
- **THEN** its list entry shows the title, `hall-bench` and today's time, and clicking it opens the conversation

#### Scenario: Start without a title
- **WHEN** the owner clicks "New conversation"
- **THEN** an untitled conversation opens with the composer ready, and after the first reply its heading and list entry show the generated title

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on "Listening wall" and confirms
- **THEN** the entry disappears from the list; when the owner cancels instead, nothing changes

### Requirement: The conversation view is the homeowner's chat
The conversation view SHALL show the owner's messages and the replies in order as chat bubbles: replies aligned to the left, the owner's messages to the right, and forms, confirmations and question sets centred. Reply text SHALL be set in Commissioner and headings and speaker names in Oswald, served with the app, with a line height of at least 1.6 and space between paragraphs. A reply SHALL be rendered as formatted text — headings, bullet and numbered lists, tables, emphasis, inline code — with raw HTML shown as text and never rendered, and an image shown only when it points at one of the app's own routes. A fenced block marked `calc` SHALL be shown in a framed box set apart from the reply's text. A composer SHALL send one message as one turn, and the turn's refusal SHALL be shown in words next to the composer when the service refuses it. While a turn is running the composer SHALL be disabled and a waiting bubble SHALL stand in the reply position: left-aligned, rounded, with a 2 px border and animated dots, naming the specialist currently working ("Designer is working…") and updating as the turn moves on, or "The Foreman is working…" before a specialist is chosen. Under each reply the specialists that ran in that turn SHALL be listed by role name only. A reply's title event SHALL update the heading without a reload. The heading SHALL be editable in place; saving sends the new title and an empty title is refused in words.

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

#### Scenario: Rename in place
- **WHEN** the owner edits the heading to "Listening wall" and saves
- **THEN** the heading and the conversation list show "Listening wall"

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

## ADDED Requirements

### Requirement: Tools and Project open from a rail
The conversation view SHALL show a narrow rail to the left of the chat with a Tools icon and a Project icon, each with an accessible name. Choosing one SHALL open its panel as a flyout over the chat; choosing it again, choosing the other, pressing Escape or closing the flyout SHALL close or switch it. The chat SHALL use the full width when no flyout is open. The Project flyout SHALL carry the project panel unchanged, including its refresh while a build is queued or running.

#### Scenario: Open and close
- **WHEN** the owner clicks the Project icon and then presses Escape
- **THEN** the project panel opens over the chat and then closes, and the messages were not reflowed

#### Scenario: Switch
- **WHEN** the Tools flyout is open and the owner clicks the Project icon
- **THEN** the Tools flyout closes and the project panel opens

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
