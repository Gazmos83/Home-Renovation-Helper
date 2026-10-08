## MODIFIED Requirements

### Requirement: The conversation view shows the project's progress
The conversation view SHALL show a project panel with the bound piece, its latest version and build state, the progress steps (brief confirmed, piece created, built, draft or preview rendered, reviewed with open items, detail pass, final) each marked done or not, the next step the owner can ask for, the latest still when one exists and otherwise the screenshot, and the piece's open generator-extension requests. The panel SHALL NOT offer a link to a turntable viewer. The panel SHALL refresh while a build is queued or running, while a render of the latest version is queued or running, and after every turn. It SHALL show nothing when the service's progress read is refused other than the refusal's reason.

#### Scenario: After the first build
- **WHEN** the Builder's build of version 1 finishes while the view is open
- **THEN** the panel shows version 1 built with its screenshot, "built" done, and the next step as a draft render, without a reload

#### Scenario: Open review items
- **WHEN** the latest review of the piece has two open items
- **THEN** the panel shows "reviewed, 2 open" and links to the piece's page

#### Scenario: Turntable finished
- **WHEN** the draft turntable of version 1 finishes while the view is open
- **THEN** the panel shows the still and "draft" rendered without a reload, and shows no "Open the turntable viewer" link

### Requirement: A piece version can be inspected in 3D
The Studio SHALL have an owner-only page per piece version at `/pieces/<package-id>/versions/<n>`. For a built version it SHALL show the version's `model.glb` in a 3D view, with:
- **Camera:** free rotate and zoom with the mouse, and buttons for the Iso, Front, Side and Plan cameras.
- **Modes:** Workshop (lit), Blueprint (flat light with the parts' edges drawn) and Exploded. Exploded has a slider that moves each module away from the piece's centre, with its parts following. The direction comes from the module positions in the version's `spec.json`.
- **Layer switches:** one for each layer the version's `spec.json` names, plus `dimensions`. Switching a layer off hides exactly the meshes the layer map lists under it. A mesh the map does not name stays visible.
- **Overall dimensions:** W, H and D in mm from `spec.json` `overall`, drawn beside the model. Hidden in Exploded mode and when `dimensions` is off.
- **Scale:** a floor grid and a contact shadow.
- **Straight-on views:** `front.png`, `side.png` and `top.png`, when the version has them.

A Cut list tab SHALL show the version's parts (id, name, quantity, length, width, thickness, material, grain, banding, notes, module) and its hardware (id, item, quantity, notes), both read from `spec.json`. When the parts belong to more than one module, the tab SHALL offer a filter with "All" and one choice per module, in the order the parts first name them. Each module is labelled by its name from `spec.json` `module_names`, "Extra parts" for `extras`, and otherwise its id. Choosing a module SHALL show only that module's parts, with their count of rows and pieces. The parts table SHALL name each part's module by that same label. Hardware is not divided by module.

Every measurement on the page SHALL come from the version's own files. The 3D view SHALL be loaded only on this page and in a conversation's split view, and only once one of them is shown. The split view SHALL show the same inspector with the same controls and tabs.

A version that is not built SHALL show its build state instead of the 3D view. A version, or a file it lacks, SHALL be named in plain words rather than shown as an error code. The page SHALL NOT show a model name, prompt, token count or cost, and it SHALL pass a recorded browser check before it counts as done.

#### Scenario: Built version inspected
- **WHEN** the owner opens `/pieces/murphy-bed/versions/1`
- **THEN** the model is shown from the Iso camera with W 3000 mm, H 2900 mm and D 450 mm beside it, and the layer switches carcass, backs, shelves, fronts, extras and dimensions

#### Scenario: Front camera
- **WHEN** the owner presses Front
- **THEN** the view looks straight at the piece's front

#### Scenario: Exploded
- **WHEN** the owner chooses Exploded and moves the slider to its end
- **THEN** each module moves away from the centre along its own direction, and the dimension overlay is hidden

#### Scenario: Layer off
- **WHEN** the owner switches `fronts` off
- **THEN** every mesh the layer map lists under `fronts` is hidden and all others stay visible

#### Scenario: Cut list
- **WHEN** the owner opens the Cut list tab
- **THEN** every row of `spec.json` `parts` and `hardware` is listed with its figures

#### Scenario: Cut list filtered by module
- **WHEN** the owner opens the Cut list of `murphy-bed` version 2 and chooses "Left lower cabinet"
- **THEN** only the parts of module `left-base` are listed, with their row and piece counts, and choosing "All" lists every part again

#### Scenario: Version built before the views
- **WHEN** the owner inspects a version that has no `front.png`
- **THEN** the 3D view, the overlay and the cut list are shown and the straight-on views are left out

#### Scenario: Not built yet
- **WHEN** the owner opens a version whose build is running
- **THEN** the page says the version is building and shows no 3D view

#### Scenario: Conversation without the split view
- **WHEN** the owner opens a conversation and does not open the inspector
- **THEN** the 3D view is not loaded

### Requirement: The inspector is reachable from the Pieces page and the conversation
The Pieces page SHALL offer an "Inspect" link for every built version, opening the inspector page for that version. A conversation's project panel SHALL offer an "Inspect version N" button for the bound piece's latest version once it is built: a framed button with rounded corners in the Studio's button style, not a text link. It SHALL open the inspector for that version in the conversation's split view. A render notice's Review button SHALL open the same split view.

#### Scenario: Inspect from the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers "Inspect" and version 3 does not

#### Scenario: Inspect from the conversation
- **WHEN** the bound piece's version 1 has just been built
- **THEN** the panel shows an "Inspect version 1" button, and pressing it shows the inspector for version 1 beside the chat

### Requirement: The Pieces page shows renders and takes feedback
The Studio SHALL show the owner a Pieces page that lists the pieces, then each piece's versions, then each version's published renders, showing for each:
- its kind and tier;
- a preview image (the still, or the first frame);
- its current rating and comment, with controls to rate up, rate down, edit the comment and clear.

The page SHALL NOT offer a link to a render's viewer. The page SHALL show an API refusal next to the render it names. It SHALL NOT show model names, prompts, token counts or costs. It SHALL pass a recorded browser check before it counts as done.

#### Scenario: Rate a turntable
- **WHEN** the owner opens `hall-bench` v2 on the Pieces page and rates the `draft` turntable down with "too dark"
- **THEN** the page shows the down rating and the comment, and a reload shows the same

#### Scenario: No internals
- **WHEN** the Pieces page shows a render the Builder started
- **THEN** no model slug, prompt text or token figure appears on the page

#### Scenario: No viewer link
- **WHEN** a version has a published draft turntable
- **THEN** its render entry shows the preview image and the rating controls, and no "Open the turntable viewer" link

### Requirement: Tools and Project open from a rail
The conversation view SHALL show a narrow rail with a Tools icon and a Project icon, each with an accessible name. The rail SHALL sit at the left edge of the screen, below the header, outside the centred page, and SHALL stay visible while the page scrolls. The rail SHALL have an expand control: expanded, each icon is shown with its label ("Tools", "Project"); collapsed, only the icons are shown. The control SHALL say which it does and whether the rail is expanded. Choosing an icon SHALL open its panel as a flyout beside the rail, over the chat; choosing it again, choosing the other, pressing Escape or closing the flyout SHALL close or switch it. The chat SHALL use the full width beside the rail when no flyout is open. The Project flyout SHALL carry the project panel unchanged, including its refresh while a build or render is queued or running.

#### Scenario: Open and close
- **WHEN** the owner clicks the Project icon and then presses Escape
- **THEN** the project panel opens over the chat and then closes, and the messages were not reflowed

#### Scenario: Switch
- **WHEN** the Tools flyout is open and the owner clicks the Project icon
- **THEN** the Tools flyout closes and the project panel opens

#### Scenario: Scrolled conversation
- **WHEN** the owner scrolls a long conversation to its end
- **THEN** the rail is still shown at the left edge of the screen and its icons still open their panels

#### Scenario: Expanded
- **WHEN** the owner presses the expand control
- **THEN** the rail shows "Tools" and "Project" beside their icons; pressing it again shows the icons only

## ADDED Requirements

### Requirement: The Studio header stays at the top
The Studio's top header, with its navigation, SHALL stay at the top of the screen while any page scrolls, and SHALL not cover the content below it when the page is scrolled to its top.

#### Scenario: Long page
- **WHEN** the owner scrolls a long conversation down
- **THEN** the header and its links stay visible at the top of the screen

### Requirement: A render notice is shown in the conversation
The conversation view SHALL show each notice in the thread's history in its place among the messages, centred and framed like a confirmation, with its text. A finished render of a piece version SHALL show a Review button that names the render's tier: "Review <tier> v1" when the version is 1, and "Review <tier> revision <n>" for version n above 1, where the tier is `draft`, `preview` or `final`. Pressing it SHALL open the inspector for that piece version in the split view. A failed render's notice, and a notice for a shell or composition, SHALL show no button. A notice posted while the view is open SHALL appear without a reload while the project panel is following a render. A notice SHALL NOT show a model name, prompt, token count or cost.

#### Scenario: First draft ready
- **WHEN** the draft turntable of `hall-bench` version 1 finishes while the conversation is open
- **THEN** a notice appears without a reload, saying it is ready and can also be checked in the Project panel, with a "Review draft v1" button

#### Scenario: Later version
- **WHEN** a notice is shown for a finished draft render of `hall-bench` version 3
- **THEN** its button reads "Review draft revision 3"

#### Scenario: Preview and final
- **WHEN** notices are shown for a finished preview of `hall-bench` version 1 and a finished final of version 4
- **THEN** their buttons read "Review preview v1" and "Review final revision 4"

#### Scenario: Failed render
- **WHEN** a preview turntable of `hall-bench` version 2 fails
- **THEN** a notice says it did not finish and shows no button

### Requirement: A piece version is reviewed beside the conversation
The conversation view SHALL be able to show the inspector for one piece version beside the chat: on a wide screen the chat on one side and the inspector on the other, both visible at once; on a narrow screen the inspector below the chat. The conversation route SHALL use the full width of the screen for this. While the inspector is shown the owner SHALL still be able to read, scroll and send messages, and opening the inspector SHALL NOT start a turn. The inspector SHALL have a control to close it, after which the chat takes the width again. Opening another version SHALL replace the shown one. The open inspector SHALL be part of the page's address, so a reload shows it again. A version that is not built, or a file it lacks, SHALL be named in plain words as on the inspector page.

#### Scenario: Review from a notice
- **WHEN** the owner presses "Review draft v1" on a notice for `hall-bench` version 1
- **THEN** the inspector for `hall-bench` version 1 is shown beside the chat and the composer is still usable

#### Scenario: Ask about a detail
- **WHEN** the inspector is open and the owner sends "the left shelf looks too thin"
- **THEN** the message is sent as a normal turn and the inspector stays open

#### Scenario: Close
- **WHEN** the owner closes the inspector
- **THEN** the chat takes the full width beside the rail again

#### Scenario: Reload
- **WHEN** the owner reloads the conversation while the inspector shows `hall-bench` version 2
- **THEN** the conversation and the inspector for version 2 are shown again
