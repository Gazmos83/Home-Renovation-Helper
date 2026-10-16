# help-center Specification

## Purpose
One help source for the Studio: the topics the Help page shows and the chat answers from, the default prompt for turning a furniture photo into a design file, and the read-only tool that lets the chat read the help.

## Requirements

### Requirement: Help lives in one source
The service SHALL ship one help source holding an ordered list of topics, each with a unique id, a title and its body, and optionally a prompt to copy and a download. The source SHALL be validated at startup; a malformed source, a duplicate topic id or an unknown field SHALL be refused naming the file and the problem. The help source SHALL hold at least these topics: preparing a blueprint or a sketch; files a conversation accepts; designing from a photo with the design file template; pieces and renders; conversations and rooms; how a piece is made. The owner SHALL be able to read the source through an owner-gated route; it SHALL hold no model, prompt of an agent, token or cost.

#### Scenario: Shipped source valid
- **WHEN** the service starts with the shipped help source
- **THEN** it loads, and the six topics are present in order

#### Scenario: Duplicate topic refused
- **WHEN** the help source holds two topics with the id `template`
- **THEN** startup refuses it naming the help file and the duplicate id

#### Scenario: Without a login
- **WHEN** the help route is called without the owner's session
- **THEN** it answers 401

### Requirement: The template topic guides a design from a photo
The design file template topic SHALL give these steps in order: download the import template; open a high-end AI chat that reads images; attach a photo of a piece of furniture the owner likes and the template, and paste the default extraction prompt; save the chat's reply as a `.json` file; attach that file to a new conversation in the Studio, confirm the room and then the import; revise the imported piece in the conversation like any other piece. It SHALL say that a field the template does not define is refused by name and that dimensions read from a photo are estimates to check before building.

The default extraction prompt SHALL ask the other chat to: fill in the attached template's `build` so that it describes the piece in the photo; follow the template's `guide` and use only the fields it names; give every size in whole millimetres, estimating from common furniture sizes when the photo shows none; keep the `kind`, `schema_version`, `units` and `guide` unchanged; add no room survey; and return the whole document as JSON alone, with no other text. The prompt SHALL be fixed text in the help source and SHALL NOT be editable from the developer pages.

#### Scenario: Steps listed
- **WHEN** the template topic is read
- **THEN** it lists the six steps in order and says photo dimensions are estimates

#### Scenario: Prompt asks for JSON alone
- **WHEN** the default extraction prompt is read
- **THEN** it asks for the filled template as JSON alone, in millimetres, using only the fields the guide names, with no survey

### Requirement: The chat reads the help through `read_help`
A non-toggleable `help` plugin SHALL give Intake a read-only `read_help` tool. With no topic it SHALL return every topic's id and title; with a topic id it SHALL return that topic's title, body and prompt as written in the help source, wrapped as retrieved content. An unknown topic id SHALL be refused naming the id and listing the valid ids. The tool SHALL write nothing.

#### Scenario: Topics listed
- **WHEN** Intake calls `read_help` with no topic
- **THEN** it receives the six topic ids and titles

#### Scenario: Topic read
- **WHEN** Intake calls `read_help` with the topic `template`
- **THEN** it receives the template topic's steps and the default extraction prompt exactly as the Help page shows them

#### Scenario: Unknown topic refused
- **WHEN** Intake calls `read_help` with the topic `pricing`
- **THEN** it is refused naming `pricing` and listing the valid topic ids

#### Scenario: Not toggleable
- **WHEN** the owner tries to switch the `help` plugin off for a conversation
- **THEN** it is refused naming the plugin as not toggleable
