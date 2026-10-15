## Why

`two-tier-renders` made a detail (photoreal) turntable render-server only, because a Cycles turntable takes hours on this CPU. The owner may have no render server, and asked on 2026-10-15 for the laptop option back. The app should still state the time plainly, so the owner chooses it knowingly. A detail turntable is quoted at about 3 h 24 min here (36 × 2.25 MP × 30 × 5.031 s/MP, multiplier uncalibrated). The current 4-hour limit on a final would cut it off.

## What Changes

- **Local detail turntable allowed.** A `final` detail turntable may run on the laptop again, behind the typed "yes". The guard no longer refuses it. A detail render's kind still defaults to a still, so a turntable is asked for on purpose.
- **Long-render warning (above 20 minutes).** The approval of any render quoted above 20 minutes carries a disclaimer:
  - the estimate in hours and minutes;
  - that it is rough until the first final calibrates the Cycles multiplier;
  - that heavy lighting can make it longer;
  - for a detail turntable, that a single still (about 6 minutes) or the render server is much faster.
- **Laptop-busy warning.** A long render on the laptop also says it holds the one Blender process for that time, so builds, drafts and the live detail pass wait behind it.
- **Final limit 6 hours.** The `final` tier's timeout multiplier goes from 24 to 36: 6 h at the 600 s default (owner's decision, 2026-10-15).
- **Lighting agent.** Asked for a detail turntable, it offers three choices: a still now, the laptop turntable with its time, or the render server when finals go there.
- **Docs.** The CLAUDE.md §6 final row, and step 11 of the workflow PDF: "Detail: still or turntable on the laptop, turntable on the server".

**Ladder step and agents:** step 3 (Lighting & materials, `render_detail`). The Builder's `render_turntable` and the Studio render routes get the same warning on long finals. **Render guard: affected.** One rule is removed (no local detail turntable), the approval gains warnings, and the final tier's timeout grows. Tiers, estimates, tickets and calibration are unchanged. **bpy allow-list: not affected.**

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `render-guard`: a local detail turntable is allowed; approvals over 20 minutes carry the long-render and laptop-busy warnings; the final tier runs up to 6 hours.
- `render-offload`: a detail turntable may run locally or remotely, like any final.
- `scene-rendering`: a detail turntable publishes from the laptop or the render server.
- `photoreal-detail`: the Lighting specialist offers the still, the local turntable with its time, or the render server.

## Impact

- Backend:
  - `backend/config/render.yaml`: `final.timeout_multiplier: 36`; the TODO note is resolved.
  - `app/render/guard.py`: drop the local detail-turntable refusal; add the warning text to the quote.
  - `app/render/estimate.py`: an hours-and-minutes wording used by the warning; other estimates are unchanged.
  - `plugins/render_turntable/tool.py`, `plugins/photoreal_detail/tool.py`: the confirmation summaries carry the warning.
  - `app/api/renders.py`, `app/api/apartments.py`: the "approval required" answer carries it.
  - `app/agent/instructions/lighting.md`.
- Frontend: no change. A render's approval reaches the owner as the chat's confirmation card, which already shows the summary text the warning is added to.
- Tests: guard, estimate, render-detail, render-turntable, renders API, tiers (multiplier 36).
- Docs: CLAUDE.md §6 and the workflow PDF (the scratchpad copy).
