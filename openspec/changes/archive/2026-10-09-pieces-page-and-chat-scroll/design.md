## Context

See proposal.md for the why. Current state:

- `frontend/src/routes/Pieces.tsx`, `Piece`: the versions are a `role="group"` row of `Button`s with `aria-pressed`, newest first. `Piece` already loads every version's `VersionInfo` with `useQueries` (`status`, `approved_at`, `files`), and it keeps the chosen version, falling back to the newest after a delete.
- `Downloads` puts "Download design (version N)", "Download bundle (version N)" and an "Inspect version N" `Link` on one `<p>` of underlined links. `Approval` renders "Approve/Unapprove version N" only for a version whose build succeeded.
- `VersionInfo.files` lists the served files present, so `screenshot.png` can be found without a new field. `versionFile(id, n, "screenshot.png")` is its URL. Every successful build writes `screenshot.png` (`storage.BUILD_FILES`).
- `frontend/src/routes/Conversation.tsx`: the messages `<section aria-label="Messages">` has no height limit, so the page scrolls and opens at the top. The composer, `ConfirmationCard` or `QuestionForm` sits after the section. The inspector `aside` is already sticky and scrolls in its own box, using `--header-h` (`index.css`).

## Goals / Non-Goals

**Goals:**
- Use the data the page already loads. No backend, route or schema change.
- Keep the accessible names that other tests and the browser check use where the behaviour is unchanged ("Approve version N", "Delete version N").

**Non-Goals:**
- No change to the Project panel, the inspector's own version buttons, or the render cards.
- No thumbnail size variants and no new image route. The browser scales the existing screenshot.
- No "new messages" pill or unread marker in the chat.

## Decisions

**Native `Select` for the versions.** Use the existing `@/components/ui/select`, which the pricing dropdown also uses. Its accessible name is "Versions of <id>", and each option value is the version number. The entry's state comes from the `useQueries` result: `approved_at` gives "(approved)", `status === "failed"` gives "(failed)", and `queued`/`running` give "(building)". The owner chose "(approved)" and "(failed)"; "(building)" is added so a queued or running version is not mistaken for a built one. A version whose info has not loaded yet shows "Version N" only. *Alternative*: a shadcn popover listbox. Rejected because it is new markup for the same job.

**Inspect joins `Approval`, renamed to a version actions row.** `Approval` already renders only for a succeeded version, which is exactly when Inspect is offered. The row becomes `[Approve version N] [Inspect version N]`, and `Downloads` keeps only the two links under a "Downloads:" label. The Inspect button is `Button asChild` around the existing router `Link`, so it stays a link to `/pieces/<id>/versions/<n>` but looks like a button. This matches the Project panel's framed button. The link texts become "Design (JSON)" and "Bundle (ZIP)", each with an `aria-label` of "Download design (version N)" and "Download bundle (version N)". That keeps the old accessible names and download file names.

**The picture is chosen from the loaded infos, not the dropdown.** A small pure function in `Pieces.tsx` takes the versions (newest first) and their infos. It returns the approved version when its `files` include `screenshot.png`, otherwise the first version whose `files` include it, otherwise nothing. It is unit-tested in Vitest. The `img` uses `versionFile(...)` with alt text "<id> version N". It is capped at `max-h-48` with `object-contain`, so a large screenshot does not dominate the card. The approve, unapprove and delete flows already invalidate `["version", id]` and `["pieces"]`, so the picture updates without new wiring.

**Chat column as a viewport-height flex column.** At every width, the chat column (messages section plus composer or form) becomes `flex flex-col` with a height of `calc(100vh - var(--header-h) - <title block>)`. The messages section gets `flex-1 min-h-0 overflow-y-auto`, and the composer, card or form keeps its natural height. The messages section keeps a minimum height (about 12rem). A very tall confirmation card or question form then makes the page scroll rather than squeeze the messages to nothing. The title block's height is not a CSS variable today. The column measures its own top offset once on mount and on resize, which is simpler and more robust than a hard-coded rem value. *Alternative*: a fixed `max-h` box. Rejected by the owner ("Fill the screen").

**Stick-to-bottom with one ref and one flag.** A `useRef` on the messages section and an `atBottom` ref are updated on `scroll`: the owner counts as at the bottom within 32 px of it. A layout effect keyed on the number of rendered items (messages, optimistic message, waiting bubble, kept line) scrolls to `scrollHeight` when `atBottom` is set. On the first render with data it always scrolls, so the conversation opens at the last message. `send` and `answer` set `atBottom` before they post, so the owner's own action always jumps down. There is no smooth scrolling, so tests and the browser check see the final position at once. *Alternative*: `scrollIntoView` on a sentinel. Rejected because it also scrolls the page itself.

## Risks / Trade-offs

- **jsdom has no layout**, so Vitest cannot see real heights. → Tests stub `scrollHeight`, `clientHeight` and `scrollTop` on the section element, and assert the `scrollTop` the component sets. The real layout is confirmed in the browser check.
- **Streaming replies grow without adding items**: a reply streaming in grows its bubble without changing the item count. → Also keying the effect on the waiting bubble's `working`/`tool` and on the last message's text length keeps the box at the bottom while the owner stays there.
- **Version label state is per version info**: with 15 versions that is 15 version reads. → These are already made today by `useQueries`, so there are no extra requests.
- **Changed link texts** ("Design (JSON)") could break the browser check's selectors. → `aria-label`s keep the old names.
