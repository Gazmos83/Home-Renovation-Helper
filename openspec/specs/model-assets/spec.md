# model-assets Specification

## Purpose
Keeps the owner's library of imported 3D models (bought furniture, decor) that room compositions place. Only GLB, glTF and OBJ files that have been checked are accepted, and they are stored and served safely.

## Requirements

### Requirement: The owner uploads a model with its real size
The owner SHALL be able to upload one model at a time with a name and its real width, depth and height in whole millimetres, and list, fetch and delete the library's models. Every model route SHALL require the owner's session.

The type SHALL be identified from the file's bytes, never from its name or declared type. Accepted forms SHALL be:
- a binary glTF (GLB, version 2);
- a zip holding exactly one `.gltf` file with its buffers and images;
- a zip holding exactly one `.obj` file with its `.mtl` and texture images.

Any other type, including a `.blend`, FBX, USD or STL file, SHALL be refused with 415. A file larger than the configured limit SHALL be refused with 413 without being stored in full.

#### Scenario: GLB accepted
- **WHEN** the owner uploads a 6 MB GLB armchair named `armchair` at 800 × 700 × 900 mm
- **THEN** the response carries a model id, its type `glb` and its stated size, and the library lists it as `checking`

#### Scenario: Blend file refused
- **WHEN** the uploaded bytes are a `.blend` file, whatever the file name says
- **THEN** it is refused with 415 and nothing is stored

#### Scenario: Too large
- **WHEN** the file exceeds the model size limit
- **THEN** it is refused with 413 and no partial file remains

### Requirement: Zips and references are safe
A zip SHALL be refused, naming the problem and nothing kept, when it:
- has an entry with an absolute path, a `..` segment, a drive letter or a symbolic link;
- has more entries than the configured limit;
- unpacks to more than the configured total size;
- has an entry whose extension is not one of `gltf`, `bin`, `obj`, `mtl`, `png`, `jpg`, `jpeg`;
- has no model file, or more than one.

Every buffer and image a glTF names, every `mtllib` an OBJ names and every texture map an MTL names SHALL be a relative path to a file inside the same upload, or, for glTF only, an embedded `data:` URI. Any `http:`, `https:`, `file:` or absolute reference SHALL be refused naming it. A GLB SHALL NOT reference any file outside itself.

#### Scenario: Path traversal
- **WHEN** a zip holds an entry `../../app/main.py`
- **THEN** it is refused naming the entry and nothing is unpacked

#### Scenario: Remote texture
- **WHEN** a glTF image's URI is `https://example.com/wood.png`
- **THEN** the upload is refused naming that URI

#### Scenario: Missing material file
- **WHEN** an OBJ's `mtllib` names a file the zip does not contain
- **THEN** the upload is refused naming the missing file

### Requirement: A model is checked once in headless Blender
After upload, a model SHALL be imported once in headless Blender, under the one-process rule and the Blender timeout, without rendering. It SHALL become `ready` with its measured size and triangle count, or `refused` with the reason when the import fails, it yields no mesh, or it exceeds the configured triangle limit. Only a `ready` model SHALL be placeable.

#### Scenario: Ready
- **WHEN** the check imports the armchair GLB and finds 40 000 triangles
- **THEN** the model reads `ready` with its measured size and triangle count

#### Scenario: Too heavy
- **WHEN** a model has more triangles than the limit
- **THEN** it reads `refused` naming the count and the limit, and a composition naming it is refused

#### Scenario: Not yet checked
- **WHEN** a composition names a model still `checking`
- **THEN** the composition is refused saying the model is not ready yet

### Requirement: Models are stored by id, never in conversation state
A model SHALL be stored under the configured upload root in a folder named by its id. Its files SHALL be served only through owner-gated routes, by id and exact relative name, with a fixed content type and `nosniff`. Conversation state SHALL hold model ids only. A model placed in any composition version SHALL NOT be deletable. The refusal SHALL name the compositions that use it.

#### Scenario: Delete in use
- **WHEN** the owner deletes `armchair` while `Wohnen` v2 places it
- **THEN** the delete is refused naming `Wohnen` v2, and the model is kept
