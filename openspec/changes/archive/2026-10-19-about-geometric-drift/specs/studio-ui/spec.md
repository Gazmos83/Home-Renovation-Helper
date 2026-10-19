## MODIFIED Requirements

### Requirement: An About page explains the app in plain words
A signed-in owner SHALL reach an About page at `/about` from an "About" link in the header and in the footer. The page SHALL explain, with no technical terms (no model, prompt, token, frame, resolution or engine names):
- that the app makes 3D pictures of furniture and rooms on an ordinary, low-powered computer;
- that pieces are improved by revising them with an AI assistant;
- that a revised piece can be downloaded to add to an existing house model, or placed in a room in the app;
- that every picture is drawn from the piece's exact measurements, so a piece's shape does not drift between pictures and changes only when the owner asks.

The About page SHALL NOT list the crew; the crew is on the crew page at `/crew`. Opening `/about` signed out SHALL show the same About page under the marketing page's top bar, reached from its "About" link; Help SHALL stay owner-only.

#### Scenario: About from the header
- **WHEN** the signed-in owner clicks "About" in the header
- **THEN** the About page opens and explains the four points in plain words

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

#### Scenario: Measurements stay put
- **WHEN** the owner reads the About page
- **THEN** its last section, "Your measurements stay put", says in plain words that pictures are drawn from the piece's exact measurements and that the shape changes only when the owner asks
