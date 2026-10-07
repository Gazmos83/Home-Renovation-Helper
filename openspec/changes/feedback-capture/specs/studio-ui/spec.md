## ADDED Requirements

### Requirement: The Pieces page shows renders and takes feedback
The Studio SHALL show the owner a Pieces page that lists the pieces, then each piece's versions, then each version's published renders, showing for each:
- its kind and tier;
- a preview image (the still, or the first frame);
- a link to its viewer;
- its current rating and comment, with controls to rate up, rate down, edit the comment and clear.

The page SHALL show an API refusal next to the render it names. It SHALL NOT show model names, prompts, token counts or costs. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Rate a turntable
- **WHEN** the owner opens `hall-bench` v2 on the Pieces page and rates the `draft` turntable down with "too dark"
- **THEN** the page shows the down rating and the comment, and a reload shows the same

#### Scenario: No internals
- **WHEN** the Pieces page shows a render the Builder started
- **THEN** no model slug, prompt text or token figure appears on the page

### Requirement: The developer panel shows feedback
The developer route tree SHALL include a Feedback page listing the per slot, model and tier rating counts, and the comments of a selected group. Like the other developer pages, it SHALL be reachable only when the developer API answers, and SHALL pass a recorded browser check before it counts as done.

#### Scenario: Feedback page
- **WHEN** the developer opens the Feedback page after ratings exist
- **THEN** each slot and model row shows its up and down counts per tier, and selecting a row lists its comments newest first
