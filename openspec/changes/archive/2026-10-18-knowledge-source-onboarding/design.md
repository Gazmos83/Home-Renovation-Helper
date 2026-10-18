## Context

See `proposal.md`. Today `ingest_version` already fetches a version's `source_url` when no file is staged, checking robots rules, rights and hash. The blockers are the 50 MB `guideline_upload_max_bytes` (shared with browser uploads) and the lack of a UI path. The foundation's rules stay as they are.

## Goals / Non-Goals

**Goals:** fewer typed fields, one click per owner decision, no new way for the system to grant itself permission.

**Non-Goals:** automatic rights or verification decisions, AI-drafted legal conclusions, new metadata fields (a separate decision), bulk approval of several sources at once, changes to retrieval or the calculators.

## Decisions

1. **Presets fill the existing rights payload.** Both presets include retention, since ingestion requires it for every block. A preset is a client constant mapped to the existing `RightsIn` grants; the server needs no new rights code. Alternative: server-side "approve preset" endpoint; rejected because it adds a second path that could drift from the validated one.
2. **Draft evidence is a template.** It quotes the source's own metadata (publisher, edition, URL, licence note) and says what the developer must confirm. It is editable, and the form still requires non-empty reviewer and evidence. Alternative: model-written rationale; rejected, since a model must not author rights evidence.
3. **Unregistered list is read-only.** A GET compares catalogue keys and metadata with stored versions using the same equality as `seed_catalogue`; Register calls `register_source`. The CLI seed stays.
4. **Larger cap on the link action only.** Add `engineering_link_max_bytes` (default 150 MB) used by the ingest route's fetcher; the 50 MB browser limit and the CLI are untouched. Memory and time are bounded by streaming checks in `KnowledgeFetcher._get`. Alternative: raise the global limit; rejected as it widens the browser upload surface.
5. **Technical review is not collapsed.** Only reviewer and status are prefilled; there is no "approve everything" button.

## Risks / Trade-offs

- A convenient preset could be clicked without reading it → the preset lists its operations beside the button, none is preselected, and decisions stay append-only and revocable.
- A 150 MB download holds memory while parsing → streamed cap, one fetch at a time, failure leaves prior content (existing atomic publish).
- A public-domain claim may be wrong for embedded third-party figures → page-scoped grants remain available and are shown in the form.

## Open Questions

- Whether to allow the cap to be set from the settings panel rather than environment only.
