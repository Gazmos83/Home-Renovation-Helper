# plan-uploads Specification

## Purpose
Defines how the owner hands the agents a blueprint or a room photo: uploading it to a conversation, how it is checked and stored, and how a turn attaches it so Intake can read it.

## Requirements

### Requirement: Plans and photos are uploaded to a thread
The owner SHALL be able to upload one file at a time to a conversation thread and list and fetch that thread's uploads. PNG and JPEG images and design files SHALL be accepted, identified from the file's bytes and never from its name or declared type. A file is:
- an image when its bytes start with the PNG or JPEG signature;
- a design file when it decodes entirely as UTF-8 to a JSON object whose `kind` is `custom_build` or `package_import`.

A design file SHALL be refused with 413 above its own, smaller size limit. A file larger than the configured limit SHALL be refused with 413 without being stored in full, any other type with 415, and an upload beyond the per-thread count with 409. Every upload route SHALL require the owner's session.

#### Scenario: Blueprint uploaded
- **WHEN** the owner uploads a 2 MB JPEG blueprint to a thread
- **THEN** the response carries an upload id, its type and size, and the thread's upload list includes it

#### Scenario: A PDF renamed to .png
- **WHEN** the uploaded bytes are a PDF whatever the file name says
- **THEN** it is refused with 415 and nothing is stored

#### Scenario: Too large
- **WHEN** the file exceeds the size limit
- **THEN** it is refused with 413 and no partial file remains

#### Scenario: Design file uploaded
- **WHEN** the owner uploads `wall-unit.json` holding a custom-build document
- **THEN** the response carries an upload id with type `design`, and the thread's upload list includes it

#### Scenario: JSON that is not a design
- **WHEN** the uploaded bytes are a JSON array, or a JSON object whose `kind` is `room_scene`
- **THEN** it is refused with 415 and nothing is stored

### Requirement: Uploads are stored on disk, never in conversation state
An upload SHALL be stored under the configured upload root, named by its id, and served back only by its id through the owner-gated route with a fixed content type (`application/json` for a design file) and `nosniff`. Conversation state and checkpoints SHALL hold the upload's id, never its bytes.

#### Scenario: Checkpoint size
- **WHEN** a turn attaches a 2 MB photo
- **THEN** the stored conversation holds the upload id and not the image data

#### Scenario: Design served as JSON
- **WHEN** the owner fetches an uploaded design file by its id
- **THEN** it is served as `application/json` with `nosniff`

### Requirement: A turn may attach uploads
A turn SHALL accept up to the configured number of upload ids belonging to the same thread, of which at most one is a design file. An id that does not belong to the thread SHALL be refused with 422 and no turn runs, and so SHALL a second design file in one turn.

The specialist that answers SHALL receive each attached image with the owner's message. A specialist whose slot is not image-capable SHALL receive a note that images were attached and not the images. An attached design file SHALL never be sent to a model: the answering specialist SHALL receive a note naming the file and its upload id.

#### Scenario: Photo with the message
- **WHEN** the owner sends "this is the hall" with one photo attached
- **THEN** Intake's model call contains the text and the image

#### Scenario: Someone else's upload id
- **WHEN** a turn names an upload id from another thread
- **THEN** the turn is refused with 422 naming the id

#### Scenario: Design named, not sent
- **WHEN** the owner sends "import this" with `wall-unit.json` attached
- **THEN** the Designer's model call contains the text and a note naming `wall-unit.json` and its upload id, and not the document's contents
