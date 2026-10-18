## Why

Onboarding one engineering source takes six hand-typed steps: catalogue YAML and a CLI seed, a rights JSON form, a command-line ingest for files over 50 MB, then separate reviews. Every owner decision is mixed in with boilerplate, which invites copy errors and hides which fields are actually decisions. Autofill the boilerplate and reduce each real decision to one explicit confirmation, without letting the system grant itself permission.

## What Changes

- Depend on the [RAG foundation](../archive/2026-10-15-furniture-engineering-rag-foundation/proposal.md); it owns rights, verification and ingestion rules, and none of them change.
- Show catalogue entries from `config/engineering_sources.yaml` that are not yet registered on the Engineering Knowledge view of the Design Studio's Design Knowledge tab, each with a **Register** button. Registration stays metadata-only and unverified.
- Prefill the rights form: reviewer name, a draft evidence sentence built from the source's own metadata, and a grant **preset** chosen by the owner ("Local use": extraction, local embedding, local retrieval and retention, which ingestion requires; "Local use plus cloud excerpts": adds remote model use). The preset lists the exact operations before **Record approval** is pressed. No preset is selected by default and nothing is recorded without the click.
- Prefill the technical-review form with reviewer and status; it still needs an explicit click after the owner has inspected extracted blocks and properties.
- Add a single **Ingest from official link** action that runs the existing URL ingest for a version with a `source_url` and the required rights, showing the hash, page count and refusal reasons. A raised, explicit size limit applies to this action only (see `design.md`), because the USDA handbook (104 MB) exceeds the 50 MB browser limit.
- **Not changed:** no field is approved automatically. The system never writes rights, verification, `approved_for_embedding` or reviewer decisions without an owner click, and a draft evidence sentence is editable text, not evidence.

**Ladder step:** none; no spec, generator or Blender change. **Agents:** none. **Render guard and bpy allow-list:** unaffected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dev-panel`: adds one-click, prefilled onboarding actions for engineering sources while keeping each rights and verification decision an explicit owner action.

## Impact

- Frontend `routes/admin/Knowledge.tsx` (catalogue list, presets, prefilled forms, ingest button) and its tests; it renders as the Engineering Knowledge view (`/admin/design-knowledge/engineering`).
- Backend `api/admin_knowledge.py`: a read-only route listing unregistered catalogue entries, and a route to ingest from the official link under a size cap; reuses `register_source`, `decide_rights`, `ingest_version` and the pinned-address `KnowledgeFetcher`. No migration.
- A rights decision recorded this way is the same append-only row as today, so revocation, expiry and request-time rechecks are unchanged.
- Cost: about 3–5 developer days.
