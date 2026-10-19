## MODIFIED Requirements

### Requirement: An About page explains the app in plain words
A signed-in owner SHALL reach an About page at `/about` from an "About" link in the header and in the footer. The page SHALL explain, with no technical terms (no model, prompt, token, frame, resolution or engine names):
- that the app makes 3D pictures of furniture and rooms on an ordinary, low-powered computer;
- that pieces are improved by revising them with an AI assistant;
- that a revised piece can be downloaded to add to an existing house model, or placed in a room in the app;
- that every picture is drawn from the piece's exact measurements, so a piece's shape does not drift between pictures and changes only when the owner asks;
- that design and engineering advice is checked against rules from published guidelines, shows the rule, the measurement and the source, says when it cannot be sure, and names what still needs a qualified person's check;
- that a piece is priced from the DIY store's real prices, with boards fitted to waste little and offcuts used first, and that a missing price is named rather than made up.

The page text SHALL be centred. Each point SHALL be a box with its own icon above its heading, in a grid of three boxes per row on a wide screen, two on a medium one and one on a phone, with no sideways scroll.

The About page SHALL NOT list the crew; the crew is on the crew page at `/crew`. Opening `/about` signed out SHALL show the same About page under the marketing page's top bar, reached from its "About" link; Help SHALL stay owner-only.

#### Scenario: About from the header
- **WHEN** the signed-in owner clicks "About" in the header
- **THEN** the About page opens and explains the six points in plain words

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

#### Scenario: Advice you can check
- **WHEN** the owner reads the About page
- **THEN** a section, "Advice you can check", says in plain words that advice names its rule and source, says when it cannot be sure, and names what needs a qualified person's check, and it claims no certification

#### Scenario: Stick to your budget
- **WHEN** the owner reads the About page
- **THEN** its last section, "Stick to your budget", says in plain words that pieces are priced from the store's real prices and that a missing price is named, not made up, and it does not claim the app keeps a piece within the budget

#### Scenario: Boxed points with icons
- **WHEN** the owner opens the About page on a wide screen
- **THEN** the six points are centred boxes, each with an icon, in two rows of three
