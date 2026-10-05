## Context

See proposal.md. What exists: `room_contract.normalise_room_shell`/`normalise_room_scene` (convex, 4–8 corners, per-room frame, wall index + offset openings), `build_room_scene.py` (extruded-polygon `_prism` for floor, ceiling and wall segments; still camera from the corner farthest from the piece's wall; turntable orbiting the centroid), the house file (`rooms` with JSONB corners and openings), `record_brief` (one room per call), the Foreman graph with Intake on `openai/gpt-5.6-luna` (text-only), `runner.run_build`/`run_render` with `RENDER_SCRIPTS` guarded and builds unguarded, and `storage` version folders under the render root.

The predecessor's apartment-render skill (`.claude/skills/blender-Grok-package/blender-apartment-render/`) holds a manifest in metres with rooms as polygons in one frame, openings by `from`/`to` world points, shared-edge deduplication (`edge_key` rounded to 3 decimals; shared edges centred, unshared offset outward by half the thickness), a validator (ceiling 1.8–6 m, edges ≥ 5 cm, area ≥ 0.5 m², sill + height ≤ ceiling), and plausibility checks in `references/measurement-intake.md` (door 0.70–1.00 m, sill 0.70–1.10 m, ceiling 2.30–3.20 m, area within 5% of the printed label). Its generator emits MCP chunks with bounding-rectangle floors and a hard-coded Cycles/GPU render; none of that is carried over. The predecessor never sent an image to a model; its upload code (`app/domain/uploads.py`: magic-byte sniffing, 10 MiB cap, chunked read, per-account quota, files under the artifact root) is the pattern to port.

Constraints: the spec JSON is the source of truth (§1); one cheap model per agent (§4) — the owner chose to route Intake to the image model rather than add a second model or slot; secrets and file bytes never in state (§8).

## Goals / Non-Goals

**Goals:**
- A blueprint photo in a turn becomes, after one `yes`, an apartment of rooms in the house file, with stated assumptions and plausibility warnings.
- L-shaped and U-shaped rooms work everywhere a room works: storage, `room_fit`, room renders.
- A shell build in about the time of a furniture build, with a screenshot, and shell turntables through the guard.

**Non-Goals:**
- Camera matching to photos, look-dev, Cycles finals of the shell (step 3 / step 8).
- PDF or multi-page blueprints; automatic scale from pixels without a stated reference.
- Placing furniture across several rooms in one render; doors swinging; stairs; multi-storey.
- Curved walls (an arc is approximated by the owner's corners).

## Decisions

1. **Intake on the image model, by routing.** `config/models.yaml` routes `intake` to `deepseek/deepseek-v4.1-flash`; `routing.IMAGE_SLOTS = {"intake", "reviewer"}`, so a text-only Intake fails startup by name and the startup probe sends the image probe for Intake's slug. CLAUDE.md §4's table is updated in the same change. *Alternative:* a vision tool calling the reviewer slot's model; rejected by the owner (two models per Intake turn).

2. **Uploads: files on disk, ids in state.** New table `uploads` (id uuid, thread_id FK CASCADE, kind `image/png|image/jpeg`, bytes, original_name, created_at). Bytes are written to `<UPLOAD_ROOT>/<thread-id>/<upload-id>.<ext>` (default `<repo>/docs/uploads`, gitignored, folder kept) by a chunked reader that stops past `UPLOAD_MAX_BYTES` (default 10 MiB); type sniffed from magic bytes only; at most `UPLOAD_MAX_PER_THREAD` (default 20). A DB failure deletes the written file. Routes (owner-gated): `POST /chat/threads/{id}/uploads` (multipart, one file), `GET /chat/threads/{id}/uploads`, `GET /uploads/{upload_id}` (fixed `Content-Type`, `X-Content-Type-Options: nosniff`, inline).

3. **Attaching an image to a turn.** `TurnIn` gains `upload_ids: list[UUID]` (max `TURN_MAX_IMAGES`, default 4). The route checks each belongs to the thread (else 422). The human message is stored with `additional_kwargs={"upload_ids": [...]}` and plain text content, so checkpoints never hold image bytes. The specialist `agent` node expands, for messages inside the history window and only for image-capable slots, each referenced upload into an `image_url` content block (`data:image/<type>;base64,…`, the same shape the probe already sends). Non-image slots get a fixed note "the owner attached N image(s); Intake reads them". The history window counts an image as one message.

4. **Simple polygons replace convexity.** `room_contract`: `MIN_CORNERS = 3`, `MAX_CORNERS = 12`; refuse a repeated corner, an edge shorter than 50 mm, zero area, and self-intersection (O(n²) segment test over non-adjacent edges); normalise to CCW. Point-in-polygon becomes the even-odd ray test with boundary inclusion; "footprint inside the room" becomes all four footprint corners inside **and** no footprint edge properly crossing a room edge (catches the inner corner of an L). Furnishing containment uses the same test. Wall indexing, opening offsets and outward normals are unchanged (valid for any CCW simple polygon). New helper `interior_point(corners)`: the centroid if it is inside, else the midpoint of the longest horizontal chord through the polygon's vertical middle — deterministic and always inside. *Alternative:* store L-shapes as two convex rooms; rejected by the owner.

5. **Room generator on concave rooms.** `_prism` already builds caps as n-gons; the caps are triangulated with `bmesh.ops.triangulate` (ear-clipping handles concave n-gons) before `recalc_face_normals`, so Eevee and Workbench shade them correctly. The still camera picks, among corners sorted by distance from the piece's wall, the first whose sight line to the piece's centre stays inside the polygon (the footprint test reused); the turntable orbits `interior_point` instead of the centroid. A `--blender` test renders an L-shaped room at `draft`.

6. **Apartments in the house file.** Table `apartments` (id, name unique, ceiling_height_mm, wall_thickness_mm, notes, created/updated); `rooms.apartment_id` FK SET NULL. Validation: every room by the room rules; then pairwise no area overlap (polygon intersection test: any edge crossing or one room's interior point inside the other), allowing shared edges. A shared wall is a pair of collinear, overlapping edges of two rooms (tolerance 1 mm). Openings stay per room by wall index + offset; a door on a shared wall is recorded once, on either room, and the shell cuts the shared wall.

7. **`record_plan` (Intake, gated).** Args: `apartment_name`, `ceiling_height_mm`, `wall_thickness_mm`, `rooms: [{name, corners_mm, ceiling_height_mm?, openings?, printed_area_m2?}]`, `scale_note` (how the scale was read), `assumptions: [str]`. Preview: one line per room (size, area), openings, the scale note and assumptions, and plausibility warnings (Decision 8). `yes` upserts the apartment and its rooms in one transaction; existing rooms of the same name are replaced; `no` returns the reason. Subject `plan`. `record_brief` stays for one room and a piece brief; Intake's instruction file says when to use which.

8. **Plausibility rules are code, not prompt.** `app/blender/shell_contract.py` holds the predecessor's ranges (door 700–1000 mm wide, window sill 700–1100 mm, ceiling 2300–3200 mm, printed area within 5%). They warn in the preview; they never refuse (a real flat may have a 2200 mm ceiling). Hard limits stay the room contract's.

9. **The shell generator.** `generators/build_shell.py` (`--shell <json> --out <dir>`), standard-library contract in `shell_contract.normalise_shell(document)` shared with the backend like `room_contract`. Walls: every room edge, deduplicated as shared walls (Decision 6), each a `_prism` segment of the wall thickness, centred on a shared edge and offset outward on an outer edge; openings cut by splitting the wall's interval into solid segments plus lintel and sill prisms (the room generator's interval method, not booleans, so no FLOAT-solver artefacts). Floors and ceilings are each room's polygon prism (triangulated). Objects named `Floor_<room>`, `Ceiling_<room>`, `Wall_<n>_<seg>`; collections Shell/Openings. Publishes `model.blend`, `model.glb`, `shell.json` and a Workbench 800×500 `screenshot.png` from a top-down three-quarter camera. Not in `RENDER_SCRIPTS`: it is a build.

10. **Shell storage and renders.** Shells live at `<render root>/shells/<apartment-slug>/v<N>/` (`shells` reserved like `benchmark`, so it is never listed as a piece). `storage` gains `shell_version_dir`. The render guard is unchanged: a `RenderQuote`'s subject becomes `(kind_of_record, id, version)` with record kind `piece` or `shell`, carried through `RenderTicket.matches` and `runner.run_render`, which resolves the folder from it. A shell turntable uses `render_turntable.py --blend <shell>/model.blend`. Routes (owner-gated): `GET /apartments`, `GET /apartments/{slug}`, `POST /apartments/{slug}/shell` (build), `GET /apartments/{slug}/shell/versions/{n}`, files by exact name, `POST …/renders` and `…/renders/approve` mirroring the package render routes.

11. **Builder tools.** `build_shell(apartment)` waits like `blender_build` and reports `/apartments/<slug>/shell/versions/<n>/files/screenshot.png`. `render_turntable` gains an optional `shell` argument (apartment name) exclusive with `package_id`; everything else — tier required, raw knobs refused, `final` paused — is the same code path. The Foreman's Builder rule extends: a thread may reach the Builder when the house file has an apartment with a shell version, as well as for a bound piece.

## Risks / Trade-offs

- [The vision model misreads a scale or a wall] → It must state the scale reference; `record_plan`'s preview shows every room's size and area and the warnings; nothing is stored before `yes`.
- [Non-convex footprint tests are subtler than convex ones] → Property tests over L/U/T shapes: footprints across the inner corner, along the inner walls, and touching the boundary.
- [Image tokens are expensive per turn] → Images are only expanded inside the history window and only for image slots; a later step-7 budget counts them.
- [Intake's model changes family for every Intake turn] → Owner's decision; recorded in CLAUDE.md §4.
- [Changing `RenderQuote`'s subject touches the guard's ticket matching] → Covered by the existing guard tests plus a shell ticket that must not match a piece of the same id.

## Migration Plan

Migration `0003_apartments_uploads` adds `apartments`, `uploads` and `rooms.apartment_id`; existing rooms remain without an apartment. Existing convex rooms and room documents stay valid under the wider contract. Rollback: downgrade drops the two tables and the column; shell folders on disk are left in place.

## Open Questions

None that change the specs. Defaults recorded as assumptions: 3–12 corners, 50 mm minimum edge, 1 mm shared-wall tolerance, 10 MiB / 20 uploads per thread / 4 images per turn.
