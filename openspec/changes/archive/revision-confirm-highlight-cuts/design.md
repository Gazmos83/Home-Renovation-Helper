## Context

See proposal.md for motivation. Today `revise_package.preview` builds the confirmation summary from change lines plus `derived_changes(...)` ("Cut list:" / "Hardware:" lines). The inspector Cut list tab (`CutListTables`) renders the current version's `spec.json` only, with no baseline. Each `PieceVersion` already stores `revised_from`; the version read API does not yet return it.

## Goals / Non-Goals

**Goals:**
- Confirmation text names only what the owner decided (change lines + existing warnings / heads-up / fit lines).
- After the build, the inspector makes added and changed cut and hardware rows obvious in red against `revised_from`.

**Non-Goals:**
- Changing `create_piece` confirmation (it still previews the new piece's cut list and hardware).
- Showing removed rows, drilling-entry diffs, or a side-by-side diff UI.
- Deleting `derived_changes` (keep for unit tests and any future non-confirmation use).
- Changing render guard, bpy allow-list, or generators.

## Decisions

1. **Drop effects from the confirmation only.** In `plugins/revise_package/tool.py` `preview`, stop appending `effects` from `derived_changes`. Keep computing them optional or leave the call unused in preview; `run` already uses `_revised` without effects. Update tests that assert Cut list / Hardware lines in the confirmation.

2. **Baseline is `revised_from`, exposed on the version API.** Add `revised_from` (int or null) to `describe_version` / `VersionInfo` from the house-file row. The inspector loads the baseline version's `spec.json` when `revised_from` is set and that version is built with a readable spec. Fallback: if the row is missing `revised_from` but version > 1, do not guess `version - 1` when the house file has no link — show no highlight. (House-file revisions always set `revised_from`; Studio-route creates may leave it null.)

3. **Client-side row compare.** Compare part rows by `id` on `(l, w, t, qty)`; hardware by `id` on `qty`. New id or changed fields → red text (and a stable marker such as `data-changed` for tests). Prefer existing Tailwind destructive/red tokens so the highlight matches Studio alerts. Module filter still applies; red rows stay red when filtered.

4. **Same component for page and split view.** `InspectorView` fetches the baseline spec and passes a set of changed ids into `CutListTables`; no second UI path.

## Risks / Trade-offs

- [Confirmation no longer shows hardware impact before yes] → Spec and proposal accept this; the fix-shelf question still states confirmat/pin effects before the Designer proposes; the inspector highlights after the build.
- [Baseline version deleted] → No readable baseline → no red rows (safe, matches "no readable prior document").
- [rebuild_piece creates a version with no document changes] → `revised_from` set, compare finds no diffs → no red rows.

## Migration Plan

Deploy backend and frontend together. Old confirmations already answered are unaffected. Existing built versions gain highlights once the API returns `revised_from` and the prior `spec.json` exists.
