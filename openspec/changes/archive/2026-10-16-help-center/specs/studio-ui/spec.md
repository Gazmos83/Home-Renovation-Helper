## MODIFIED Requirements

### Requirement: A help page explains how to prepare a blueprint
The Studio SHALL have a help page, linked from the navigation, that shows every topic of the help source in the help source's order. Each topic SHALL show only its title at first, with a control that expands it to reveal the rest and collapses it again; every topic SHALL start collapsed. The text SHALL come from the help source, so that the page and the chat show the same words.

The blueprint topic SHALL explain how to prepare a blueprint or a hand sketch for Intake and list the measurements Intake needs: each room's name; the length of every wall, edge by edge in one direction around the room; every corner angle that is not 90°; the ceiling height; the wall thickness; every door and window with the wall it is on, its offset from that wall's starting corner, its width, its height and (for a window) its sill height; a scale reference (a dimension line, a printed area or a known door width); and that all rooms of one apartment are drawn in one plan frame. It SHALL keep the worked example of one room. The files topic SHALL say which file types the conversation accepts.

The design file template topic SHALL offer the import template as a download, give the steps for using it, and show the default extraction prompt with a Copy button that copies the prompt exactly. The workflow topic SHALL show a diagram of how a piece is made, with the template import as a branch into the Designer, and a text alternative that names every step. The Pieces page SHALL keep its own template download.

#### Scenario: Help reached
- **WHEN** the owner opens Help from the navigation
- **THEN** every topic shows its title only, and none of its text is visible

#### Scenario: Topic expanded
- **WHEN** the owner expands the blueprint topic
- **THEN** it lists the measurements above, and the other topics stay collapsed

#### Scenario: Files topic
- **WHEN** the owner expands the files topic
- **THEN** it says plans and photos are PNG or JPEG, notes are Markdown or plain text, and designs are a `.json` design file

#### Scenario: Template downloaded from Help
- **WHEN** the owner expands the template topic and chooses the download
- **THEN** the import template is downloaded as `import-template.json` from the owner-gated route

#### Scenario: Prompt copied
- **WHEN** the owner chooses Copy beside the default extraction prompt
- **THEN** the clipboard holds the prompt exactly as the help source states it, and the button confirms the copy

#### Scenario: Workflow diagram
- **WHEN** the owner expands the workflow topic
- **THEN** a diagram shows wish → Intake confirms → Designer drafts → owner confirms → Builder blockout → draft turntable → Reviewer → revise → optional detail pass → final after a typed "yes", with the template import joining at the Designer, and a screen reader reads the same steps

#### Scenario: Help unavailable
- **WHEN** the help source cannot be loaded
- **THEN** the page says the help could not be loaded, and no topic is shown
