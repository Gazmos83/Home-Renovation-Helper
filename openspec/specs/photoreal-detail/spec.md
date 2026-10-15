# photoreal-detail Specification

## Purpose
Defines ladder step 3 for furniture: a confirmed detail pass on a copy of a built version in the owner's live Blender, driven by the Lighting & materials specialist through allow-listed scripts, checked with viewport screenshots, logged, and never written back to the spec.

## Requirements

### Requirement: A detail pass starts only after the owner confirms
Starting a detail pass SHALL pause for the owner's confirmation, naming the piece and version and stating that the file open in the live Blender will be replaced. On `yes`, the service SHALL copy the version's `model.blend` to the version's `detail/detail.blend` when no copy exists yet, keep an existing copy so a later pass continues the earlier one, and open that copy in the live Blender. The version's `model.blend`, `spec.json` and cut list SHALL NOT be modified. A version without a successful build SHALL be refused, saying it must be built first.

#### Scenario: First pass
- **WHEN** the owner confirms a detail pass on `hall-bench` v2
- **THEN** `v2/detail/detail.blend` exists as a copy of `v2/model.blend`, the live Blender has it open, and `v2/model.blend` is byte-identical to before

#### Scenario: Declined
- **WHEN** the owner answers `no` to the pass confirmation
- **THEN** nothing is copied and nothing is sent to Blender

#### Scenario: Not built
- **WHEN** a detail pass is asked for a version whose build has not succeeded
- **THEN** it is refused saying the version must be built first

### Requirement: Every script passes the allow-list before the socket
Every script sent to the live Blender, whether the Lighting specialist wrote it or the service did, SHALL be checked before it is sent. Scripts SHALL be refused naming the first offending construct and its line when they:
- do not parse, or exceed 20 000 characters;
- import any module other than `bpy`, `bmesh`, `mathutils`, `math` or `random`;
- call `open`, `exec`, `eval`, `compile`, `__import__`, `getattr`, `setattr`, `delattr`, `globals`, `locals` or `vars`;
- access a dunder attribute;
- reach Blender text blocks, libraries, application handlers or timers, preferences, add-ons or file load/save methods;
- use `bpy.ops` other than as a direct call into the mesh, object, material, node, uv or transform operators, an argument-free `bpy.ops.wm.save_mainfile()`, or `bpy.ops.wm.open_mainfile` with anything other than a single string-literal path equal to the pass's `detail.blend`.

A refused script SHALL NOT be sent. Scripts that only use `bpy.data`, modifiers, material and world node trees, and render settings SHALL be allowed.

#### Scenario: Subprocess import refused
- **WHEN** a script contains `import subprocess`
- **THEN** it is refused naming `subprocess` and its line, and nothing is sent to Blender

#### Scenario: Render operator refused
- **WHEN** a script calls `bpy.ops.render.render(write_still=True)`
- **THEN** it is refused naming `bpy.ops.render.render`

#### Scenario: Aliased text block refused
- **WHEN** a script assigns `d = bpy.data` and then uses `d.texts.new("x")`
- **THEN** it is refused naming `texts`

#### Scenario: Save with a path refused
- **WHEN** a script calls `bpy.ops.wm.save_mainfile(filepath="/tmp/x.blend")`
- **THEN** it is refused naming `bpy.ops.wm.save_mainfile`

#### Scenario: Opening the pass's file allowed
- **WHEN** the service sends `bpy.ops.wm.open_mainfile(filepath="<the pass's detail.blend>")`
- **THEN** it is allowed and sent

#### Scenario: Opening another file refused
- **WHEN** a script calls `bpy.ops.wm.open_mainfile` with the version's `model.blend` path, or with a path held in a variable
- **THEN** it is refused naming `bpy.ops.wm.open_mainfile`

#### Scenario: Material script allowed
- **WHEN** a script creates a material with a Principled BSDF node, sets its base colour and roughness, and assigns it to an object through `bpy.data`
- **THEN** it is allowed and sent

### Requirement: The live socket never competes with a headless job
The service SHALL refuse any live Blender command while a headless Blender job is running, saying a Blender job is running and to try again when it finishes. It SHALL hold the one-process lock for the duration of each live command, so a headless job requested meanwhile waits. It SHALL connect only to a loopback address, and SHALL report a refused connection as Blender not being open with the MCP addon. Before each agent-written script, the service SHALL check that the live Blender still has the pass's `detail.blend` open. Otherwise the script SHALL NOT run, and the agent SHALL be told the pass was interrupted.

#### Scenario: Build running
- **WHEN** a headless build is running and the Lighting specialist sends an allowed script
- **THEN** the script is refused saying a Blender job is running, and nothing is sent

#### Scenario: Blender closed
- **WHEN** nothing listens on the live port and a script is sent
- **THEN** the reply says Blender is not open with the MCP addon

#### Scenario: Owner opened another file
- **WHEN** the live Blender's open file is not the pass's `detail.blend`
- **THEN** the script is not run and the agent is told the pass was interrupted

### Requirement: Progress is checked with viewport screenshots
A detail screenshot SHALL capture the live viewport at no more than 800 pixels wide into the version's `detail/screens/` folder under a name chosen by the service, numbered in order. The screenshot SHALL be available to the owner through the version's file route, and SHALL NOT be a render or need a tier. Screenshots SHALL NOT be sent to the Lighting specialist's model, which is text-only; after each script it SHALL instead receive a text report of the scene (objects, materials and modifiers, world and lights).

#### Scenario: Screenshot after a material change
- **WHEN** the Lighting specialist takes a screenshot after an allowed script
- **THEN** a new numbered PNG exists under `detail/screens/` and the owner can open it

#### Scenario: Agent sees text only
- **WHEN** the Lighting specialist's model is called after a screenshot was taken
- **THEN** the call contains the scene report as text and no image

### Requirement: Every live script is logged
Every script sent to the live Blender SHALL be recorded in the version's detail log with the time, the agent's stated purpose, the code, the allow-list verdict (with construct and line when refused), the outcome (ok, or the addon's error) and the duration. The same fields except the code SHALL be recorded as a tracing event when tracing is configured, and a tracing failure SHALL NOT affect the pass. Addon output and errors SHALL reach the model only as delimited untrusted content.

#### Scenario: Refused script logged
- **WHEN** a script is refused by the allow-list
- **THEN** the log holds its code, verdict `refused` with the construct and line, and no outcome

### Requirement: Step 3 never writes back to the spec
Nothing a detail pass produces SHALL change the package's spec, cut list, pricing input or any version record. The Lighting specialist SHALL bind only the detail-pass tools. It SHALL NOT create or revise a piece, record a brief or start a non-detail render. When asked for a change of size or construction, it SHALL say the Designer makes that change.

#### Scenario: Owner asks for a wider bench during a pass
- **WHEN** the owner tells the Lighting specialist to make the bench 100 mm wider
- **THEN** the reply says the Designer changes dimensions, and no detail script changes geometry for it

### Requirement: The Lighting specialist offers the detail render's choices
When the owner asks for a final image of the detail pass, the Lighting & materials specialist SHALL render a detail still unless the owner asks for a turntable. When the owner asks for a detail turntable, the specialist SHALL offer the choices in plain words before asking for it:
- a detail still now;
- the turntable on the laptop, with its estimate;
- the turntable on the render server, when finals go there.

The render itself SHALL still wait for the owner's typed `yes` to the approval with its warnings. The specialist SHALL NOT pass frames, resolution or engine.

#### Scenario: Turntable asked for
- **WHEN** the owner writes "make a turntable of the lit version" and finals run on the laptop
- **THEN** the reply offers a detail still now or the laptop turntable with its estimate, and no render starts until the owner chooses and answers `yes`

#### Scenario: Final image without a kind
- **WHEN** the owner writes "render the final image"
- **THEN** a detail still is proposed for approval
