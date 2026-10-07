## Why

Renders are the owner's main judgement point, but there is no record of what they thought of one. DESIGN_NOTES ("Feedback loop") gives feedback two uses:
- **personalisation:** the agents read the owner's past reactions from the house file;
- **routing evidence:** Langfuse tags show which model does best at which task, so the owner can change a slot's model by hand.

Learning from feedback is also a course requirement. This is §11 step 9.

## What Changes

- **Render origin recorded.** When a guarded render starts, the service records which render it is (package, version, render key, tier). When an agent turn started it, the record also holds the thread, the turn's trace id, the owner's message that asked for it, and the slot and model that called the render tool. This lives in the database, never in the version folder, so the model never reaches a homeowner file route.
- **Thumbs up/down plus an optional comment** on every published render: still, turntable, room still and room turntable, and detail renders from `photoreal-detail`. There is one current rating per render run, and the owner can change or clear it.
- **Two ways in:**
  - **Pieces page** (new homeowner route `/pieces`): pieces → versions → the version's renders with a preview image, a link to `viewer.html`, and thumbs + comment. It shows no model, prompt, token or cost.
  - **`record_render_feedback`** chat tool on the Builder and Lighting & materials. When the owner reacts in words ("the draft is too dark 👎"), the tool proposes the rating and comment for the render it means and records them only on `yes`.
- **House file:** the Designer's and Lighting's turn context lists the latest five ratings on the bound piece (version, render, tier, up or down, comment), labelled as the owner's own words and neutralised.
- **Langfuse:** each rating becomes a score on the trace of the turn that started the render, plus a `render-feedback` trace tagged with the rating, tier, slot and model. A tracing failure never affects recording.
- **Developer panel:** a Feedback page summarising ratings per slot × model × tier (up and down counts, latest comment time) to inform manual routing changes. It never changes routing itself.

**Ladder step and agent:** feeds ladder step 1 (the Designer reads feedback) and step 3 (Lighting reads feedback). There is no step-2 change. Agents: Builder and Lighting & materials (new tool), Designer and Lighting (context). **Render guard:** not affected in what it allows. Its start path additionally records the render origin, and recording failures never block a render. **bpy allow-list:** not affected.

## Capabilities

### New Capabilities
- `render-feedback`: render origin records, rating and commenting a render (route and chat tool), the tracing score and tags, and the feedback summary.

### Modified Capabilities
- `house-file`: the Designer's turn context gains the bound piece's recent render feedback. Lighting's context gains the same, once `photoreal-detail` adds that specialist.
- `studio-ui`: a homeowner Pieces page with render feedback, and a developer Feedback page.
- `dev-panel`: feedback is readable per slot, model and tier.
- `plugins`: a built-in manifest may share its tools with another agent (`also_for`), so one `record_render_feedback` tool serves both the Builder and Lighting & materials under one homeowner toggle.

## Impact

- Code:
  - New: `app/feedback/` (origin, ratings, house-note lines), `app/api/feedback.py` (homeowner rating routes + `/admin/feedback`), `plugins/render_feedback/` (manifest + tool), `frontend/src/routes/Pieces.tsx`, `frontend/src/routes/admin/Feedback.tsx`.
  - Changed: `app/blender/runner.py` / `plugins/render_turntable/tool.py` (record origin at start), `app/agent/house_file.py` and `app/agent/prompts.py` (house note), `app/observability/langfuse.py` (`record_feedback`), `builder.md` and `lighting.md` headers.
  - Migration `0008_render_feedback` (`render_runs`, `render_feedback`).
- Port reference: `Interior_Design_App` `domain/feedback.py`, `api/feedback.py` and `feedback_policy.py`. Only the rating record and summary are ported; the per-scope policy knobs (style notes, retrieval limits) are not, because the house file carries personalisation here.
- Tests: origin recorded for agent- and route-started renders, rating and changing and clearing, a rating on a render that never ran refused, the chat tool's confirmation, house-note lines and neutralisation, Langfuse score and tags with tracing off or failing, the summary, no model or prompt in homeowner responses, and the browser check for both pages.
- Depends on `photoreal-detail` (detail render keys, the Lighting specialist).
