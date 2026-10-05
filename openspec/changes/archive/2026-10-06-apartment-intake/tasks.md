## 1. Room contract and room renders

- [x] 1.1 Widen `room_contract` to simple polygons (3–12 corners, repeated corner, 50 mm edge, self-intersection), even-odd point-in-polygon, footprint-in-room with edge crossing, `interior_point`; verify `tests/test_room_spec.py` keeps passing and new cases cover an L, a U, a bow-tie, 13 corners, a footprint across the inner corner, a footprint along the inner wall, and a furnishing in the missing quarter
- [x] 1.2 Update `house_file.validate_room` docs and messages and `record_brief` for non-convex rooms; verify `tests/test_house_file.py` stores a six-corner L and refuses a bow-tie naming the outline
- [x] 1.3 Triangulate prism caps and pick the still camera's sight line and the turntable's orbit centre with `interior_point` in `build_room_scene.py`; verify `tests/test_room_generator_blender.py` (`--blender`) renders an L-shaped room still at tier `draft` with the floor inside the L

## 2. Routing and Intake vision

- [x] 2.1 Route `intake` to `deepseek/deepseek-v4.1-flash`, add `intake` to `IMAGE_SLOTS`, update CLAUDE.md §4; verify `tests/test_routing.py` fails startup naming `intake` for a text-only model and the probe sends the image probe for Intake's slug
- [x] 2.2 Migration `0003_apartments_uploads` (`apartments`, `uploads`, `rooms.apartment_id`) with downgrade; verify upgrade/downgrade on the test database and no autogenerate drift
- [x] 2.3 Add `app/agent/uploads.py` (sniff, chunked write with cap, per-thread count, delete on DB failure) and `app/api/uploads.py` routes; verify `tests/test_uploads_api.py` covers PNG and JPEG accepted, PDF-renamed-png 415, oversized 413 with no file left, the per-thread cap 409, 401 without the cookie, and `nosniff` on fetch
- [x] 2.4 Accept `upload_ids` on turns (422 for a foreign id), store ids in `additional_kwargs`, expand them into image blocks in the agent node for image slots inside the window, and a note for other slots; verify `tests/test_chat_images.py` (fake model) sees the image block for Intake, a note for the Designer, and a checkpoint holding no base64

## 3. Apartments and `record_plan`

- [x] 3.1 Add `shell_contract.py` (apartment normalisation, overlap test, shared walls, plausibility warnings) and `house_file` apartment functions; verify `tests/test_shell_contract.py` covers the two-room fixture's shared wall, overlapping rooms refused naming both, a door on the shared wall, and each plausibility warning
- [x] 3.2 Add `tools/record_plan.py` (gated, subject `plan`) and update `intake.md` (when to use `record_plan` vs `record_brief`, state scale and assumptions, never invent a figure); verify `tests/test_record_plan.py` covers the preview with sizes, areas and warnings, `yes` writing the apartment and rooms, `no` writing nothing, and a failing room refused with no pause
- [x] 3.3 Convert the predecessor's two-room manifest to a millimetre fixture and carry the apt-4 living room provenance note; verify both load through `shell_contract`

## 4. Shell generator and renders

- [x] 4.1 Write `generators/build_shell.py` (walls deduplicated, interval openings, triangulated floors and ceilings, Workbench screenshot) and `storage.shell_version_dir`; verify `tests/test_shell_generator_blender.py` (`--blender`) builds the two-room fixture with one wall at x = 5200, the door cut in it, and an L-shaped room's floor inside the L
- [x] 4.2 Carry a record kind (`piece` | `shell`) through `RenderQuote`, `RenderTicket.matches` and `runner.run_render`; verify the guard tests still pass and a shell ticket never matches a piece of the same id
- [x] 4.3 Add `app/api/apartments.py` (list, read, build, versions, exact-name files, renders and approve); verify `tests/test_apartments_api.py` with the fake launcher covers a build, a `draft` shell turntable (tier `draft`) with its estimate, `frames: 12` refused naming `frames`, a `final` 409 then approve, and files served by exact name only
- [x] 4.4 Add `tools/build_shell.py`, the `shell` argument on `render_turntable`, and the Foreman's Builder rule for apartments with a shell; verify `tests/test_builder_tools.py` and `tests/test_foreman.py` cover a shell build report and a shell `draft` render (tier `draft`)

## 5. Documentation and verification

- [x] 5.1 README: uploads, a plan turn with `curl`, the shell build and a `draft` shell turntable; tick CLAUDE.md §11 step 4a; verify the curl sequence against a live service (the vision turn documented as needing a key)
- [x] 5.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, then `uv run pytest --blender -m blender` once (every render at `draft`); verify all pass and record the counts in the commit message
