No task renders; no tier is used.

## 1. Model Library page

- [x] 1.1 Move `ModelLibrary` from `routes/Rooms.tsx` to a new `routes/ModelLibrary.tsx` as the page's default export, laid out like Pieces (heading row "Model Library", intro, one card per model with `h2` name, size, state badge and delete; upload form card below); verify with `pnpm test` on the moved tests
- [x] 1.2 Move the library tests (refused upload, checking → ready, no model/prompt/token/cost text) from `Rooms.test.tsx` to `ModelLibrary.test.tsx`, add "Models listed" and the empty-library line; verify `pnpm test ModelLibrary` passes

## 2. Measured Rooms page

- [x] 2.1 Give `CompositionCard` an `inRoom` wrapper (a group under an `h3` "Composition" inside a room card, its own card otherwise); verify the existing composition tests (versions, 3D, dimensions, approval, delete version) still pass
- [x] 2.2 Rework `Rooms.tsx` into the Measured Rooms page: heading row "Measured Rooms", intro, one `h2` card per room with its composition inside (joined by slug, shown once compositions have loaded) or "no composition yet" with how to get one; unclaimed compositions as their own cards below with scope badge; empty-house-file line; verify with `pnpm test Rooms`
- [x] 2.3 Update `Rooms.test.tsx` lookups to find compositions inside their room card and add tests for "Composition inside its room", "Apartment composition on its own card", "No rooms" and the no-composition line; verify `pnpm test Rooms` passes

## 3. Navigation

- [x] 3.1 In `App.tsx` replace the "Rooms" link with "Measured Rooms" (`/rooms`) and "Model Library" (`/models`) after "Pieces", add the signed-in `/models` route, and switch the `/models` Vite proxy entry to the `page` rule; add tests for the nav order and the signed-out redirect in `App.test.tsx`; verify `pnpm test App`

## 4. Checks

- [x] 4.1 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`; all pass
- [x] 4.2 Browser check of both pages (record it): Measured Rooms shows each room with its composition, approve/unapprove, delete version, delete room with warning, 3D view; Model Library uploads, shows checking → ready, deletes; navigation reads Pieces, Measured Rooms, Model Library
