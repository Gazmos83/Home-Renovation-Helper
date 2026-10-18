## MODIFIED Requirements

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

## ADDED Requirements

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

Opening `/about` signed out SHALL show the sign-in page.

#### Scenario: About from the header
- **WHEN** the signed-in owner clicks "About" in the header
- **THEN** the About page opens and explains the three points in plain words

#### Scenario: Header links
- **WHEN** the owner is signed in and looks at the header navigation
- **THEN** its links are "Little Homey", "Help" and "About", in that order, followed by "Sign out"

#### Scenario: Header layout
- **WHEN** the owner is signed in and looks at the header
- **THEN** "Little Homey" with its icon is at the left edge, and "Help", "About" and "Sign out" are together at the right edge

#### Scenario: Signed out
- **WHEN** someone who is not signed in opens `/about`
- **THEN** the sign-in page is shown

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
