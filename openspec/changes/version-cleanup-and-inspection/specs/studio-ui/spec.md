## ADDED Requirements

### Requirement: A version is deleted from the Pieces page and the Project panel after "Are you sure?"
The Pieces page SHALL offer "Delete version N" for the version shown. The Project panel SHALL offer "Delete version N" for the latest version. Neither SHALL offer it for an approved version.

Pressing it SHALL NOT delete anything yet. It SHALL show, in place, "Are you sure? Version N and its renders, reviews and pricings will be deleted. This cannot be undone." with "Yes, delete version N" and "Cancel" buttons. When N is the piece's only version, the question SHALL say that the whole piece will be deleted.

Only "Yes" SHALL send the delete. Afterwards:
- the Pieces page SHALL show the piece's remaining versions, or drop the piece when it has none left;
- the Project panel SHALL refresh;
- an inspector showing the deleted version SHALL close.

A refusal SHALL be shown with its reason next to the control. The Project panel SHALL show "N of 15 versions" once the piece holds 13 or more.

#### Scenario: Confirmed delete on the Pieces page
- **WHEN** the owner shows `hall-bench` version 2, presses "Delete version 2", then "Yes, delete version 2"
- **THEN** version 2 is no longer among the piece's version buttons and the page shows another version

#### Scenario: Cancelled
- **WHEN** the owner presses "Delete version 2" and then "Cancel"
- **THEN** nothing is deleted and the delete control is shown again

#### Scenario: Approved version has no delete
- **WHEN** the owner shows `hall-bench` version 4, which is approved
- **THEN** no "Delete version 4" control is shown

#### Scenario: Refusal shown
- **WHEN** the owner confirms deleting a version that a composition places
- **THEN** the refusal naming the composition is shown next to the control and the version stays listed

#### Scenario: Near the limit
- **WHEN** the conversation's piece holds 14 versions
- **THEN** the Project panel shows "14 of 15 versions"

### Requirement: Piece titles do not carry the version
The Project panel's header line SHALL show the piece's name, its id and its build state, without "version N". The heading of the inspector beside the chat SHALL show the piece's name, or its id when the name cannot be read, without the version. Its version buttons already show which version is open. Lines and buttons that act on one version SHALL keep its number, such as "Approve version 14", "Inspect version 14" and "Delete version 14".

#### Scenario: Project panel header
- **WHEN** the conversation's piece is `listening-wall`, named "Listening wall", at version 14
- **THEN** the panel's header reads "Listening wall" with the id `listening-wall` and contains no "version 14"

#### Scenario: Inspector heading
- **WHEN** the inspector beside the chat shows `listening-wall` version 14
- **THEN** its heading reads "Listening wall" and the version buttons mark version 14 as shown

### Requirement: A build notice is shown with an Inspect button
The conversation view SHALL show each build notice in its place among the messages, framed like a render notice. A finished build's notice SHALL show an "Inspect version N" button that opens the inspector for that piece version beside the chat. A failed build's notice, and a notice whose version was deleted, SHALL show no button. A build notice posted while the view is open SHALL appear without a reload while the Project panel is following a build. It SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: Built while open
- **WHEN** `hall-bench` version 2 finishes building while its conversation is open
- **THEN** a notice saying version 2 is built appears without a reload, with an "Inspect version 2" button

#### Scenario: Inspect from the notice
- **WHEN** the owner presses "Inspect version 2" on that notice
- **THEN** the inspector for `hall-bench` version 2 is shown beside the chat and the composer is still usable

#### Scenario: Failed build
- **WHEN** the build of `hall-bench` version 3 fails
- **THEN** its notice says it did not build and shows no button

### Requirement: The exploded view labels each module's size
In Exploded mode, the inspector SHALL show one label per module that `spec.json` `modules` names. Each label SHALL give the module's name from `module_names`, or its id when it has no name, and its width × height × depth in mm, for example "Left lower cabinet 600 × 720 × 560 mm". The figures SHALL come from the version's own `spec.json`. Each label SHALL sit at its module and move with it as the explode slider moves. The labels SHALL follow the `dimensions` layer switch. The overall dimensions SHALL stay hidden in Exploded mode. A version whose `spec.json` has no `modules` SHALL show no labels and SHALL NOT show an error.

#### Scenario: Labels when exploded
- **WHEN** the owner inspects `murphy-bed` version 2 and chooses Exploded
- **THEN** every module shows a label with its name and W × H × D in mm, and the overall dimensions are hidden

#### Scenario: Labels follow the slider
- **WHEN** the owner moves the explode slider
- **THEN** each label moves with its module

#### Scenario: Dimensions off
- **WHEN** the owner switches `dimensions` off in Exploded mode
- **THEN** no module labels are shown

#### Scenario: Not exploded
- **WHEN** the owner chooses Workshop
- **THEN** no module labels are shown and the overall dimensions are drawn as before
