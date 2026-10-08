## Why

The conversation view is hard to work in. The top header and the Tools / Project rail scroll away, the rail shows icons with no words, and a finished render is not noticed: the Project panel only refreshes while a build runs, and nothing in the chat says a render is ready or has failed. To look at a result the owner leaves the chat for a separate viewer page, so they cannot point at a detail and ask the Foreman about it in the same view. The owner asked for this on 2026-10-08.

## What Changes

- **Fixed header.** The Studio's top header stays at the top of the screen while the page scrolls.
- **Left column pinned to the screen edge.** The Tools and Project rail moves out of the centred page and sits at the left edge of the screen, below the header, and stays visible while scrolling. An expand control shows the icons with their labels ("Tools", "Project"); collapsed shows icons only. The choice is remembered per browser (assumption, see design).
- **Render notices in the conversation.** When a render started from a conversation finishes (draft, preview or final; turntable or still; also a detail pass), code posts a notice into that conversation. For a piece version the notice has a button that names the tier: "Review draft v1" for version 1 and "Review draft revision <n>" for later versions, and likewise "Review preview …" and "Review final …"; it says the result can also be checked in the Project panel. When a render fails, a notice says so in plain words and has no button. The model does not post or promise the notice; the Builder's rule "never promise to tell the owner later" stays as it is.
- **Split screen with the Inspector.** The Review button and the Project panel's Inspect button open the Piece Inspector for that version beside the chat: chat on one side, inspector on the other. The conversation route uses the full screen width for this. The inspector page itself stays.
- **Inspect is a button.** "Inspect version N" in the Project panel becomes a framed button with rounded corners, in the existing button style.
- **No more turntable viewer links for pieces.** "Open the turntable viewer" is removed from the Project panel and the Pieces page. The Inspector is the one way in to look at a piece. The Rooms page keeps its composition link "Open the turntable viewer of <composition>" for now, because compositions have no inspector. Turntable renders still run and still write their frames, still and `viewer.html` exactly as now.
- **The render reply drops the viewer route.** When `render_turntable` or `render_detail` starts a render, its reply gives the estimate and says that a Review button appears in this chat when it finishes (for a shell or composition: that a notice appears), instead of "When it finishes it will be at <route>". The Builder's and Lighting's instruction lines that say to tell the owner where the viewer will be change to match.
- **Project panel follows a render.** The panel refreshes while a render of the latest version is queued or running, not only while a build is.
- Ladder and agents: Studio and chat plumbing around ladder **step 1**. No agent's tools or model change; the render tools (Builder's `render_turntable`, Lighting's `photoreal_detail`) gain a code-side notice on completion and a reply without the viewer route, and one line each in `builder.md` and `lighting.md` follows that reply. **The render guard and the bpy allow-list are not affected**: no new render path, no change to tiers, estimates, approval or the socket.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: sticky header; rail pinned to the left edge with an expand control; render notices with a Review button; the inspector opened beside the chat; Inspect as a framed button; viewer links removed from the Project panel and Pieces page (the Rooms page keeps its composition link); the 3D view may load in the split view; the Project panel refreshes while a render runs.
- `design-agents`: the render reply gives the estimate and says a Review button (or, for a shell or composition, a notice) appears in this chat when it finishes, not where the viewer will be.
- `homeowner-chat`: a render started from a thread posts a notice to it when it finishes or fails; the thread's history returns notices in order; the progress read says whether a render of the latest version is queued or running.

## Impact

- Backend: a new `thread_notices` table (one Alembic migration, next free number), `app/agent/house_file.py` (write and read notices), `app/agent/chat.py` `history` (notice entries), `app/api/chat.py` (`MessageOut` gains `notice`), `app/agent/progress.py` (`rendering`), `plugins/render_turntable/tool.py` and `plugins/photoreal_detail/tool.py` (post the notice from `on_outcome`; reply without the viewer route), `app/agent/instructions/builder.md` and `lighting.md` (one line each). No new dependency.
- Frontend: `App.tsx` (sticky header), `components/Page.tsx` (wide variant), `components/chat/Rail.tsx` (pinned, expandable), `routes/Conversation.tsx` (layout, notice bubble, split view, Inspect button, refresh), a new `components/inspector/InspectorView.tsx` extracted from `routes/PieceInspector.tsx`, `routes/Pieces.tsx` (viewer link removed; `routes/Rooms.tsx` unchanged), `lib/api.ts` (types). No new dependency.
- Unchanged: generators, `viewer.html` and its writers, render offload, the Rooms page, the Reviewer's evidence.
- Out of scope (parallel changes): room and build scoping of a conversation (`conversation-projects`), references from the Reviewer and Foreman to renders (`render-references`), the hardware calculator.
