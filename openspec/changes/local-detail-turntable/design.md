## Context

- **The refusal.** `quote()` in `app/render/guard.py` refuses `source == "detail"`, `kind == "turntable"`, `target == "local"` (two-tier-renders). `render_detail` already defaults `kind` to `"still"`, and its description says a turntable needs the render server.
- **Approval text.** It is built in three places, all from `RenderQuote.summary` and `estimate_text`:
  - `render_turntable` and `render_detail` previews: a `Confirmation` summary shown as the chat's confirmation card;
  - `guard_node`: the interrupt;
  - `api/renders.py` and `api/apartments.py`: the `approval_required` answer.
- **Wording.** `estimate.describe` words anything over a minute as "about N minutes", so 12 200 s reads "about 203 minutes".
- **Timeout.** The runner stops a job after `blender_timeout_seconds × tier.timeout_multiplier`: local, remote and pod jobs all use it. `final` is 24 (4 h at 600 s).
- **Lighting instructions.** `lighting.md` tells the agent to leave the kind out on the laptop, and to offer the still when the tool says a turntable runs only on the server.

## Goals / Non-Goals

**Goals:**
- A local detail turntable is allowed behind the typed "yes".
- Every approval quoted above 20 minutes says how long it takes, and how rough that figure is.
- A long local render says the laptop will be busy.
- A final can run 6 hours.

**Non-Goals:**
- Changing the estimate formula, the Cycles multiplier or its calibration.
- Making the timeout follow the estimate (the owner chose a fixed 6 h).
- Warning on drafts, which never reach 20 minutes and need no approval.
- Changing where finals run, or the render server's own checks.

## Decisions

1. **The warning lives on the quote.** `RenderQuote` gains a `warning` property, empty at or below `LONG_RENDER_SECONDS = 20 * 60`. Above it, the text is built from the quote: estimate, `target`, `source` and `kind`.
   - For a detail turntable, it also needs the detail still's estimate. `quote()` computes it with the same tier and benchmark (frames = 1), stores it on the quote (`still_seconds`), and the text reads it.
   - The approval surfaces append `quote.warning` to their summary. `api/renders.py` and `apartments.py` also return it as a `warning` field, so nothing needs a second copy of the wording.
   - *Alternative:* build the text in each tool. Rejected because three copies of the same wording would drift.

2. **Hours only in the warning.** A new `describe_long()` in `estimate.py` words a time as "about 3 h 24 min" ("about 1 h 0 min" on the hour; minutes below an hour), and the warning uses it. `describe()` and every existing estimate stay as they are, so the render-guard scenario "about 101 minutes" still holds. *Alternative:* switch `describe()` to hours everywhere. Rejected because it rewords every estimate and spec scenario for a warning-only need.

3. **Remove the refusal, keep the still default.** The guard rule goes. `render_detail` keeps `kind="still"` as its default, and its description now says a turntable runs on the laptop or the server with its time shown. A turntable is still something the owner asks for.

4. **Timeout by configuration.** `final.timeout_multiplier: 36` in `render.yaml`, which resolves its `TODO(user)` note with the owner's choice of 2026-10-15. A remote final is bounded the same way. Nothing else changes in the runner.

5. **Lighting instructions.** When the owner asks for a detail turntable, the agent first offers the three choices in words: a still now, the laptop turntable with its estimate (taken from a preview of `render_detail`), or the server when finals go there. It then calls `render_detail` with the chosen kind. The guard's warning still appears in the approval.

## Risks / Trade-offs

- **Six hours may not be enough.** The ×30 Cycles multiplier is uncalibrated, and heavy lighting can push a turntable past 6 h. Then it fails at the limit, stating the timeout, and nothing is published. The warning says so, and a still first calibrates the multiplier.
- **The laptop is unusable for builds for hours.** That is accepted by the owner's typed yes, after the explicit warning. A live detail-pass command is refused while the job runs, as today.
- **The scenario name "Local detail turntable refused" stays** while its body now allows the turntable. OpenSpec refuses to drop a scenario name from a modified requirement, so it is kept and its content says the opposite.
