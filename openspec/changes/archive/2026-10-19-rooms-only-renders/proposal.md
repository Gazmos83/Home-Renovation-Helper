## Why

On 2026-10-18 the owner decided that renders are made of **room versions**, not pieces: "The Inspector view is good enough" for a piece. `render-now-blueprints-verdict-note` (revised the same day) already removed the piece inspector's Renders tab, put a Renders tab with "Render version N now" on the room inspector, and deleted every existing piece render. Asked what should happen to rendering pieces from a conversation, the owner chose "Rooms only from now on".

Today a conversation can still make piece renders that would now show nowhere:
- the Builder's `render_turntable` renders a piece on its own or placed in the conversation's room;
- `restyle_render` makes piece look variants, offered on the piece pane and the Pieces page with "Use this look";
- the Pieces page lists a version's stills with ratings.

## What Changes

- **The Builder renders rooms and shells only.** `render_turntable` refuses a `package_id` target and `in_room` in plain words: "renders are made of rooms; compose the room with this piece and render the room". A composition and an apartment shell render as before, through the guard.
- **Restyle is for rooms only.** `restyle_render` refuses `slots` (piece looks); room styles stay. The piece pane and the Pieces page no longer show piece variants or "Use this look". The "keep a look" revision flow goes with them.
- **The Pieces page lists no renders.** A version's stills, their ratings and the render feedback controls leave the Pieces page; the version keeps its screenshot, inspector link and files.
- **Agents.** The Builder's and Foreman's instructions say renders are of rooms: a piece is built and inspected, and "render it" for a piece is answered by offering to render its room.
- **Unchanged:**
  - the Lighting detail pass and its `final` detail render work on a piece's detail copy as today (the owner kept it for now). TODO(user): move it to rooms in its own change;
  - the Reviewer compares the version's screenshot and straight-on views with the spec, which it already does when there is no render;
  - the render guard, its tiers, estimates and the `final` approval;
  - the developer HTTP route `POST /packages/{id}/versions/{n}/renders`, which no Studio page calls any more; it stays for the detail pass's offload and the guard's tests. TODO(user): remove it in a later change.
- **Rating:** `record_render_feedback` rates a piece's own runs (now only detail renders). Room renders are not recorded as runs, so they cannot be rated yet. TODO(user): rating room renders is its own change.
- **Old data.** Piece renders were deleted on 2026-10-18 (backup outside the repository). Old piece render notices stay in conversation histories as text.

Ladder: none of the three steps (no schema or generator change; the generators keep their piece paths for the detail pass). Agents touched: the **Builder** (`render_turntable`, `restyle_render`, instructions), the **Foreman** (routing wording). **Render guard: not affected** (rooms still render only through it). **bpy allow-list: not affected.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: the Builder renders compositions and shells only.
- `restyle-variants`: piece looks, keeping a look and rating a piece variant are removed; room styles stay.
- `studio-ui`: the Pieces page no longer shows renders and feedback.

## Impact

- `backend/plugins/render_turntable/tool.py`, `backend/plugins/restyle_render/tool.py`, their manifests' descriptions, `backend/app/agent/instructions/builder.md` and `foreman.md`.
- `frontend/src/routes/Conversation.tsx` (piece pane `PieceVariants`), `frontend/src/routes/Pieces.tsx` (stills, ratings, variants), `frontend/src/components/Variants.tsx` (`keepLookRequest`).
- Tests: `test_builder_tools.py` / render tool tests, restyle tool tests, `test_instructions.py`, `Pieces.test.tsx`, `Conversation.test.tsx`, `Variants.test.tsx`.
- Order: apply after `render-now-blueprints-verdict-note` is archived; this change removes the Pieces-page requirement that change modifies.
