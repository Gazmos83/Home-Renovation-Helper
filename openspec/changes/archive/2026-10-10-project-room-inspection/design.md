## Context

- The Project panel (`frontend/src/routes/Conversation.tsx`, `ProjectPanel`) reads `GET /threads/{id}/progress`, which today knows only the bound piece (`progress.piece_progress`).
- The conversation view already has a split screen: `?inspect=<package-id>/<n>` shows `InspectorView` in an `<aside>` beside the chat, closed by a button that removes the parameter.
- The conversation's confirmed room or apartment is `house_file.thread_scope(session, thread_id)`; its composition is `house_file.composition_by_scope(session, scope, name)`.
- The Rooms page shows a composition's 3D view with `RoomView({ name, model, report })`, where `model` and `report` are the routes `/compositions/<slug>/versions/<n>/files/model.glb` and `.../report.json`, set by `GET /compositions` only when the latest version folder has `model.glb`.

## Goals / Non-Goals

**Goals:** reuse `RoomView` and the existing split-screen layout unchanged; one extra field on the progress read; no new route.

**Non-Goals:** choosing a composition version other than the latest; showing the room of the active piece or of other conversations; any change to the Rooms page or to composing rooms.

## Decisions

**Progress carries the room.** `ProgressOut` gains `room: RoomOut | None` with `name`, `scope`, `slug | None`, `model | None`, `surfaces | None`. The route already opens a session for `piece_progress`; it also calls `thread_scope` and `composition_by_scope`, and builds the two routes with the same rule as `list_compositions` (latest version, `model.glb` present). The composition route is built in `agent/progress.py`, as that module already builds package routes (the agent layer does not import from `api/`). A small `room_progress(session, root, thread_id)` beside `piece_progress` in `agent/progress.py` keeps the route thin. `slug` is set only when the composition exists; `model`/`surfaces` only when its latest version has `model.glb` — so the panel can tell "no composition" from "compose again for 3D".
*Alternative:* the panel reads `/rooms` and `/compositions` and matches by name. Rejected: the frontend does not know the conversation's confirmed room, and the house-file rule is that a conversation sees only its slice.

**`?room=<slug>` beside `?inspect=`.** The address holds the composition slug. The pane renders only when the slug equals `progress.room.slug` and a model is known; otherwise nothing is shown (a stale address after the conversation's room changed, or before progress loads). One helper sets one parameter and deletes the other, which gives the one-pane-at-a-time rule for every opener (panel button, notice's Review, version picker). The aside's layout and close button are shared; its content is `InspectorView` or `RoomView`.
*Alternative:* one `?pane=` parameter. Rejected: it would change the existing `?inspect=` addresses that notices and reloads rely on.

**Panel wording.** Room section under the piece block: heading with the room's name; "Inspect <name>" button when `model` is set; "<name> has no 3D view yet. Ask the Designer to compose the room." (or "the apartment") when `slug` is null; "Composing <name> again adds the 3D view." when the composition exists without a model (same words as the Rooms page).

## Risks / Trade-offs

- [The progress read polls every 3 s while building, now also touching compositions] → two indexed lookups and one `is_file`; negligible.
- [A composition re-building while its view is open] → `RoomView` keeps the routes it was given; the next progress refresh after the build gives the new version's routes and the pane follows, as the Rooms page does.
- [`RoomView` is lazy-loaded with three.js] → unchanged cost; loaded only when the owner opens the pane.

## Additions after the owner's check (2026-10-09)

**Version views in one place.** `progress.composition_version_views(session, root, composition)` returns the newest five versions, newest first, each with `version`, `status`, `picture`, `viewer`, `items`, and — when the folder has `model.glb` — `model`, `surfaces` and `dimensions` routes. `GET /compositions` adds it as `version_views` (the existing `versions` list of numbers is kept as is), and `progress.room` adds it as `versions`. The cap of five is a display limit only; no version is deleted or refused.
*Alternative:* the frontend slices the full list. Rejected: every listed version needs its own file checks and items, which are cheaper to do for five than for all.

**Dimensions from the stored document.** `compositions.room_dimensions(document)` reads the version's `input.json`. A room scope uses `resolved.rooms[0]`: wall *i* runs from corner *i* to corner *i+1* and is labelled `wall <i+1>`, as the surface map labels `Wall_<i>_…`. An apartment scope uses `normalise_shell(resolved["shell"]).walls`, which already holds each physical wall once with its length, labelled by `apartment_wall_labels`, and each shell room's `height_mm`. Each room's ceiling marker sits at the mean of its corners. Served as `GET /compositions/{slug}/versions/{n}/dimensions`. Nothing changes in the generators, so the render guard and the `--blender` suite are unaffected.
*Alternative:* write the dimensions into `report.json` at build time. Rejected: it needs a generator change and leaves existing versions without dimensions.

**Labels in the 3D view.** `InspectorCanvas` takes an optional `overlay` node drawn inside the offset group, so plan coordinates map as `[x/1000, z/1000, -y/1000]` (the model is exported Y-up). `RoomDimensions` draws each wall as a line just above the floor with its length on a drei `Html` label, and each ceiling as a vertical line at the room's marker point with `ceiling <h> mm`, the same page-text labels as the piece's `DimensionOverlay`. The switch is a "dimensions" button beside the surface switches, off at first.

**Version in the address.** Beside the chat the address becomes `?room=<slug>` or `?room=<slug>/<n>`; without a number, or with one not among the newest five, the latest is shown. On the Rooms page the chosen version is local state of the card.

**"Selected room".** The panel's room group gets an `h3` "Selected room" with the name below it as plain strong text.
