## 1. Extraction

- [x] 1.1 Switch `pdf_blocks` to plain extraction and add page cleanup (whitespace-only lines, page labels, repeated top lines, `CHAPTER` line kept as fallback section); verify with a fixture whose pages repeat a running header and a page label that neither becomes a passage and the chapter becomes the section.
- [x] 1.2 Split prose into passage-sized blocks with the short-title heading rule, IDs `pdf-p{page}-{n}`; verify with a two-column fixture page that each column's sentences stay contiguous, the page yields several `paragraph` blocks with its page reference, and none exceeds 1,200 characters of content.
- [x] 1.3 Detect captioned tables and caption-less row runs as `needs_review` `table` blocks carrying caption and column-header lines, with trailing notes as footnotes; verify a fixture table's row block holds the caption, units line and row values, and a prose page yields no `table` block.
- [x] 1.4 Continue tables across pages (`—con.` caption, or a page that opens with rows after a table) with both page numbers and no neighbouring page text; rewrite `test_cross_page_pdf_layout_retains_context_and_requires_review` to the new rule and verify it, keeping its intent (headers, units, conditions and both pages on the continued row).
- [x] 1.5 Enforce `MAX_BLOCK_TEXT` (4,000 characters) on `block_text`, trimming headers and footnotes but never content or caption, and refusing if still over; verify an oversized-header fixture is trimmed and an unbounded one raises.
- [x] 1.6 Verify the existing PDF tests still pass unchanged (sections, damaged equation `needs_review`, AES-encrypted file, partial page permission never extracting other pages); run the engineering tests on a throwaway test database plus `ruff check .`.

## 2. Handbook re-ingestion

- [x] 2.1 Dry-run `pdf_blocks` on `docs/guidelines/pdf/fpl-gtr-282.pdf` without writing to the database; verify the block count, the kind counts and that the largest `block_text` is ≤ 4,000 characters, and spot-read pages 100 (two columns), 120 (Table 5–3a) and 155 (Creep and Relaxation).
  Checks 2026-10-18: engineering and kitchen-engineering tests 126 passed on a throwaway database (dropped afterwards); `ruff check .` clean. Dry run on the handbook, no database writes, about 15 s: 2,391 blocks (2,121 paragraph, 192 table, 63 equation, 15 unreadable), largest `block_text` 3,590 characters, average 888, all IDs unique, running header in no block. Page 100 reads both columns in order under "Dynamic Vapor Sorption Measurements" and "Rate of Sorption"; page 120 gives 14 `table` blocks under the Table 5–3a caption; page 124 rows cite pages [120, 124]; page 155 splits into "Time Under Load", "Creep and Relaxation" and "Duration of Load".
- [ ] 2.2 Owner re-runs `uv run python -m app.engineering ingest-file 284a720a-3bde-4336-ac1b-6cc6af134f42 pdf/fpl-gtr-282.pdf` (about an hour); verify it prints `"state": "published"` and the version still shows the Local use grant and the recorded technical review.
- [ ] 2.3 Spot-check against the baseline below; verify each query's expected page is in the top 5, each result is a single readable passage, and the "Alder, red" row from page 120 appears as a `table` block with the Table 5–3a caption.

Baseline 2026-10-18 (550 page blocks; pages listed per result, first page is the chained run start):
- "creep of wood under sustained load" → [80,155,156] 0.51, [80,154,155] 0.50, [80,130,131], [80,131,132], [501,503,504]. Expected: page 155.
- "modulus of elasticity of red alder at 12% moisture content" → [80,117,118] 0.42, [80,118,119], [189,199,200], [80,119,120], [189,198,199]. Expected: page 120.
- "withdrawal resistance of wood screws" → [189,214,215] 0.49, [189,213,214], [189,215,216], [189,206,207], [189,216,217]. Expected: the screw withdrawal passages in Chapter 8 (pages 213–215).
