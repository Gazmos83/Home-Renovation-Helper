## Context

- `render_turntable` renders a piece, a shell, or a composition. A composition is recorded as `room`, with its slug in `package_id`. When the render ends, `notices.finished` calls `notices.post`, which stores a `thread_notices` row with the text, and with a package and version only for a piece.
- The conversation view polls the thread only while `progress.rendering` or a build is running (`Conversation.tsx`). `rendering` reads the render jobs in the `status.json` of the bound piece's latest version only (`progress.py`).
- `render_runs` records only piece renders, because ratings are per piece. It is not reused here.
- Composition files are served at `/compositions/{slug}/versions/{n}/files/{name}`: `viewer.html` and `still.png` are what the Rooms page links to.

## Goals / Non-Goals

**Goals:**
- A room render started in a conversation shows its notice there without a reload.
- That notice links to the result, and says it is on the Rooms page too.

**Non-Goals:**
- A room inspector beside the chat.
- Links for shell renders.
- Notices for renders started outside a conversation.
- Changes to the Rooms page.

## Decisions

1. **A small `thread_room_renders` table, not a reuse of `render_runs`.** Rows hold thread id (cascade on delete), composition slug, version, render key and started-at. `render_turntable` inserts a row when it enqueues a `room` render with a thread. `notices.post` deletes the thread's row for that slug, version and key when it posts. Reusing `render_runs` would put compositions into the per-piece ratings and counts.

2. **`rendering` stays honest after a crash.** Progress counts a row only while that composition version's `status.json` shows a queued or running render under the row's key. A row left behind by a crashed process therefore stops the polling, and is deleted the next time progress reads it.

3. **Links are computed when history is read, not stored.** A notice row gains a nullable `composition_slug`, set for `room` renders together with `version`. When the thread history is read, a finished room notice gets `links`: for a turntable `{"label": "Open the turntable viewer", "href": <viewer.html route>}`, for a still `{"label": "Open the still", "href": <still.png route>}`. Each link is included only if its file exists. The kind is read from the notice's render key, stored in a nullable `render_key` column beside the slug. `package_id` stays empty for rooms, so the piece Review button logic is untouched.

4. **The text names the Rooms page.** A finished room notice reads, for example, "The draft turntable of wohnen version 11 is ready. You can also find it on the Rooms page."

5. **Frontend.** `Notice.tsx` renders each link as an outline-styled anchor opening in a new tab (`target="_blank"`, `rel="noreferrer"`), the same as the Rooms page link. Piece notices are unchanged.

## Risks / Trade-offs

- **[Polling cost]** One extra indexed query per progress call. → Only rows of the thread are read.
- **[Old notices]** Notices posted before this change have no slug, so they show no link. This is accepted and stated in the spec.

## Migration Plan

One Alembic migration: create `thread_room_renders`, and add the nullable `composition_slug` and `render_key` to `thread_notices`. Rollback drops them; notices fall back to text only.

## Open Questions

- TODO(user): should a shell render's notice get the same links?
