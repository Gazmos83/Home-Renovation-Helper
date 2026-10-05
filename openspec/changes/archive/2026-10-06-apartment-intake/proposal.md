## Why

After `agent-loop` the owner can describe one room in numbers, but the house is an apartment: several rooms, shared walls, L-shaped spaces, a blueprint on paper and photos on the phone. Typing every corner by hand is where the loop stalls. CLAUDE.md §3 puts apartment shells in scope: Intake reads blueprints and room photos with a vision model into the house file, and the Builder generates the shell headless at ladder step 1 from that data. This is §11 step 4a.

## What Changes

- **Plan uploads**: the owner uploads a blueprint or a room photo (PNG or JPEG, sniffed from the bytes, size-capped) to a thread; a turn can attach uploads, and Intake sees them as images. Files live under an upload root on disk, never in graph state.
- **Intake reads plans**: Intake is routed to the image-capable registry model (`deepseek/deepseek-v4.1-flash`) and becomes an image slot, so startup refuses a text-only model there. It reads the blueprint's scale, room outlines, ceiling height and openings, states what it read and what it assumed, and never invents a figure it cannot see — it asks.
- **`record_plan`** (gated, Intake): proposes a whole apartment at once — its name and every room's outline in one plan frame, heights and openings — and on the owner's `yes` writes them to the house file. Scale plausibility checks (door width, sill, ceiling, room area against the plan's printed area) are reported in the preview.
- **Non-convex rooms**: the room contract grows from convex 4–8 corners to simple polygons of 3–12 corners (no self-intersection, no repeated corner). Room-scene placement and the footprint check, the room generator's floor/ceiling and its camera target work for L- and U-shaped rooms.
- **Apartments in the house file**: an `apartments` table; a room may belong to one, and its corners are then in the apartment's plan frame (millimetres). Single rooms keep working as before.
- **Apartment shell** (Builder, headless): a new generator builds every room of an apartment — floors, ceilings, walls with each shared wall built once, openings cut — into `docs/renders/shells/<apartment>/v<N>/` with `model.blend`, `model.glb`, `shell.json` and a Workbench `screenshot.png`. `build_shell` (Builder) runs it and reports the screenshot. A shell turntable renders through the guard like any version (`render_turntable` with a required tier).
- **Ported**: `generate_shell.py`'s shared-edge deduplication and opening placement, the manifest validator's checks, and the measurement-intake plausibility rules from the predecessor's apartment-render skill — rewritten as a headless Blender 5.2 generator from validated JSON (no pasted MCP chunks, no Cycles, no GPU).
- **Not included**: camera matching to photos, materials look-dev and Cycles finals (ladder step 3, step 8); PDF blueprints (PNG/JPEG only); furniture placed across rooms of a shell (a room render still places one piece in one room).

**Ladder step and agent:** ladder step 1 (validated JSON → headless generator). Agents: Intake (vision read, `record_plan`), Builder (`build_shell`, renders). **Render guard:** used, not changed in behaviour — shell renders go through `authorise`/`run_render` with a required tier; the shell generator joins the build (unguarded, screenshot-only) side, and the render scripts list is unchanged. **bpy allow-list:** not affected; no live socket.

## Capabilities

### New Capabilities
- `plan-uploads`: uploading blueprints and photos to a thread, their validation and storage, and attaching them to a turn.
- `apartment-shell`: the apartment record, `record_plan`, the headless shell generator and its build and render.

### Modified Capabilities
- `house-file`: rooms may be non-convex (3–12 corners) and may belong to an apartment in one plan frame.
- `scene-rendering`: the room-scene document accepts non-convex outlines; the convexity refusal becomes a simple-polygon refusal.
- `llm-gateway`: Intake joins the Reviewer as a slot that needs image input.
- `design-agents`: Intake reads attached plans and photos and may propose a whole apartment.

## Impact

- Code: `app/blender/room_contract.py` (simple polygons, point-in-polygon, interior point), `app/blender/generators/build_room_scene.py` (concave floor/ceiling, camera target), new `app/blender/generators/build_shell.py` and `app/blender/shell_contract.py`, `app/blender/storage.py` (reserved `shells` folder), `app/agent/tools/{record_plan,build_shell}.py`, `app/agent/uploads.py`, `app/api/uploads.py`, `app/api/apartments.py`, chat turn body gains `upload_ids`, migration `0003_apartments_uploads`.
- Config: `config/models.yaml` routes `intake` to `deepseek/deepseek-v4.1-flash`; `IMAGE_SLOTS` gains `intake`; CLAUDE.md §4 table updated; new settings `UPLOAD_ROOT`, upload size and count limits.
- Tests: polygon contract (L-shape, self-intersection, 12 corners), room render of an L-shaped room (`--blender`, `draft`), shell contract and generator (shared wall once, door on a shared wall), upload sniffing and limits, Intake turn with an image (fake model), `record_plan` preview/yes/no, routing refusal for a text-only Intake.
- Fixtures: the predecessor's two-room manifest converted to millimetres, the apt-4 living room with its provenance note.
