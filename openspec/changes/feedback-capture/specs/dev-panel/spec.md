## ADDED Requirements

### Requirement: Feedback is readable per slot, model and tier
The developer SHALL be able to read the render-feedback summary (up and down counts and latest comment time, grouped by slot, model and tier), and the comments of one group newest first, behind the developer gate. Renders started outside an agent turn SHALL be grouped under no slot and no model. Reading feedback SHALL NOT change routing.

#### Scenario: Ungrouped HTTP renders
- **WHEN** a still started through the renders route is rated up
- **THEN** the summary counts it in a row with no slot and no model at its tier
