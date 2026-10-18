## Why

On 2026-10-16 the owner asked, in the Murphy bed conversation, for a draft render of the Wohnen room composition (version 11). The render succeeded: a 12-frame turntable and a still, finished at 17:20. Both notices were stored, but the owner saw no notification and could not tell where to view the result. There are two causes:
- **The chat never refreshed.** It re-reads its messages only while its progress reports `rendering`, and that flag looks only at the conversation's bound piece (`progress.py`), never at a room composition.
- **The notice had nowhere to point.** A composition's notice has no button by spec. The only way to the render is the Rooms page dialog's "Open the turntable viewer" link.

The owner asked for a link in the chat when the render is ready.

## What Changes

- **The chat follows a room render it started.** When a conversation starts a render of a room or apartment composition, the service records it against that thread. While it runs, the thread's progress reports `rendering`, so the chat refreshes and the notice appears without a reload. The record is removed when the notice is posted, and it stops counting once that composition version shows no queued or running render, so a crash cannot leave the chat polling for ever.
- **A finished room render's notice carries a link.** A turntable's notice links to its turntable viewer ("Open the turntable viewer"), and a still's notice links to the still image ("Open the still"). Each opens in a new tab and uses the same composition file route as the Rooms page. The notice text adds where else to find it: "You can also find it on the Rooms page." A failed render shows no link. A link is shown only while its file exists, so a deleted version shows the notice without a link.
- **Explicit behaviour changes:**
  - a composition's notice now shows links, where it showed nothing;
  - the progress `rendering` flag now also covers room renders started in the thread.

Ladder step: none. Rendering, specs and generators are unchanged. Agents touched: **Builder** (`render_turntable` records the room render), and the **Foreman** conversation view (notices). The **render guard is not affected**: no new render path, and tiers, estimates and the typed "yes" for `final` are unchanged. The **bpy allow-list is not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: a room render started in a thread is followed by the thread's progress, and its notice records the composition and says where else to find it.
- `studio-ui`: a finished room render's notice shows a link to its viewer or still.

## Impact

- **Backend:**
  - `app/db/models.py` plus one Alembic migration: a `thread_room_renders` table (thread, composition slug, version, render key, started), and a nullable `composition_slug` on `thread_notices`;
  - `plugins/render_turntable/tool.py`: record the room render when it is enqueued;
  - `app/agent/notices.py`: post the composition slug and the extra sentence, and remove the record;
  - `app/agent/progress.py`: `rendering` also reads the thread's room renders;
  - `app/agent/chat.py` / the thread history route: a notice entry carries `links` built from the composition file route, only for files that exist.
- **Frontend:** `src/components/chat/Notice.tsx` renders `links`, and `src/lib/api.ts` types them.
- **Tests:** notice text, progress `rendering` for a room render and for a stale record, history links (present, and missing after the file is deleted), Vitest for the link, and a recorded browser check.
- **Unchanged:**
  - piece notices and their Review button;
  - shell renders (still no button; TODO(user) if wanted);
  - renders started outside a conversation (no notice);
  - the Rooms page.
