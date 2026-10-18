## Context

See `proposal.md` for the reasons. The relevant parts that exist today:

- **Source catalogue.** `config/engineering_sources.yaml` seeds `knowledge_sources` and `knowledge_source_versions`. Each version stores `collections` (JSONB) and typed `attributes`: `applicable_furniture`, `edition`, `page_section`, `jurisdiction`, `standard_or_model` and so on. `superseded_by` marks old editions.
- **Rights.** Rights are append-only `knowledge_rights_decisions`. `registry.permits()` and `require_rights()` check a `Scope` (`local_retrieval`, `retention`, `remote_model_use`) against the current decision for exact pages and blocks.
- **Stored text.** Published text lives in `engineering_chunks`, one row per block, with `ordinal`, `kind`, `content` and `provenance` (page or section).
- **Reports.** `GET /packages/{id}/versions/{v}/engineering/reports` is owner-gated and returns `report_copy(remote=False)`. The frontend never calls it.
- **Approval.** `PUT …/versions/{v}/approval` sets `approved_at` on the house-file row.
- **Modules.** `ModuleIn` is strict (`extra="forbid"`). Optional lists are dropped from the dump when empty, as with `hanging_rails`, so older documents normalise unchanged.

## Goals / Non-Goals

**Goals:**
- A pure, deterministic function from (normalised spec, current catalogue) to a reading list, with no I/O beyond the database and no model.
- Rights rechecked on every block read, reusing the existing registry checks rather than a parallel rule.
- The new `mounting` field has no effect on derivation or the generator.

**Non-Goals:**
- Ranking by semantic search. Matching is by tags only, so the list is explainable and reproducible.
- Recording which sources the owner read, or tying approval to having read them.
- Showing reading lists for room compositions.

## Decisions

1. **Rule table in `config/reading_rules.yaml`, not in code.** Each item kind lists `applicable_furniture` values and `collections`. Initial values:
   - `wall_shelf`: furniture `shelf` and `wall_shelf`; collection `kitchen_wall_anchoring`.
   - `wall_module`: furniture `wall_cabinet` and `kitchen_wall_cabinet`; collection `kitchen_wall_anchoring`.

   The table is loaded and validated at startup, and a malformed file is refused by name, as with the plugin manifests. *Alternative:* local hybrid search per item. Rejected because its results move with the corpus and thresholds, and a reading list has to be explainable ("matched `shelf`").

2. **Metadata from every registered source, whatever its rights.** Citations and links are facts, and the engineering spec already lets metadata reach even cloud agents. Pending or revoked rights only affect "Read here". *Alternative:* list only rights-approved sources. Rejected because it would hide exactly the paywalled standards the owner most needs to know exist.

3. **"Read here" is bounded to the version's own sources.** The block route accepts a source version id only if it is on that version's computed reading list or cited by its stored reports' evidence snapshot. This stops the route becoming a general corpus browser, and keeps each read tied to a purpose. It checks `local_retrieval` and `retention` through `registry.permits()` per block, so page or block grants and expiry apply. Unpermitted blocks are skipped. If none are permitted, the reason is returned.

4. **Separate owner routes, no agent tool.** The routes are `GET …/versions/{v}/reading` and `GET …/versions/{v}/reading/sources/{version_id}/blocks?page=`, alongside `api/engineering.py` with `require_owner`. No plugin or tool exposes them, so the text cannot reach graph state. Langfuse only instruments model calls, so no export path exists.

5. **The reports view reuses the existing endpoint unchanged.** The tab calls the current reports route. Its `remote=False` copy already carries evidence packets with text and handles unavailable evidence.

6. **`mounting` is an optional `Literal["floor", "wall"]`, omitted from the dump when unset.** `ModuleChange` gains the same field, plus an explicit clear the way other optional module fields are cleared. Derivation and the generator ignore the field. A test proves the cut list, hardware and drilling list are identical with and without it. *Alternative:* infer from `z` and the modules below. Rejected by the owner's decision of 2026-10-17: a guess can be wrong, and reading on wall fixing must not depend on one.

## Risks / Trade-offs

- [Catalogue tags are sparse. Today only DIN EN 15939 carries `wall_cabinet`, and nothing covers plasterboard or masonry anchors.] → Gaps are shown per item instead of hidden. Adding tags or sources is a catalogue edit, not a code change.
- [The owner may read the list as a sign-off.] → A fixed NOT VERIFIED notice on every list, no "safe" wording anywhere, and approval stays independent of the list.
- [Large sources, such as the 104 MB USDA handbook, have many blocks.] → Paged reads of a fixed size, ordered by `ordinal`, loaded only on "Read here".
- [Rights revoked while a page is open.] → Each page request rechecks. Text already on screen is not recalled, which the existing rules accept for local history.

## Migration Plan

No database migration. Deploy the backend with `config/reading_rules.yaml`, then the frontend. To roll back, remove the routes and the tab. The `mounting` field can stay, since it changes no derived output.
