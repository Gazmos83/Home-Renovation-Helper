import io
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import embedding
from app.db.models import EngineeringChunk
from app.engineering import blocks
from app.engineering.blocks import block_text, html_blocks, markdown_blocks, pdf_blocks
from app.engineering.fetch import KnowledgeFetcher
from app.engineering.ingest import ingest_version, stage_file
from app.engineering.registry import (
    EvidenceRefused,
    add_property,
    decide_rights,
    register_source,
    review_property,
)
from app.engineering.schemas import (
    Collection,
    EvidenceBlock,
    PropertyIn,
    ReviewIn,
    RightsIn,
    Scope,
    SourceIn,
)
from tests.test_guideline_ingestion import make_pdf


@pytest.fixture
def registered(db_session):
    return register_source(
        db_session,
        SourceIn(
            key=f"test-{uuid4().hex}",
            metadata={
                "title": "Owner-authored material fixture",
                "material_grade": "TEST GRADE",
                "thickness_mm": 18,
            },
            collections=[Collection.MATERIALS],
        ),
    )


def allow(session, version, grants=None):
    return decide_rights(
        session,
        version.id,
        RightsIn(
            action="approve",
            reviewer="fixture author",
            evidence="Owner-authored synthetic fixture grants these operations for testing",
            grants=grants
            if grants is not None
            else {scope: {} for scope in Scope if scope != Scope.COMMERCIAL},
        ),
    )


def setup_file(root, content="## Board\nOwner-authored fixture for tests only.\n"):
    root.mkdir(exist_ok=True)
    target = root / "fixture.md"
    target.write_text(content)
    return "fixture.md"


def test_no_extraction_or_embedding_without_permission(
    db_session, registered, tmp_path, monkeypatch
):
    settings = SimpleNamespace(guideline_root=tmp_path)
    monkeypatch.setattr(
        blocks, "PdfReader", lambda *args: pytest.fail("parser must not run")
    )
    monkeypatch.setattr(
        embedding, "_load_model", lambda: pytest.fail("embedder must not load")
    )
    run = ingest_version(db_session, settings, registered.id)
    assert run.state == "failed" and "extraction" in run.reason
    assert registered.state == "pending"
    assert (
        db_session.scalar(
            select(EngineeringChunk).where(EngineeringChunk.version_id == registered.id)
        )
        is None
    )
    with pytest.raises(EvidenceRefused, match="retention"):
        stage_file(db_session, registered.id, tmp_path, "fixture.md")


def test_atomic_refresh_reuses_vectors_and_keeps_prior_on_failure(
    db_session, registered, tmp_path, fake_embedder, monkeypatch
):
    allow(db_session, registered)
    path = setup_file(tmp_path)
    settings = SimpleNamespace(guideline_root=tmp_path)
    stage_file(db_session, registered.id, tmp_path, path)
    first = ingest_version(db_session, settings, registered.id)
    assert first.state == "published" and first.blocks > 0
    second = ingest_version(db_session, settings, registered.id)
    assert second.reused_vectors == second.blocks == first.blocks
    prior = [
        (row.block_id, row.content_hash)
        for row in db_session.scalars(
            select(EngineeringChunk).where(EngineeringChunk.version_id == registered.id)
        )
    ]
    monkeypatch.setattr(
        "app.engineering.ingest.markdown_blocks",
        lambda *args: (_ for _ in ()).throw(ValueError("damaged extraction")),
    )
    failed = ingest_version(db_session, settings, registered.id)
    assert failed.state == "failed" and registered.state == "published"
    assert [
        (row.block_id, row.content_hash)
        for row in db_session.scalars(
            select(EngineeringChunk).where(EngineeringChunk.version_id == registered.id)
        )
    ] == prior


def test_wrong_file_identity_or_escaped_path_is_refused(
    db_session, registered, tmp_path
):
    allow(db_session, registered)
    path = setup_file(tmp_path)
    stage_file(db_session, registered.id, tmp_path, path)
    (tmp_path / path).write_text("A different edition")
    with pytest.raises(EvidenceRefused, match="new source version"):
        stage_file(db_session, registered.id, tmp_path, path)
    with pytest.raises(EvidenceRefused, match="leaves"):
        stage_file(db_session, registered.id, tmp_path, "../outside.md")


def test_manual_blocks_keep_units_conditions_and_candidate_review_separate(
    db_session, registered, tmp_path, fake_embedder
):
    allow(db_session, registered)
    block = EvidenceBlock(
        block_id="reviewed-row",
        kind="table",
        content="TEST GRADE, 18 mm, E = 2–3 GPa",
        pages=[2],
        headers=["Grade | thickness (mm) | E (GPa)"],
        footnotes=["Mean test values, dry condition"],
        conditions=["Test fixture only; not a real board"],
        verification_status="verified",
        reviewed_by="fixture author",
    )
    run = ingest_version(
        db_session,
        SimpleNamespace(guideline_root=tmp_path),
        registered.id,
        reviewed_blocks=[block],
    )
    assert run.state == "published"
    data = PropertyIn(
        block_id=block.block_id,
        kind="E_MPa",
        original_unit="GPa",
        original_minimum=2,
        original_maximum=3,
        value_basis="mean",
        material_grade="TEST GRADE",
        thickness_mm=18,
        page_section="p. 2",
        conditions={"moisture": "dry"},
    )
    prop = add_property(db_session, registered.id, data)
    assert prop.verification_status == "unverified"
    assert (prop.record["minimum"], prop.record["maximum"]) == (2000, 3000)
    review_property(
        db_session, prop.id, ReviewIn(reviewer="fixture author", status="verified")
    )
    assert (
        prop.verification_status == "verified" and prop.record["value_basis"] == "mean"
    )
    with pytest.raises(EvidenceRefused, match="material_grade"):
        add_property(
            db_session,
            registered.id,
            data.model_copy(update={"material_grade": "ANOTHER GRADE"}),
        )


def test_markdown_and_html_table_context_is_indivisible():
    markdown = "# Board\n## Properties\nFor dry service, tested thickness 18 mm.\n| Grade | E (MPa) |\n| --- | --- |\n| TEST | 2000 |\nFootnote: mean laboratory values, not allowable resistance.\n"
    row = next(block for block in markdown_blocks(markdown) if block.kind == "table")
    assert row.section == "Board / Properties"
    assert all(
        value in block_text(row) for value in ["18 mm", "MPa", "2000", "not allowable"]
    )
    html = "<article><h1>Board</h1><p>For dry service, 18 mm.</p><table><caption>Mean values</caption><tr><th>Grade</th><th>E (MPa)</th></tr><tr><td>TEST</td><td>2000</td></tr></table><p>Not allowable resistance.</p></article>"
    row = next(block for block in html_blocks(html) if block.kind == "table")
    assert all(
        value in block_text(row)
        for value in ["18 mm", "MPa", "2000", "Mean", "Not allowable"]
    )


def test_pdf_pages_sections_and_damaged_equations():
    output = pdf_blocks(
        make_pdf(
            [
                "1 Scope",
                "Fixture introduction",
                "2 Properties",
                "Elasticity depends on grade",
                "E = damaged / equation",
            ]
        )
    )
    assert {block.section for block in output} == {"1 Scope", "2 Properties"}
    assert all(block.pages == [1] and block.printed_pages == ["1"] for block in output)
    assert any(
        block.kind == "equation" and block.verification_status == "needs_review"
        for block in output
    )


def test_aes_encrypted_pdf_without_open_password_is_read():
    # Publisher PDFs often use AES with an empty open password; pypdf needs `cryptography`.
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(
        clone_from=PdfReader(io.BytesIO(make_pdf(["1 Scope", "Fixture text"])))
    )
    writer.encrypt(user_password="", owner_password="owner", algorithm="AES-256")
    encrypted = io.BytesIO()
    writer.write(encrypted)

    output = pdf_blocks(encrypted.getvalue())

    assert any("Fixture text" in block_text(block) for block in output)


def test_partial_pdf_permission_never_extracts_other_pages(monkeypatch):
    calls = []

    class Page:
        def __init__(self, number):
            self.number = number

        def extract_text(self, **kwargs):
            calls.append(self.number)
            return "Owner-authored page text"

    monkeypatch.setattr(
        blocks,
        "PdfReader",
        lambda *args: SimpleNamespace(
            pages=[Page(1), Page(2), Page(3)], page_labels=["i", "1", "2"]
        ),
    )
    result = pdf_blocks(b"unused", allowed_pages=[2])
    assert calls == [2] and result[0].pages == [2] and result[0].printed_pages == ["1"]


def fake_pdf(monkeypatch, texts, labels=None):
    """Patch the reader so each string is one page's extracted text."""

    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self, **kwargs):
            return self.text

    monkeypatch.setattr(
        blocks,
        "PdfReader",
        lambda *args: SimpleNamespace(
            pages=[Page(text) for text in texts],
            page_labels=labels or [str(number) for number in range(1, len(texts) + 1)],
        ),
    )


def two_column_pdf(left: list[str], right: list[str]) -> bytes:
    """One page that draws its whole left column, then its right column, side by side."""

    def column(x, lines):
        return (
            f"BT /F1 10 Tf 12 TL {x} 700 Td "
            + " T* ".join(f"({line}) Tj" for line in lines)
            + " ET"
        )

    stream = column(50, left) + " " + column(320, right)
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_two_column_page_keeps_each_column_contiguous():
    output = pdf_blocks(
        two_column_pdf(
            [
                "Wood deforms elastically when it is",
                "first loaded and recovers when the",
                "load is removed.",
            ],
            [
                "Creep and Relaxation",
                "If the load is maintained, additional",
                "deformation occurs over time.",
            ],
        )
    )
    assert [block.kind for block in output] == ["paragraph", "paragraph"]
    assert (
        "when it is\nfirst loaded and recovers when the\nload is removed."
        in output[0].content
    )
    assert output[1].section == "Creep and Relaxation"
    assert "additional\ndeformation occurs" in output[1].content
    assert all(block.pages == [1] for block in output)


def test_long_pdf_page_splits_into_passages(monkeypatch):
    sentence = "Moisture content changes the stiffness of every board in service."
    fake_pdf(monkeypatch, ["\n".join([sentence] * 60)])
    output = pdf_blocks(b"unused")
    assert len(output) > 1
    assert all(block.kind == "paragraph" for block in output)
    assert all(len(block.content) <= 1200 for block in output)


def test_running_headers_and_page_labels_are_not_passages(monkeypatch):
    pages = [
        f"General Technical Report FPL\nCHAPTER 5 | Mechanical Properties\n5–{number}\n"
        f"Page {number} explains how wood behaves under load."
        for number in range(1, 7)
    ]
    fake_pdf(monkeypatch, pages)
    output = pdf_blocks(b"unused")
    assert len(output) == 6
    assert all("General Technical Report" not in block_text(block) for block in output)
    assert all(not block.content.startswith("5–") for block in output)
    assert {block.section for block in output} == {"CHAPTER 5 | Mechanical Properties"}


def test_captioned_table_rows_carry_caption_headers_and_footnotes(monkeypatch):
    fake_pdf(
        monkeypatch,
        [
            (
                "Strength values follow.\n"
                "Table 5–3a. Strength properties (metric)a\n"
                "Modulus of\n"
                "elasticity (MPa)\n"
                "Alder, red Green 0.37 45,000 8,100 55\n"
                "12% 0.41 68,000 9,500 58\n"
                "aResults of tests on clear specimens."
            ),
            "Prose about drying explains why boards shrink.\nIt has no table at all.",
        ],
    )
    output = pdf_blocks(b"unused")
    table = next(block for block in output if block.kind == "table")
    assert table.headers[0].startswith("Table 5–3a.")
    assert "elasticity (MPa)" in table.headers
    assert "Alder, red Green 0.37 45,000" in table.content
    assert table.footnotes == ["aResults of tests on clear specimens."]
    assert table.verification_status == "needs_review"
    assert not [
        block for block in output if block.pages == [2] and block.kind == "table"
    ]


def test_caption_less_numeric_rows_form_a_review_pending_table(monkeypatch):
    fake_pdf(
        monkeypatch,
        [
            (
                "Shelf spans measured in the lab.\nSpan mm Load N Sag mm\n"
                "600 400 2.1 1\n800 400 4.8 1\n1000 400 9.6 1"
            )
        ],
    )
    table = next(block for block in pdf_blocks(b"unused") if block.kind == "table")
    assert table.headers == [
        "Shelf spans measured in the lab.",
        "Span mm Load N Sag mm",
    ]
    assert (
        "1000 400 9.6" in table.content and table.verification_status == "needs_review"
    )


@pytest.mark.parametrize(
    "second_page",
    [
        "C30 12,000 18 3\naMean values at 12% moisture.",
        (
            "Table 2. Board stiffness (dry service only)—con.\nGrade E (MPa) Thickness (mm)\n"
            "C30 12,000 18 3\naMean values at 12% moisture."
        ),
    ],
    ids=["opens-with-rows", "continuation-caption"],
)
def test_cross_page_table_retains_context_and_requires_review(monkeypatch, second_page):
    fake_pdf(
        monkeypatch,
        [
            (
                "Table 2. Board stiffness (dry service only)\nGrade E (MPa) Thickness (mm)\n"
                "C24 11,000 18 2"
            ),
            second_page,
        ],
        labels=["10", "11"],
    )
    result = pdf_blocks(b"unused")
    continued = next(block for block in result if "C30" in block.content)
    assert continued.kind == "table" and continued.verification_status == "needs_review"
    assert continued.pages == [1, 2] and continued.printed_pages == ["10", "11"]
    assert all(
        value in block_text(continued)
        for value in ["MPa", "dry service", "Thickness (mm)", "12,000", "Mean"]
    )
    assert "C24" not in block_text(continued)


def test_embedded_block_text_is_bounded(monkeypatch):
    header_lines = "\n".join(
        f"Header line {number} " + "x" * 80 for number in range(60)
    )
    fake_pdf(
        monkeypatch,
        [f"Table 1. Wide table\n{header_lines}\nA 1 2 3\nB 4 5 6"],
    )
    table = next(block for block in pdf_blocks(b"unused") if block.kind == "table")
    assert len(block_text(table)) <= blocks.MAX_BLOCK_TEXT
    assert table.headers[0] == "Table 1. Wide table" and "A 1 2 3" in table.content
    oversized = EvidenceBlock(block_id="x", kind="table", content="y" * 5000)
    with pytest.raises(ValueError, match="exceeds"):
        blocks._bounded(oversized)


def test_safe_fetch_refusals_and_address_pinning(settings):
    settings.ingestion_min_interval_seconds = 0
    seen = []

    def public(host, port, **kwargs):
        return [(2, 1, 6, "", ("8.8.8.8", port))]

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})

    fetcher = KnowledgeFetcher(
        settings, resolver=public, transport=httpx.MockTransport(handler)
    )
    with fetcher, pytest.raises(ValueError, match="no redirect"):
        fetcher.fetch_page("https://manual.test/file.pdf")
    assert (
        len(seen) == 1
        and seen[0].url.host == "8.8.8.8"
        and seen[0].headers["host"] == "manual.test"
    )
    assert "HomeRenovationAgentsBot" in seen[0].headers["user-agent"]
    fetcher = KnowledgeFetcher(
        settings,
        resolver=lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
        transport=httpx.MockTransport(handler),
    )
    with fetcher, pytest.raises(Exception, match="non-public"):
        fetcher.fetch_page("https://private.test/manual")
    assert len(seen) == 1


def test_compressed_rules_and_pages_are_read_once_decoded(settings):
    # research.fs.usda.gov serves robots.txt gzip-encoded; the decoded body must not be decoded again.
    import gzip

    settings.ingestion_min_interval_seconds = 0
    robots = b"User-agent: *\nDisallow: /private/\n"
    page = b"%PDF-1.7 compressed body"

    def handler(request):
        body = robots if request.url.path == "/robots.txt" else page
        content_type = (
            "text/plain" if request.url.path == "/robots.txt" else "application/pdf"
        )
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip", "content-type": content_type},
            content=gzip.compress(body),
        )

    fetcher = KnowledgeFetcher(
        settings,
        resolver=lambda host, port, **kwargs: [(2, 1, 6, "", ("8.8.8.8", port))],
        transport=httpx.MockTransport(handler),
    )
    with fetcher:
        rules = fetcher.fetch_rules("https://manual.test", source="manual.test")
        fetched = fetcher.fetch_page("https://manual.test/file.pdf")
    assert rules.allows("https://manual.test/file.pdf")
    assert not rules.allows("https://manual.test/private/x")
    assert fetched.content == page and "content-encoding" not in fetched.headers


def test_revocation_committed_during_embedding_prevents_publication(
    db_session, registered, tmp_path, fake_embedder
):
    allow(db_session, registered)
    path = setup_file(tmp_path)
    stage_file(db_session, registered.id, tmp_path, path)
    db_session.commit()
    version_id = registered.id

    def revoke_then_embed(texts):
        with Session(db_session.bind) as other:
            decide_rights(
                other,
                version_id,
                RightsIn(
                    action="revoke",
                    reviewer="fixture author",
                    evidence="Withdrawn while embedding",
                ),
            )
            other.commit()
        return fake_embedder(texts)

    embedding.set_embedder(revoke_then_embed)
    try:
        result = ingest_version(
            db_session, SimpleNamespace(guideline_root=tmp_path), version_id
        )
        assert result.state == "failed" and "current documented rights" in result.reason
        assert (
            db_session.scalar(
                select(EngineeringChunk).where(
                    EngineeringChunk.version_id == version_id
                )
            )
            is None
        )
    finally:
        embedding.set_embedder(fake_embedder)
        db_session.rollback()
        # These tables contain only synthetic test data in the designated test DB.
        db_session.execute(text("TRUNCATE knowledge_sources CASCADE"))
        db_session.commit()


def test_large_cli_path_and_partial_embedding_keep_only_authorised_blocks(
    db_session, registered, tmp_path, fake_embedder
):
    allow(
        db_session,
        registered,
        {Scope.EXTRACT: {}, Scope.RETAIN: {}, Scope.EMBED: {"blocks": ["permitted"]}},
    )
    path = setup_file(
        tmp_path, "Owner-authored fixture exceeds this tiny test upload cap."
    )
    with pytest.raises(EvidenceRefused, match="upload limit"):
        stage_file(db_session, registered.id, tmp_path, path, max_bytes=16)
    stage_file(db_session, registered.id, tmp_path, path)
    manual = [
        EvidenceBlock(
            block_id=name,
            kind="paragraph",
            content=f"Original synthetic {name} text",
            pages=[1],
            reviewed_by="fixture author",
            verification_status="verified",
        )
        for name in ["permitted", "not-permitted"]
    ]
    run = ingest_version(
        db_session,
        SimpleNamespace(guideline_root=tmp_path),
        registered.id,
        reviewed_blocks=manual,
    )
    assert run.state == "published" and run.blocks == 1
    assert db_session.scalars(
        select(EngineeringChunk.block_id).where(
            EngineeringChunk.version_id == registered.id
        )
    ).all() == ["permitted"]
