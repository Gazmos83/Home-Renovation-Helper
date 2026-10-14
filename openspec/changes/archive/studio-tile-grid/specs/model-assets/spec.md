## ADDED Requirements

### Requirement: A model has an optional preview picture
A model SHALL have at most one preview picture. The owner's session SHALL be able to store one and fetch it by the model's id. Storing it SHALL replace any earlier picture of that model. The picture SHALL be accepted only when:
- the model exists and reads `ready` (otherwise 409, naming its state);
- its bytes are a PNG, identified from the bytes, never from a declared type (otherwise 415);
- it is at most 256 KB (otherwise 413, without being stored in full);
- its width and height are each from 1 to 512 pixels (otherwise 422, naming the size).

A refused picture SHALL leave any earlier picture in place. The picture SHALL be stored apart from the model's uploaded files: it SHALL NOT be listed among them, SHALL NOT be reachable through the model-file route, and an uploaded file of any name SHALL NOT replace it. It SHALL be served only as `image/png` with `nosniff`. A model without a picture SHALL answer 404. A model's read and list entries SHALL say whether it has a picture, and SHALL name the model's entry file so the owner's browser can load the model to draw it. Deleting a model SHALL delete its picture. Storing a picture SHALL NOT start Blender, change the model's state or affect whether it can be placed.

#### Scenario: Picture stored
- **WHEN** the owner stores a 384 × 384 PNG of 60 KB for the ready model `Sofa`
- **THEN** it is accepted, `Sofa` reads as having a picture, and fetching it returns that PNG as `image/png`

#### Scenario: Not ready
- **WHEN** the owner stores a picture for a model still `checking`
- **THEN** it is refused with 409 naming `checking`, and nothing is stored

#### Scenario: Not a PNG
- **WHEN** the stored bytes are a JPEG or an SVG, whatever the request says
- **THEN** it is refused with 415 and any earlier picture is kept

#### Scenario: Too large
- **WHEN** the picture is 2048 × 2048 pixels
- **THEN** it is refused with 422 naming the size

#### Scenario: Kept apart from the upload
- **WHEN** a zip model holds its own `thumbnail.png` texture and a preview picture is stored for it
- **THEN** the model's file list and its `thumbnail.png` texture are unchanged, and the preview picture is fetched only from the picture route

#### Scenario: No picture
- **WHEN** the owner fetches the picture of a model that has none
- **THEN** the answer is 404

#### Scenario: Deleted with the model
- **WHEN** the owner deletes `Sofa`
- **THEN** its picture is gone as well

#### Scenario: Signed out
- **WHEN** a request without the owner's session fetches or stores a picture
- **THEN** it is refused as for every other model route
