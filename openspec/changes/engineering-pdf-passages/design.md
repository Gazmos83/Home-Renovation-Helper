## Context

See `proposal.md` for why. `pdf_blocks` (`backend/app/engineering/blocks.py`) reads each page with `extract_text(extraction_mode="layout")`. Any page with a two-space gap becomes one `table` block, chained to the first page of its run and the previous page through `headers`. `block_text` joins section, headers, content, footnotes and conditions into the embedded text. Pages without such a gap already use `_prose`, which splits on headings and `chunk_text` (1,200 characters, 120 overlap).

Measured on the handbook file (`docs/guidelines/pdf/fpl-gtr-282.pdf`, 546 pages):
- **Plain mode** reads the two columns one after the other (page 100), and it emits table rows as lines, such as `Alder, red Green 0.37 45,000 8,100 …` (page 120).
- **Table captions** read `Table 5–3a. …` and repeat on continuation pages with `—con.` (pages 120–124).
- **Running headers and page labels** come first on the page: "General Technical Report FPL–GTR–282" on 255 pages, `CHAPTER 5 | Mechanical Properties of Wood` on alternating pages, and the page label such as `4–12`.
- **Equations** come out as runs of whitespace-only lines around fragments such as `b 1 /100xxGG S` (page 106).

## Goals / Non-Goals

**Goals:** readable passages in reading order, bounded embedded text, honest block kinds, and table context limited to the table itself.

**Non-Goals:**
- Parsing table cells into columns or typed properties. Table blocks stay `needs_review`, and typed properties stay a manual, reviewed step.
- OCR, figure text and a new PDF library.
- Changing retrieval scoring or the Markdown and HTML extractors.
- Re-ingesting PDFs other than the handbook.

## Decisions

1. **Plain extraction, no new dependency.** Use pypdf `extract_text()` (plain). It follows the content stream, which in this handbook is column order. Alternative: PyMuPDF block coordinates. It is more robust for unusual layouts but adds a dependency with an AGPL licence. Rejected for now; revisit only if a future source extracts badly in plain mode.
2. **Page cleanup before splitting.** Drop whitespace-only lines. From the top of the page, strip up to three leading lines that are the page's label, a bare page number such as `4–12`, or a line found among the first three lines of at least 5 pages; stop at the first other line. A dropped line that starts with `CHAPTER` becomes the page's fallback section, so passages still carry their chapter. The repeat count is taken over the authorised pages only, so the document is still read page by page and no denied page is extracted.
3. **Headings.** Keep `_HEADING` (numbered headings). Add a short-title rule: a line of at most 60 characters and 8 words that starts with a capital letter, does not end in punctuation, contains no digit, follows a line ending in `.`, `:` or nothing, and is followed by a line starting with a capital letter, since a wrapped sentence continues in lower case. The previous line carries over page breaks. It starts a new section, as headings do now. A wrong heading only mislabels a section and never drops text.
4. **Tables by caption, then by rows.**
   - A line matching `^Table \S+\.` opens a table region. The region runs to the next caption, the next heading or the page end.
   - A **data row** is a line with at least 3 numeric tokens, where numeric tokens are at least half of its tokens. Lines between the caption and the first data row are the **column-header lines**.
   - Rows are packed into blocks of at most 1,200 characters. Each block is `kind="table"`, `needs_review`, with `headers=[caption, header lines]`. Non-row lines after the last row become `footnotes`.
   - A caption containing `—con.` or `(continued)`, or a page that starts with data rows while the previous authorised page ended inside a table region, continues that table. Its blocks carry the original caption and headers, and their `pages` hold both page numbers. This replaces the whole-page chaining.
   - Three or more consecutive data rows without a caption also form a table block. The two non-empty lines before them serve as headers.
5. **Prose and equations unchanged in kind.** Non-table text is chunked to 1,200 characters with overlap first, and each chunk then goes through `_prose`. Chunking first matters: `_prose` keeps a whole text containing an equation as one block, which on a full page would exceed the cap in decision 6. Block IDs become `pdf-p{page}-{n}`, as non-layout pages already use.
6. **Hard bound on embedded text.** `MAX_BLOCK_TEXT = 4000` characters for `block_text`. Headers and footnotes are trimmed, never the content, and only after the caption is kept whole. `pdf_blocks` raises if a block would still exceed the bound, so ingestion fails instead of publishing a diluted vector. Alternative: truncate silently in `embed`. Rejected, because it hides the problem.
7. **Re-ingest in place.** The handbook's version keeps its hash, so `ingest-file 284a720a-… pdf/fpl-gtr-282.pdf` re-stages without a new version. `ingest_version` replaces the version's chunks atomically. The rights decision and technical review are attached to the version, so they carry over. Alternative: a new version superseding the old. Rejected: it would require a second rights approval for the same file, and `stage_file` reserves new versions for changed content.

## Risks / Trade-offs

- [Plain mode misorders another publisher's layout] → The tests use a two-column fixture, and the owner spot-check covers the handbook. Other sources are checked when they are onboarded, and decision 1 names the fallback.
- [A numeric-heavy prose line is classed as a table row] → It only becomes a review-pending table block, which never yields a verified value.
- [The short-title rule mislabels a section] → Only the `section` label is wrong, and the text is unaffected.
- [The block count grows several-fold] → Shorter texts embed faster each. The total time stays around an hour, and BGE-M3 batches are unchanged.
- [A re-run is interrupted] → Publication is atomic, so the current 550 blocks stay searchable.

## Migration Plan

1. Implement and test against fixtures. No migration.
2. The owner re-runs the `ingest-file` command for the handbook.
3. Spot-check with the same queries used for the baseline in `tasks.md`.
4. Rollback: revert the code and re-run the same command. Old-style blocks are rebuilt, and nothing else changes.
