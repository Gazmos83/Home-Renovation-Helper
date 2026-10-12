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


def test_cross_page_pdf_layout_retains_context_and_requires_review(monkeypatch):
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self, **kwargs):
            return self.text

    monkeypatch.setattr(
        blocks,
        "PdfReader",
        lambda *args: SimpleNamespace(
            pages=[
                Page("Grade  E (MPa)\nDry service only"),
                Page("TEST  2000\nMean values"),
            ],
            page_labels=["10", "11"],
        ),
    )
    result = pdf_blocks(b"unused")
    assert result[1].pages == [1, 2]
    assert all(
        value in block_text(result[1]) for value in ["MPa", "Dry", "2000", "Mean"]
    )
    assert result[1].verification_status == "needs_review"


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
