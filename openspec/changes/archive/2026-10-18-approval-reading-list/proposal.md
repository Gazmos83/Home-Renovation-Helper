## Why

Most engineering sources will hold only "Local use" rights: they can be searched on the laptop, but their text may not reach the cloud agents. Today that leaves the owner with a chat line reading "Metadata only … not verified" and no way to read the passage in the Studio. The owner-only report endpoint already returns local excerpts, but no screen calls it. Before hanging a shelf or cabinet on a wall, the owner wants to read the relevant sources themselves. The owner also wants the engineering maths kept away from the LLM, while still seeing the piece in the room. A reading list built from catalogue metadata by fixed rules does this lawfully, because citations and links are facts. Anything the owner opens to read stays on the laptop.

## What Changes

- **Reading list on approval.** When a version is approved, the Studio shows a recommended-reading list for each wall-hung item in it. Each entry holds title, publisher, edition, standard or model, page or section, jurisdiction, verification status and the catalogue's HTTPS link. Sources are chosen by a checked-in rule table (`config/reading_rules.yaml`) matching each item's kind to a source's `applicable_furniture` and `collections`. No model call is involved, and the list is never sent to OpenRouter or Langfuse.
- **Gaps stated, not filled.** When no recorded source covers an item, the list says so for that item. Every list carries a fixed notice: it is recommended reading, not a safety approval, and wall fixing depends on the wall, the anchor and the load. The notice says **NOT VERIFIED**, consistent with `engineering-safety`.
- **Local reading.** The owner can open a listed source's published blocks in the Studio, but only while current rights allow local retrieval and retention. Rights are rechecked on every read. The text is served to the owner's browser only. A source without those rights shows its link and the reason it can't be read in the app.
- **Stored engineering reports shown locally.** The same inspector tab lists the version's stored engineering assessment reports through the existing owner endpoint, with their stale state, `NOT_ESTABLISHED` conformity and evidence passages. It shows what already exists: no new calculation and no automatic re-run.
- **Wall-mounted modules are marked explicitly.** Modules get an optional `mounting` field (`floor` or `wall`). The cut list, hardware, drilling list and model are unchanged by it. `revise_package` can set or clear it. Wall shelves are always wall-hung. A module without `mounting: wall` gets no reading list, and its height is never used to guess.

**Ladder and agents.** The `mounting` field is a ladder step 2 generator extension: the schema, the Designer's revision tool and the import validation grow; generator output does not change. The reading list, local reader and reports view are Studio and API work with no agent involvement. The Designer (`revise_package`) is the only agent touched. The render guard and the `bpy` allow-list are not affected: nothing renders, nothing goes over the socket.

## Capabilities

### New Capabilities
- `installation-reading`: rule-matched recommended reading for wall-hung items of an approved version, the stated gaps and notice, local reading of rights-eligible source blocks, and the guarantee that none of it reaches a model or tracing.

### Modified Capabilities
- `furniture-packages`: a module accepts an optional `mounting` (`floor` | `wall`) that `revise_package` can set or clear, with no effect on derived outputs.
- `studio-ui`: the inspector gains a Reading tab with the reading list, local source reading and the version's stored engineering reports.

## Impact

- **Backend:** `app/blender/schemas.py` (`ModuleIn`, `ModuleChange`); `app/agent/revise.py` change lines; new `app/engineering/reading.py` (rule matching, eligibility check, block paging); new owner routes under `/packages/{id}/versions/{v}/reading`; `config/reading_rules.yaml`.
- **Frontend:** `components/inspector/InspectorView.tsx`, a new `ReadingTab.tsx`, `lib/api.ts`.
- **Data:** no migration. Reads `knowledge_sources`, `knowledge_source_versions`, `knowledge_rights_decisions`, `engineering_chunks` and the existing report tables.
- **Not in scope:** an LLM summary of passages, a local answering model, choosing anchors or calculating wall loads, the import template guide naming `mounting`, and freestanding pieces.
