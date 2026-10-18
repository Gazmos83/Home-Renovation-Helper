## MODIFIED Requirements

### Requirement: Engineering ingestion preserves complete evidence blocks
Approved PDF, HTML and Markdown content SHALL retain section hierarchy, page references, source revision, table row labels/headers/units/footnotes and equation definitions/conditions. A numerical value SHALL NOT be detached from its product, grade, thickness, test/load conditions or units. Unreadable or ambiguous blocks SHALL be reported for review and SHALL NOT become verified numerical evidence. Local paths SHALL remain confined; remote content SHALL respect identity, robots, SSRF, pacing and refusal restrictions without expanding permitted retail pricing sources.
PDF text SHALL be extracted in reading order, so that text from separate columns of one page is never merged line by line. PDF content SHALL be split into passage-sized blocks with the same size bound as Markdown and HTML prose, never one block per page. A block's kind SHALL describe its content: prose is a paragraph, and only text belonging to a captioned table or made of tabular rows is a table. Table context carried into a block SHALL be limited to that table's caption, column headers, units and conditions, never whole neighbouring pages. Running page headers and footers SHALL NOT be stored as passages. The text embedded for any one block SHALL stay within a fixed bound.

#### Scenario: Material table spans a page boundary
- **WHEN** an approved table has its headers on one page and a thickness row on the next
- **THEN** the retrieved row carries its headers, unit, grade, conditions and both relevant page references

#### Scenario: Equation damaged by extraction
- **WHEN** extraction cannot reliably retain an equation's symbols or units
- **THEN** the block is marked for review and no verified engineering property is generated from it

#### Scenario: Approved source refuses fetching
- **WHEN** robots rules or the host refuse an approved engineering URL
- **THEN** ingestion reports the refusal, keeps metadata and does not retry through another identity or route

#### Scenario: Two-column PDF page
- **WHEN** an approved PDF page sets its prose in two columns
- **THEN** each column's sentences stay contiguous in the extracted passages, and the page yields several paragraph blocks carrying that page's reference and nearest heading

#### Scenario: Captioned table continues on the next page
- **WHEN** a table caption and its column headers are followed by data rows, and the table continues on a page marked as a continuation
- **THEN** the rows on both pages become review-pending table blocks that each carry the caption and column headers, with no other page's full text attached

#### Scenario: Running header repeats on every page
- **WHEN** the same header or footer line appears on many pages of an approved PDF
- **THEN** no passage consists only of that line, and it does not displace the page's own text in search results
