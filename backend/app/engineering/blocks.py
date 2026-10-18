"""Provenance-first extraction; ambiguous layouts require reviewed transcription.

No parser promotes an extracted table/equation to a verified numerical fact.
PDF text is read in reading order and split into passages; table rows stay
review-pending and carry only their own caption and column headers.
"""

import io
import re
from collections import Counter
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag
from pypdf import PdfReader

from app.engineering.schemas import EvidenceBlock
from app.ingestion.extract import chunk_text

_HEADING = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*\s+[A-ZÄÖÜ]|§\s*\d)")
_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_EQUATION = re.compile(r"(?:\$\$|\\\[|[A-Za-z][\w_]*\s*=\s*[^=]|[∑∫√])")
_CAPTION = re.compile(r"^(Table\s+[\w–\-.]*\w)\.\s")
_CONTINUED = re.compile(r"(?:—|-)\s*con\.|\(continued\)", re.IGNORECASE)
_NUMBER = re.compile(r"^[(\[]?[-–+]?\d[\d,.]*%?[)\],]?$|^[—–-]$")
_FOOTNOTE = re.compile(r"^[a-z][A-Z]")
_PAGE_NUMBER = re.compile(r"^(?:\d+(?:[–-]\d+)?|[ivxlc]+)$", re.IGNORECASE)
_REPEATED_PAGES = 5
_HEADER_LINES = 3
_CONTEXT_LIMIT = 1000
MAX_BLOCK_TEXT = 4000


def block_text(block: EvidenceBlock) -> str:
    """The indivisible unit for embedding, retrieval and budget fitting."""
    pieces = [
        block.section or "",
        *block.headers,
        block.content,
        *block.footnotes,
        *block.conditions,
    ]
    return "\n".join(dict.fromkeys(piece for piece in pieces if piece)).strip()


def _prose(
    lines: list[str],
    section: str | None,
    prefix: str,
    ordinal: int,
    pages: list[int],
    printed: list[str],
) -> list[EvidenceBlock]:
    text = "\n".join(lines).strip()
    if not text:
        return []
    equation = bool(_EQUATION.search(text))
    # Equations and their neighbouring definitions stay together for review.
    parts = [text] if equation else chunk_text(text)
    return [
        EvidenceBlock(
            block_id=f"{prefix}-{ordinal + index}",
            kind="equation" if equation else "paragraph",
            content=part,
            pages=pages,
            printed_pages=printed,
            section=section,
            verification_status="needs_review" if equation else "unverified",
        )
        for index, part in enumerate(parts)
    ]


def markdown_blocks(
    text: str,
    *,
    prefix: str = "md",
    pages: list[int] | None = None,
    printed: list[str] | None = None,
) -> list[EvidenceBlock]:
    lines = text.splitlines()
    result: list[EvidenceBlock] = []
    pending: list[str] = []
    section: str | None = None
    headings: list[tuple[int, str]] = []
    page_numbers, page_labels = pages or [], printed or []

    def flush() -> None:
        result.extend(
            _prose(pending, section, prefix, len(result), page_numbers, page_labels)
        )
        pending.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith("#"):
            flush()
            heading = line.strip()
            level = len(heading) - len(heading.lstrip("#"))
            headings = [(depth, title) for depth, title in headings if depth < level]
            headings.append((level, heading.lstrip("#").strip()))
            section = " / ".join(title for _, title in headings)
            pending.append(line)
            index += 1
            continue
        if (
            index + 1 < len(lines)
            and "|" in line
            and _SEPARATOR.match(lines[index + 1])
        ):
            flush()
            header = line.strip()
            start = index
            index += 2
            rows: list[str] = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(lines[index].strip())
                index += 1
            # Keep all surrounding conditions in the section with every row.
            context_start = start
            while context_start > 0 and not lines[
                context_start - 1
            ].lstrip().startswith("#"):
                context_start -= 1
            context_end = index
            while context_end < len(lines) and not lines[
                context_end
            ].lstrip().startswith("#"):
                context_end += 1
            before = "\n".join(lines[context_start:start]).strip()
            after = "\n".join(lines[index:context_end]).strip()
            expected_columns = len(header.strip("|").split("|"))
            for row in rows:
                ambiguous = len(row.strip("|").split("|")) != expected_columns
                result.append(
                    EvidenceBlock(
                        block_id=f"{prefix}-{len(result)}",
                        kind="table",
                        content=row,
                        headers=[header],
                        footnotes=[after] if after else [],
                        conditions=[before] if before else [],
                        pages=page_numbers,
                        printed_pages=page_labels,
                        section=section,
                        verification_status="needs_review"
                        if ambiguous
                        else "unverified",
                    )
                )
            continue
        pending.append(line)
        index += 1
    flush()
    return result


def _data_row(line: str) -> bool:
    tokens = line.split()
    numeric = sum(1 for token in tokens if _NUMBER.match(token))
    return numeric >= 3 and numeric * 2 >= len(tokens)


def _short_title(line: str, previous: str | None, following: str | None) -> bool:
    # A heading ends the prior sentence and is followed by a new one, never a wrapped line.
    return (
        len(line) <= 60
        and len(line.split()) <= 8
        and line[:1].isupper()
        and line[-1] not in ".,;:"
        and "," not in line
        and not any(character.isdigit() for character in line)
        and (previous is None or previous[-1] in ".:")
        and following is not None
        and following[:1].isupper()
    )


def _bounded(block: EvidenceBlock) -> EvidenceBlock:
    """Trim context, never content or caption, so one vector stays one passage."""
    if len(block_text(block)) > MAX_BLOCK_TEXT:
        block.footnotes = (
            [] if not block.footnotes else ["\n".join(block.footnotes)[:_CONTEXT_LIMIT]]
        )
    if len(block_text(block)) > MAX_BLOCK_TEXT and len(block.headers) > 1:
        rest = "\n".join(block.headers[1:])[:_CONTEXT_LIMIT]
        block.headers = [block.headers[0], rest]
    if len(block_text(block)) > MAX_BLOCK_TEXT:
        raise ValueError(
            f"{block.block_id}: evidence block exceeds {MAX_BLOCK_TEXT} characters"
        )
    return block


class _Table:
    def __init__(self, caption: str | None, number: str | None, page: int, label: str):
        self.caption, self.number = caption, number
        self.first_page, self.first_label = page, label
        self.headers: list[str] = [caption] if caption else []
        self.rows: list[str] = []
        self.footnotes: list[str] = []


def _page_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def pdf_blocks(
    content: bytes, *, allowed_pages: Iterable[int] | None = None
) -> list[EvidenceBlock]:
    reader = PdfReader(io.BytesIO(content))
    labels = reader.page_labels
    selected = set(allowed_pages) if allowed_pages is not None else None
    if selected is not None and any(page > len(reader.pages) for page in selected):
        raise ValueError("approved physical page is outside the PDF")
    # Plain mode follows the content stream, which keeps columns in reading order.
    texts = {
        index: page.extract_text() or ""
        for index, page in enumerate(reader.pages, 1)
        if selected is None or index in selected
    }
    # Running headers and footers repeat among the first lines of many pages.
    repeated = Counter(
        line
        for text in texts.values()
        for line in set(_page_lines(text)[:_HEADER_LINES])
    )
    result: list[EvidenceBlock] = []
    section: str | None = None
    chapter: str | None = None
    table: _Table | None = None
    first_pages: dict[str, tuple[int, str]] = {}
    previous_page = 0
    previous: str | None = None

    def emit_table(index: int, label: str) -> None:
        if table is None or not table.rows:
            return
        pages = sorted({table.first_page, index})
        printed = list(dict.fromkeys([table.first_label, label]))
        for part in chunk_text("\n".join(table.rows), overlap=0):
            result.append(
                _bounded(
                    EvidenceBlock(
                        block_id=f"pdf-p{index}-{len(result)}",
                        kind="table",
                        content=part,
                        headers=list(table.headers),
                        footnotes=list(table.footnotes),
                        pages=pages,
                        printed_pages=printed,
                        section=section,
                        verification_status="needs_review",
                    )
                )
            )
        table.rows, table.footnotes = [], []

    def flush(pending: list[str], index: int, label: str) -> None:
        # Chunk first, so an equation keeps its neighbours without swallowing a page.
        for part in chunk_text("\n".join(pending)):
            result.extend(
                _bounded(block)
                for block in _prose(
                    [part], section, f"pdf-p{index}", len(result), [index], [label]
                )
            )
        pending.clear()

    def end_run(run: list[str], pending: list[str], index: int, label: str) -> None:
        # Three or more caption-less data rows form a table; fewer stay prose.
        nonlocal table
        if len(run) >= 3:
            headers = pending[-2:]
            flush(pending, index, label)
            table = _Table(None, None, index, label)
            table.headers, table.rows = headers, list(run)
            emit_table(index, label)
        else:
            pending.extend(run)
        run.clear()

    for index, text in texts.items():
        label = labels[index - 1]
        if index != previous_page + 1:
            # A skipped page breaks every continuation; never cite past a denied page.
            table, previous = None, None
            first_pages.clear()
        previous_page = index
        if not text.strip():
            result.append(
                EvidenceBlock(
                    block_id=f"pdf-p{index}-unreadable",
                    kind="unreadable",
                    content="Page has no reliably extracted text; reviewed transcription required.",
                    pages=[index],
                    printed_pages=[label],
                    section=section,
                    verification_status="needs_review",
                )
            )
            table, previous = None, None
            continue
        lines = _page_lines(text)
        # Strip leading running headers, chapter lines and page numbers only.
        for _ in range(_HEADER_LINES):
            if not lines:
                break
            line = lines[0]
            if repeated[line] >= _REPEATED_PAGES:
                if line.upper().startswith("CHAPTER") and line != chapter:
                    chapter = section = line
            elif line != label and not _PAGE_NUMBER.match(line):
                break
            lines.pop(0)
        # A table left open on the previous page continues only if this page opens with rows.
        if table is not None and not (lines and _data_row(lines[0])):
            table = None
        pending: list[str] = []
        run: list[str] = []
        for position, line in enumerate(lines):
            caption = _CAPTION.match(line)
            if caption or (_HEADING.match(line) and len(line) <= 150):
                end_run(run, pending, index, label)
                emit_table(index, label)
                flush(pending, index, label)
                if caption:
                    number = caption.group(1)
                    if not (_CONTINUED.search(line) and number in first_pages):
                        first_pages[number] = (index, label)
                    table = _Table(line, number, *first_pages[number])
                else:
                    table, section = None, line
                    pending.append(line)
                previous = line
                continue
            if table is not None:
                if _data_row(line):
                    table.rows.append(line)
                elif _FOOTNOTE.match(line) or table.footnotes:
                    table.footnotes.append(line)
                elif not table.rows:
                    table.headers.append(line)
                else:
                    table.rows.append(line)  # row labels such as a species group
                previous = line
                continue
            if _data_row(line):
                run.append(line)
            else:
                end_run(run, pending, index, label)
                following = lines[position + 1] if position + 1 < len(lines) else None
                if _short_title(line, previous, following):
                    flush(pending, index, label)
                    section = line
                pending.append(line)
            previous = line
        end_run(run, pending, index, label)
        flush(pending, index, label)
        emit_table(index, label)
    return result


def html_blocks(content: str) -> list[EvidenceBlock]:
    soup = BeautifulSoup(content, "html.parser")
    for node in soup(["script", "style", "nav", "footer"]):
        node.decompose()
    result: list[EvidenceBlock] = []
    section: str | None = None
    headings: list[tuple[int, str]] = []
    for node in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "math", "pre"]
    ):
        if node.find_parent(["table", "math", "pre"]):
            continue
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.name and node.name.startswith("h"):
            level = int(node.name[1])
            headings = [(depth, title) for depth, title in headings if depth < level]
            headings.append((level, text))
            section = " / ".join(title for _, title in headings)
        if node.name == "table":
            headers = [cell.get_text(" ", strip=True) for cell in node.find_all("th")]
            context = node.find_parent(["section", "article"]) or node.parent
            conditions = (
                [
                    child.get_text(" ", strip=True)
                    for child in context.find_all("p", recursive=False)
                ]
                if isinstance(context, Tag)
                else []
            )
            footnotes = [
                item.get_text(" ", strip=True)
                for item in node.find_all(["caption", "tfoot"])
            ]
            ambiguous = not headers or any(
                cell.get("rowspan") or cell.get("colspan")
                for cell in node.find_all(["td", "th"])
            )
            for row in node.find_all("tr"):
                if not row.find("td"):
                    continue
                result.append(
                    EvidenceBlock(
                        block_id=f"html-{len(result)}",
                        kind="table",
                        content=row.get_text(" | ", strip=True),
                        headers=headers,
                        conditions=conditions,
                        footnotes=footnotes,
                        section=section or "HTML table",
                        verification_status="needs_review"
                        if ambiguous
                        else "unverified",
                    )
                )
        else:
            blocks = _prose(
                [text], section or "HTML document", "html", len(result), [], []
            )
            if node.name in ("math", "pre"):
                for block in blocks:
                    block.kind, block.verification_status = "equation", "needs_review"
            result.extend(blocks)
    return result
