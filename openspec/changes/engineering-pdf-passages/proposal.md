## Why

The Wood Handbook (FPL-GTR-282) is published, but its passages are hard to search. `pdf_blocks` treats every page with two-space gaps, which means every two-column page, as one whole-page "table" block. pypdf's `layout` mode interleaves the two columns line by line. Each such block also carries the first page of its run and the previous page as headers, and all of them go into the embedded text. On the published version, 521 of 550 blocks are "table" blocks averaging about 25,000 characters (largest 149,000), and most of them embed page 80 or a similar run-start page. BGE-M3 sees only the start of a long input, so most vectors mean nearly the same thing. Searches score about 0.35 to 0.45 regardless of the query, and the passages are unreadable as quotes.

## What Changes

- Extract PDF text in reading order: pypdf `plain` mode, which on this handbook reads column by column, instead of `layout`.
- Split each page into passage-sized blocks at paragraph boundaries, with the same size limit Markdown and HTML already use (about 1,200 characters), carrying the nearest heading as the section.
- Classify blocks honestly:
  - "paragraph" for prose;
  - "table" only for text under a table caption (`Table 5–3a. …`) or for mostly numeric rows;
  - "equation" for formula fragments, as today;
  - "unreadable" for pages without text, as today.
- Table blocks carry their caption and column-header lines as headers, including on continuation pages (`—con.`), and stay `needs_review`. They no longer carry whole neighbouring pages.
- Drop whitespace-only lines and running headers and footers that repeat on many pages, such as "General Technical Report FPL–GTR–282".
- Bound the embedded text of every block, so no block can again carry a whole run of pages.
- Re-ingest the handbook in place under its existing version `284a720a-…`. The file hash is unchanged, so the rights approval and technical review stay valid. Publication remains atomic: if the re-run fails, the current 550 blocks stay searchable.
- **Not changed:** rights checks, the remote-use boundary, verification rules (no extracted table becomes a verified value), retrieval scoring, the Markdown and HTML extractors, and the CLI and link-ingest commands.

**Ladder step:** none; no spec JSON, generator or Blender change. **Agents:** none changed. The Designer and Researcher, which call engineering search, receive smaller, readable passages. **Render guard and bpy allow-list:** unaffected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engineering-knowledge`: the requirement "Engineering ingestion preserves complete evidence blocks" gains rules for PDFs: passages in reading order, passage-sized blocks, kinds that match the content, and table headers repeated on continuation pages instead of whole neighbouring pages.

## Impact

- Backend `app/engineering/blocks.py` (`pdf_blocks` and helpers) and `tests/test_engineering_ingestion.py`. The current test `test_cross_page_pdf_layout_retains_context_and_requires_review` expects whole-page layout blocks, so it is rewritten to the new rule, keeping its intent: a continued table keeps its headers and both page references.
- No migration, API or frontend change. `EvidenceBlock` keeps its fields and kinds.
- Already published PDF versions keep their old blocks until re-ingested. Only the handbook is re-ingested here.
- Block IDs of re-ingested PDFs change, for example from `pdf-p120-layout` to `pdf-p120-3`. No property record cites the handbook yet, and its rights grant is whole-document, so nothing breaks.
- Re-embedding the handbook takes about an hour on the laptop CPU, run by the owner.
- Cost: about 1–2 developer days.
