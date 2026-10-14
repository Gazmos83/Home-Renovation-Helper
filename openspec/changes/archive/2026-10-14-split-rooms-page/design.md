## Context

`frontend/src/routes/Rooms.tsx` renders, in order: an intro, `MeasuredRooms` (one `MeasuredRoom` card per `GET /rooms` entry), one `CompositionCard` per `GET /compositions` entry, then `ModelLibrary` (list, delete, upload form, polling while a model is `checking`). `RoomSummary.composition` carries `{ slug, versions }` for a room that has one; `Composition.slug` is the same slug. `Pieces.tsx` sets the pattern the owner asked for: `Page`, a `flex … justify-between` heading row, a short intro paragraph, an empty-state line, then one `cardClass` section per item titled with an `h2`.

## Goals / Non-Goals

**Goals:** two pages with the Pieces layout; a room's composition inside its room card; no change to any control's behaviour or any query key.

**Non-Goals:** no new API, no backend change, no "create a room" button (none exists today and the owner did not ask for one), no restyling of the controls inside a composition.

## Decisions

- **Two route files.** `Rooms.tsx` keeps the `/rooms` route and becomes the Measured Rooms page; `ModelLibrary` moves unchanged in behaviour to `routes/ModelLibrary.tsx` at `/models`. `/models` is also the library's API path, so the Vite proxy entry for `/models` changes from API-only to the shared-path `page` rule `/rooms` and `/admin` already use: a browser navigation gets the app, every other request the API. Keeping `/rooms` avoids breaking bookmarks and the default-export import in `App.tsx`.
- **Join by slug on the client.** The page reads `["rooms"]` and `["compositions"]` as today and gives each room the composition whose `slug` equals `room.composition?.slug`. Compositions not claimed by any room (apartment scope, or a room-scope composition whose room is gone) render as their own cards below. Alternative — a new combined endpoint — rejected: it would be a backend change for a pure layout move.
- **One composition component, two wrappers.** `CompositionCard` takes an `inRoom` flag: on its own it is a card with an `h2` name and scope badge, as before; inside a room card it is a group labelled with the composition's name under an `h3` "Composition". The body (dropdown, approval, delete version, items, picture, variants, viewer link, 3D view) is unchanged. Same query keys and invalidations, so delete-room and approval refreshes keep working. A separate `CompositionDetail` component was considered and dropped: the flag changes only the wrapper and heading.
- **Room card title is an `h2`.** Matches Pieces (`h2` per item). The room card's accessible name stays `Measured room <name>` so the existing tests' lookups keep working; the composition block is a group labelled with the composition's name so the composition tests find it inside the card.
- **Model cards.** Each model becomes a `cardClass` section with an `h2` name, size line, state badge and delete button, matching Pieces; the upload form stays a card below the list. Polling (`refetchInterval` while any model is `checking`) and the `["model-library"]` key are unchanged.

## Risks / Trade-offs

- [The two queries load at different times, so a room may briefly show "no composition yet" before compositions arrive] → show the composition part only once `["compositions"]` has data; until then the room card shows its own figures only.
- [Existing tests locate compositions by a top-level region name] → tests that only moved location are updated to look inside the room card; assertions stay as they are. Library tests move file unchanged except for the route rendered.
