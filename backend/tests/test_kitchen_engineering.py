"""Kitchen cabinet/drawer extension: namespaces, seeds, routing and NOT VERIFIED gates."""

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.db.models import EngineeringChunk, KnowledgeSourceVersion
from app.engineering.__main__ import seed_catalogue
from app.engineering.assessments import AssessmentIn
from app.engineering.chat import (
    SHORT_STATUS,
    engineering_intent,
    missing_inputs,
    render_answer,
)
from app.engineering.ingest import ingest_version
from app.engineering.kitchen import (
    KitchenIntent,
    all_kitchen_namespaces,
    dual_tag_targets,
    kitchen_intents,
    recommended_collections,
    refuses_cross_manufacturer,
    refuses_din_compliance_claim,
)
from app.engineering.methods import unavailable
from app.engineering.registry import decide_rights, register_source
from app.engineering.schemas import (
    KITCHEN_COLLECTIONS,
    Collection,
    EvidenceBlock,
    RightsIn,
    Scope,
    SourceIn,
    SourceMetadata,
    with_dual_tags,
)
from tests.test_engineering_retrieval import publish


def test_legacy_metadata_accepts_null_kitchen_fields_and_rejects_bad_urls():
    meta = SourceMetadata(title="Legacy shelf note")
    assert meta.approved_for_embedding is False
    assert meta.manufacturer is None
    assert meta.nominal_load_kg is None
    assert meta.runner_length_mm is None
    with pytest.raises(ValidationError):
        SourceMetadata(title="Bad", source_url="http://example.com/insecure")


def test_kitchen_collections_are_additive_and_dual_tagged():
    existing = {
        Collection.FUNDAMENTALS,
        Collection.MATERIALS,
        Collection.HARDWARE,
        Collection.STANDARDS,
        Collection.LAW,
        Collection.SAFETY,
        Collection.MURPHY_BED,
    }
    assert all_kitchen_namespaces() == KITCHEN_COLLECTIONS
    assert len(KITCHEN_COLLECTIONS) == 10
    assert existing.isdisjoint(KITCHEN_COLLECTIONS)
    expanded = with_dual_tags([Collection.KITCHEN_DRAWER, Collection.KITCHEN_PANEL])
    assert Collection.KITCHEN_DRAWER in expanded
    assert Collection.HARDWARE in expanded
    assert Collection.MATERIALS in expanded
    assert dual_tag_targets(Collection.KITCHEN_ANCHOR) == (
        Collection.HARDWARE,
        Collection.SAFETY,
    )


def test_register_source_expands_dual_tags_and_refuses_self_approved_embedding(
    db_session,
):
    with pytest.raises(Exception) as refused:
        register_source(
            db_session,
            SourceIn(
                key=f"kitchen-self-{uuid4().hex}",
                collections=[Collection.KITCHEN_DRAWER],
                metadata={
                    "title": "Self-approved runner",
                    "approved_for_embedding": True,
                },
            ),
        )
    assert "approved_for_embedding" in str(refused.value)
    version = register_source(
        db_session,
        SourceIn(
            key=f"kitchen-drawer-{uuid4().hex}",
            collections=[Collection.KITCHEN_DRAWER],
            metadata={
                "title": "Blum index fixture",
                "manufacturer": "Blum",
                "source_kind": "manufacturer_datasheet",
                "approved_for_embedding": False,
            },
        ),
    )
    assert "kitchen_drawer_systems" in version.collections
    assert "hardware_manuals" in version.collections
    assert version.attributes["approved_for_embedding"] is False
    assert (
        db_session.scalar(
            select(EngineeringChunk).where(EngineeringChunk.version_id == version.id)
        )
        is None
    )


def test_seed_links_registers_kitchen_sources_without_chunks(db_session):
    catalogue = Path(__file__).resolve().parents[2] / "config" / "engineering_sources.yaml"
    created = seed_catalogue(db_session, catalogue)
    assert created >= 10
    versions = list(db_session.scalars(select(KnowledgeSourceVersion)))
    kitchen_hits = [
        version
        for version in versions
        if any(item.startswith("kitchen_") for item in version.collections)
    ]
    assert kitchen_hits
    assert all(version.attributes.get("approved_for_embedding") is False for version in versions)
    assert (
        db_session.scalar(select(EngineeringChunk).limit(1)) is None
    ), "seed-links must not create embeddings"


def test_copyrighted_standard_stays_metadata_only_without_embed_rights(
    db_session, tmp_path, settings
):
    version = register_source(
        db_session,
        SourceIn(
            key=f"din-kitchen-{uuid4().hex}",
            collections=[Collection.KITCHEN_VALIDATION, Collection.STANDARDS],
            metadata={
                "title": "DIN EN 14749 fixture",
                "standard_or_model": "DIN EN 14749",
                "source_kind": "licensed_standard",
                "license_status": "licensed-standard-permission-required",
                "approved_for_embedding": False,
            },
        ),
    )
    decide_rights(
        db_session,
        version.id,
        RightsIn(
            action="approve",
            reviewer="fixture author",
            evidence="Extract/retain only; no embedding of licensed text",
            grants={Scope.EXTRACT: {}, Scope.RETAIN: {}},
        ),
    )
    assert version.attributes["approved_for_embedding"] is False
    block = EvidenceBlock(
        block_id="clause-1",
        kind="paragraph",
        content="Copyrighted DIN clause text must not embed",
        pages=[1],
        section="4",
        verification_status="verified",
        reviewed_by="fixture author",
    )
    run = ingest_version(
        db_session,
        settings,
        version.id,
        reviewed_blocks=[block],
    )
    assert run.state == "failed"
    assert "embedding" in (run.reason or "").casefold() or "approved_for" in (
        run.reason or ""
    ).casefold()
    assert (
        db_session.scalar(
            select(EngineeringChunk).where(EngineeringChunk.version_id == version.id)
        )
        is None
    )


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "How many anchors for a 1200 mm wall cabinet on plasterboard?",
            KitchenIntent.HANGER_ANCHOR,
        ),
        ("Can a 40 kg rated runner hold a kitchen drawer?", KitchenIntent.DRAWER),
        ("Blum hinge for a tall door", KitchenIntent.HINGE),
        ("sink unit moisture sealing", KitchenIntent.SINK_UNIT),
        ("integrated oven ventilation gap", KitchenIntent.APPLIANCE),
        ("working height accessibility DIN 18040", KitchenIntent.ERGONOMICS),
        ("quartz worktop overhang", KitchenIntent.WORKTOP),
        ("base cabinet carcass joints", KitchenIntent.BASE_WALL_CABINET),
    ],
)
def test_kitchen_intent_routing(query, expected):
    assert expected in kitchen_intents(query)
    assert engineering_intent(query)
    collections = recommended_collections(query)
    assert collections
    assert any(item in KITCHEN_COLLECTIONS for item in collections)
    if expected == KitchenIntent.DRAWER:
        assert Collection.HARDWARE in collections
    if expected == KitchenIntent.SINK_UNIT:
        assert Collection.KITCHEN_MOISTURE in collections


@pytest.mark.parametrize(
    ("query", "needle"),
    [
        (
            "Can I use 18 mm P2 for a 900 mm kitchen shelf?",
            "18 mm is adequate",
        ),
        (
            "Can a 40 kg rated runner hold a 40 kg kitchen drawer?",
            "exact runner series",
        ),
        (
            "How many anchors for a 1200 mm wall cabinet on plasterboard?",
            "wall substrate",
        ),
        (
            "Use Blum data for a Hettich runner",
            "cross-manufacturer",
        ),
        (
            "Is DIN EN 14749 compliance confirmed?",
            "do not confirm compliance",
        ),
        (
            "What gap does my integrated oven need?",
            "exact appliance",
        ),
    ],
)
def test_kitchen_acceptance_queries_are_not_verified(db_session, query, needle):
    assert refuses_cross_manufacturer("Use Blum data for a Hettich runner")
    assert refuses_din_compliance_claim("Is DIN EN 14749 compliance confirmed?")
    missing = "; ".join(missing_inputs(query))
    assert needle.casefold() in missing.casefold()
    rendered = render_answer("{}", db_session, [], query, enabled=True)
    assert rendered == SHORT_STATUS


def test_prior_murphy_and_material_filters_still_work(db_session, tmp_path, fake_embedder):
    version = publish(db_session, tmp_path)
    assert "material_datasheets" in version.collections
    murphy_missing = "; ".join(missing_inputs("Is this Murphy bed safe to build?"))
    assert "matching mechanism manual" in murphy_missing
    shelf_missing = "; ".join(missing_inputs("Can this shelf hold 30 kg?"))
    assert "exact material product/grade" in shelf_missing
    assert Collection.MURPHY_BED.value == "murphy_bed_safety"
    assert Collection.MATERIALS.value == "material_datasheets"


def test_kitchen_assessment_kinds_reuse_unavailable_methods():
    for furniture in (
        "kitchen_base_cabinet",
        "kitchen_wall_cabinet",
        "kitchen_tall_cabinet",
        "kitchen_drawer",
        "kitchen_worktop",
    ):
        AssessmentIn(version=1, furniture=furniture)
    check = unavailable(
        "hardware",
        missing=["exact runner series/variant"],
    )
    assert check.status == "NOT_VERIFIED"
    assert check.result is None
