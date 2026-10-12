"""Provenance-first extraction; ambiguous layouts require reviewed transcription.

No parser promotes an extracted table/equation to a verified numerical fact.
PDF layout is retained for review rather than treating spacing as a schema.
"""

import io
import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag
from pypdf import PdfReader

from app.engineering.schemas import EvidenceBlock
from app.ingestion.extract import chunk_text

_HEADING = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*\s+[A-ZÄÖÜ]|§\s*\d)")
_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_EQUATION = re.compile(r"(?:\$\$|\\\[|[A-Za-z][\w_]*\s*=\s*[^=]|[∑∫√])")


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


def pdf_blocks(
    content: bytes, *, allowed_pages: Iterable[int] | None = None
) -> list[EvidenceBlock]:
    reader = PdfReader(io.BytesIO(content))
    labels = reader.page_labels
    selected = set(allowed_pages) if allowed_pages is not None else None
    if selected is not None and any(page > len(reader.pages) for page in selected):
        raise ValueError("approved physical page is outside the PDF")
    result: list[EvidenceBlock] = []
    section: str | None = None
    prior_table: EvidenceBlock | None = None
    first_layout: tuple[int, str, str] | None = None
    for index, page in enumerate(reader.pages, 1):
        if selected is not None and index not in selected:
            prior_table = None
            first_layout = None
            continue
        text = page.extract_text(extraction_mode="layout") or ""
        label = labels[index - 1]
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
            prior_table = None
            first_layout = None
            continue
        # Multi-column layout cannot be interpreted reliably by pypdf. Preserve
        # the full page plus preceding table context for explicit human review.
        if any(re.search(r"\S(?: {2,}|\t)\S", line) for line in text.splitlines()):
            block = EvidenceBlock(
                block_id=f"pdf-p{index}-layout",
                kind="table",
                content=text,
                pages=[index],
                printed_pages=[label],
                section=section,
                verification_status="needs_review",
            )
            if prior_table is not None:
                # Keep the first page and immediate predecessor whole, without
                # recursively duplicating the entire book into every block.
                # Intermediate pages remain separate review-pending blocks.
                first_page, first_label, first_text = first_layout
                block.headers = list(dict.fromkeys([first_text, prior_table.content]))
                block.pages = sorted({first_page, index - 1, index})
                block.printed_pages = list(
                    dict.fromkeys([first_label, labels[index - 2], label])
                )
                block.conditions = [
                    "Ambiguous continuation: verify the complete table across its source pages before numerical use."
                ]
            else:
                first_layout = (index, label, text)
            result.append(block)
            prior_table = block
        else:
            pending: list[str] = []
            for line in text.splitlines():
                if _HEADING.match(line.strip()) and len(line.strip()) <= 150:
                    result.extend(
                        _prose(
                            pending,
                            section,
                            f"pdf-p{index}",
                            len(result),
                            [index],
                            [label],
                        )
                    )
                    pending = []
                    section = line.strip()
                pending.append(line)
            result.extend(
                _prose(pending, section, f"pdf-p{index}", len(result), [index], [label])
            )
            prior_table = None
            first_layout = None
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
