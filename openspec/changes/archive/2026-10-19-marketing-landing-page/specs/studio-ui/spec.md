## MODIFIED Requirements

### Requirement: The Studio is an owner-only single-page app
The Studio SHALL be a client-rendered single-page app served separately from the API, calling it with the session cookie; an unauthenticated visit SHALL show the sign-in page, except a visit to `/`, which SHALL show the marketing page, and a visit to `/crew`, which SHALL show the crew page, and a 401 from any call SHALL return the owner to the sign-in page. The homeowner pages SHALL NOT show model names, prompts, token counts or costs of model calls.

#### Scenario: Not signed in
- **WHEN** the owner opens the price list without a session
- **THEN** the sign-in page is shown and, after signing in, the price list

#### Scenario: Root address signed out
- **WHEN** someone who is not signed in opens `/`
- **THEN** the marketing page is shown, not the sign-in page

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

## ADDED Requirements

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
