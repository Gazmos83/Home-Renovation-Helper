# plan-uploads Specification

## Purpose
Defines how the owner hands the agents a blueprint or a room photo: uploading it to a conversation, how it is checked and stored, and how a turn attaches it so Intake can read it.

## Requirements

### Requirement: Plans and photos are uploaded to a thread
The owner SHALL be able to upload one image file at a time to a conversation thread and list and fetch that thread's uploads. Only PNG and JPEG SHALL be accepted, identified from the file's bytes and never from its name or declared type. A file larger than the configured limit SHALL be refused with 413 without being stored in full, an unsupported type with 415, and an upload beyond the per-thread count with 409. Every upload route SHALL require the owner's session.

#### Scenario: Blueprint uploaded
- **WHEN** the owner uploads a 2 MB JPEG blueprint to a thread
- **THEN** the response carries an upload id, its type and size, and the thread's upload list includes it

#### Scenario: A PDF renamed to .png
- **WHEN** the uploaded bytes are a PDF whatever the file name says
- **THEN** it is refused with 415 and nothing is stored

#### Scenario: Too large
- **WHEN** the file exceeds the size limit
- **THEN** it is refused with 413 and no partial file remains

### Requirement: Uploads are stored on disk, never in conversation state
An upload SHALL be stored under the configured upload root, named by its id, and served back only by its id through the owner-gated route with a fixed content type and `nosniff`. Conversation state and checkpoints SHALL hold the upload's id, never its bytes.

#### Scenario: Checkpoint size
- **WHEN** a turn attaches a 2 MB photo
- **THEN** the stored conversation holds the upload id and not the image data

### Requirement: A turn may attach uploads
A turn SHALL accept up to the configured number of upload ids belonging to the same thread. The specialist that answers SHALL receive each attached image with the owner's message; an id that does not belong to the thread SHALL be refused with 422 and no turn runs. A specialist whose slot is not image-capable SHALL receive a note that images were attached and not the images.

#### Scenario: Photo with the message
- **WHEN** the owner sends "this is the hall" with one photo attached
- **THEN** Intake's model call contains the text and the image

#### Scenario: Someone else's upload id
- **WHEN** a turn names an upload id from another thread
- **THEN** the turn is refused with 422 naming the id
