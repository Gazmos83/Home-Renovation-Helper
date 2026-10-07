# price-list Specification

## Purpose
Defines the one supplier price list: what an entry holds, where its price came from, the three lawful ways an entry is made, the owner's override, refreshing a captured price, and the boundary on which retailers may be read.

## Requirements

### Requirement: An entry states its price and where it came from
Each price-list entry SHALL have a unique key, a label, a category (`panel`, `hardware`, `finish`, `edge_band`, `cut_service`, `delivery`), a unit (`per_m2`, `per_piece`, `per_metre`, `per_cut`), sheet length, width and thickness for a panel, an optional bundle length for edge band, a base price in cents with its provenance — `captured` (with the URL and time it was read), `manual` or `snapshot` (with the snapshot it came from) — and optionally an owner override in cents with a note and time. The effective price SHALL be the override when one is set, else the base price; both SHALL remain readable. Every price SHALL be stated in euro cents, never estimated.

#### Scenario: Override shown beside the captured price
- **WHEN** the owner overrides a captured 39.99 EUR panel at 35.00 EUR
- **THEN** the entry reads effective 3500, captured 3999 with its URL and time, and the override with its note

#### Scenario: A panel without a sheet size
- **WHEN** a panel entry is made without its sheet length, width or thickness
- **THEN** it is refused naming the missing dimension

### Requirement: A toom product URL becomes an entry in one step
Given a toom product URL, the service SHALL check robots.txt for its own stated identity, fetch the page once, parse the product name, price, unit and, for panels, sheet dimensions, and create a `captured` entry with the parsed values and the given key and category, adding the page's text to the catalog corpus in the same step. A URL outside the configured retail sources SHALL be refused naming the host; a robots refusal, 401, 403 or 429 SHALL be reported as a refusal and SHALL NOT be retried under another identity; a page whose price cannot be parsed SHALL create nothing and say what was missing.

#### Scenario: Pasted URL
- **WHEN** the owner pastes a toom product URL for an 18 mm birch plywood sheet
- **THEN** an entry exists with the captured price, the URL and time, the sheet size, and the page's chunks are in the corpus

#### Scenario: Another retailer
- **WHEN** the URL is on bauhaus.info
- **THEN** it is refused naming the host as not a permitted source and nothing is fetched

#### Scenario: Forbidden
- **WHEN** toom answers 403
- **THEN** the response reports the refusal and no entry is created

### Requirement: Entries can be made by hand and from a snapshot
The owner SHALL be able to create a `manual` entry with key, label, category, unit, price and the dimensions its category needs, and to record a manual snapshot of a product page (retailer, URL, product name, price, currency, availability, specification text, the date seen); a snapshot SHALL be added to the corpus as dated reference material and MAY prefill a `snapshot` entry with its price. A snapshot dated in the future SHALL be refused.

#### Scenario: Manual edge band entry
- **WHEN** the owner adds `band:oak-22` at 1.20 EUR per metre with a 25 m bundle
- **THEN** the entry exists with provenance `manual`

#### Scenario: Snapshot prefills an entry
- **WHEN** the owner records a snapshot of a page the crawl cannot reach and asks it to prefill an entry
- **THEN** a `snapshot` entry exists whose price and URL come from the snapshot, and the snapshot is searchable in the corpus

### Requirement: Refresh re-reads a captured price and never touches the override
Refreshing a `captured` entry SHALL re-fetch its URL under the same robots and refusal rules and update only the captured price and time, reporting `ok`, `refused`, `timeout`, `unfetchable` or `unreadable`; the override SHALL be unchanged. Refreshing a `manual` or `snapshot` entry SHALL be refused as having no source to read. Refresh and URL capture SHALL be rate-limited.

#### Scenario: Price rose
- **WHEN** a captured entry with an override is refreshed and toom now shows a higher price
- **THEN** the captured price and time change and the override and effective price do not

### Requirement: An entry used by a pricing cannot be deleted
An entry referenced by any stored pricing SHALL NOT be deleted; other entries MAY be deleted by the owner.

#### Scenario: Used entry
- **WHEN** the owner deletes an entry a stored pricing used
- **THEN** it is refused naming the pricing
