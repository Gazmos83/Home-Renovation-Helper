## Context

- `render_runs` / `render_feedback` (feedback-capture) store one rating per render run with the slot and model that started the render. A version without a render has no run, so it cannot be rated. The rating plumbing (`app/feedback/ratings.py`, `plugins/render_feedback`, `app/api/feedback.py`, `tracing.record_feedback`, `routes/admin/Feedback.tsx`) is the pattern to follow.
- `reviews` / `review_items` hold the Reviewer's findings. `house_file.latest_open_items` shows only the **newest review** of the current version. Storing an owner verdict as a `Review` would hide the Reviewer's items behind it, and `review_items` columns (`image`, `expected_source`, `aspect`) do not fit an owner note.
- `piece_versions` (`package_id`, `version`, `revised_from`, `changes`, `approved_at`) records no origin. Every version an agent makes goes through `house_file.record_version`, called from `plugins/create_piece/tool.py` and `plugins/revise_package/tool.py` (`record_next`, also used by `design_import` and other revision paths). The calling `ToolContext` carries `slot` and `model`.
- `foreman.py` builds the house-file slice: `include_review_items` → `latest_open_items`, `render_ratings` → `recent_for_piece`. `prompts.py` renders those lines with `neutralise`.
- The owner's "Decisions so far" note is out of scope and unchanged.

## Goals / Non-Goals

**Goals:**
- A durable, per-version "matches / doesn't match" record that works without a render.
- Open mismatches reach the Designer through the existing slice.
- Counts per producing slot and model on the developer panel.

**Non-Goals:**
- No numeric or star scale. Two values match the question the owner is answering.
- No automatic action on a verdict: no rollback, no approval block, no routing change, no automatic resolving when a later version is marked `matches`.
- No retro-fitting of slot and model onto existing versions. Their origin is unknown and shows as such.
- No Reviewer change. The Reviewer still needs a render and keeps its own items.

## Decisions

1. **A separate `version_verdicts` table, one row per version.** Primary key `(package_id, version)`, foreign key to `piece_versions` with `ON DELETE CASCADE`. Columns: `verdict` (`matches` | `mismatch`), `note` (text ≤ 1 000, required for `mismatch` by a check constraint), `status` (`open` | `resolved` | `dismissed`, null for `matches`), `status_at`, `created_at`, `updated_at`. *Alternative:* reuse `reviews`. Rejected because of the newest-review shadowing above and the ill-fitting columns. *Alternative:* key it to the render run like ratings. Rejected because the whole point is versions without renders.
2. **Origin on `piece_versions`.** Add nullable `slot` (String 32) and `model` (String 128). `record_version(..., slot=None, model=None)`. `create_piece` and `record_next` pass `ctx.slot` and `ctx.model`. Homeowner routes that list versions keep their response shape: the columns are never serialised there.
3. **Domain module `app/feedback/verdicts.py`** mirroring `ratings.py`: `give`, `clear`, `set_status`, `current`, `open_for_piece(limit=5)`, `summary(days=30)`, `notes(slot, model)`. It raises a `VerdictRefused(reason, status)` like `FeedbackRefused`. The note is stripped and `neutralise`d before storage. Re-giving a verdict resets `status` to `open` for `mismatch`.
4. **Routes.** Owner: `GET/PUT/DELETE /api/packages/{id}/versions/{n}/verdict`, `PATCH .../verdict/status` with `resolved` | `dismissed`. Developer (gated): `GET /api/admin/feedback/verdicts` (summary) and `/api/admin/feedback/verdicts/notes?slot=&model=`. These live beside the existing feedback routers in `app/api/feedback.py`.
5. **Chat tool `record_version_verdict`** in a new plugin `version_verdict` (role `designer`, toggleable, on by default). Args: `verdict`, `note`, optional `version`. The package comes from `ctx.package_id`. `preview` returns a `Confirmation`, and `run` refuses without `ctx.approved`, as in `render_feedback`. Designer is the role because it owns versions and is the agent that must act on the note.
6. **Slice.** New `MemorySettings.include_version_verdicts: bool = True`. `foreman.py` reads `verdicts.open_for_piece` when it is on. `prompts.py` adds an "Owner's verdicts (version does not match what was confirmed):" block, one neutralised line per verdict with its version. Fixed limit of 5, newest first, like the render-ratings default.
7. **Tracing.** `tracing.record_verdict(package_id, version, verdict, note, slot, model)` writes a short feedback trace tagged `version-verdict`, `verdict:<v>`, `slot:<s>`, `model:<m>`. There is no trace id to score, because a version does not keep the creating turn's trace. That is acceptable for a first cut.
8. **UI.** A `VersionVerdict` component in `InspectorView` above the tab bar, using TanStack Query against the owner routes and invalidating on save. The admin `Feedback.tsx` gains a second table and notes list. `Memory.tsx` gains the toggle.

## Risks / Trade-offs

- **Open verdicts accumulate if the owner never closes them** → capped at 5 in the context. The inspector shows the status, so stale ones are visible and dismissable.
- **The alias slug `~deepseek/deepseek-v4-flash-latest` hides model changes** → counts per slug can mix two underlying models. The verdict time lets the developer see when a trend changed. Recording the resolved model is out of scope.
- **Old versions have no origin** → they group under "no slot / no model". Amesbury v4 lands there, so it informs the Designer but not the per-model count.
- **Note text is owner input that reaches a prompt** → stored neutralised and shown inside the house-file block, which is labelled as the owner's data and not an instruction, as review items are.

## Migration Plan

Alembic `0027_version_verdicts`: create the table and add the two nullable columns. Downgrade drops both. No data backfill.

## Open Questions

None. Assumptions recorded: an open mismatch does not block approval, and a later `matches` verdict does not resolve an earlier version's mismatch automatically. Both are `TODO(user)` to revisit if the owner wants otherwise.
