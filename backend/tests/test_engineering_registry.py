from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import DBAPIError

from app.db.models import (
    EMBEDDING_DIMENSIONS,
    Chunk,
    EngineeringChunk,
    KnowledgeRightsDecision,
    KnowledgeSourceVersion,
)
from app.engineering.registry import (
    current_rights,
    decide_rights,
    permits,
    register_source,
)
from app.engineering.schemas import Collection, PropertyIn, RightsIn, Scope, SourceIn


@pytest.fixture
def source_version(db_session):
    # Transaction-scoped source; rolls back with the shared db_session fixture.
    from uuid import uuid4

    return register_source(
        db_session,
        SourceIn(
            key=f"test-{uuid4().hex}",
            metadata={"title": "Owner-authored fixture"},
            collections=[Collection.MATERIALS],
        ),
    )


def decision(**kwargs):
    return RightsIn(
        action="approve",
        evidence="Owner-authored test fixture; permission for the stated test operations",
        reviewer="fixture author",
        grants={Scope.EXTRACT: {}, Scope.RETAIN: {}},
        **kwargs,
    )


def test_metadata_is_explicitly_unknown_and_registration_is_content_free(
    db_session, source_version
):
    assert source_version.attributes["material_grade"] is None
    assert source_version.attributes["edition"] is None
    assert source_version.attributes["thickness_mm"] is None
    assert source_version.content_hash is None
    assert source_version.collections == ["material_datasheets"]
    assert (
        db_session.scalar(
            select(EngineeringChunk).where(
                EngineeringChunk.version_id == source_version.id
            )
        )
        is None
    )
    assert current_rights(db_session, source_version.id) is None


def test_scope_expiry_and_revocation_do_not_fall_back(db_session, source_version):
    first = decide_rights(db_session, source_version.id, decision())
    assert permits(first, Scope.EXTRACT)
    assert not permits(first, Scope.EMBED)
    assert not permits(first, Scope.REMOTE)
    decide_rights(
        db_session,
        source_version.id,
        decision(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
    )
    assert current_rights(db_session, source_version.id) is None
    decide_rights(db_session, source_version.id, decision())
    decide_rights(
        db_session,
        source_version.id,
        RightsIn(
            action="revoke", reviewer="fixture author", evidence="Permission withdrawn"
        ),
    )
    assert current_rights(db_session, source_version.id) is None


def test_block_and_page_scopes_require_complete_coverage(db_session, source_version):
    right = decide_rights(
        db_session,
        source_version.id,
        RightsIn(
            action="approve",
            reviewer="fixture author",
            evidence="Only this row and physical pages",
            grants={Scope.RETRIEVE: {"pages": [1, 2], "blocks": ["table-1"]}},
        ),
    )
    assert permits(right, Scope.RETRIEVE, block_id="table-1", pages=[1, 2])
    assert not permits(right, Scope.RETRIEVE, block_id="table-1", pages=[2, 3])
    assert not permits(right, Scope.RETRIEVE, block_id="table-2", pages=[1])
    assert not permits(right, Scope.RETRIEVE, block_id="table-1", pages=[])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"evidence": " "},
        {"reviewer": " "},
        {"grants": {}},
        {"grants": {"made_up": {}}},
        {"grants": {Scope.EXTRACT: {"blocks": ["unknown-before-extraction"]}}},
    ],
)
def test_incomplete_rights_are_refused(kwargs):
    fields = {
        "action": "approve",
        "reviewer": "fixture author",
        "evidence": "Owner-authored permission",
        "grants": {Scope.EXTRACT: {}},
    }
    fields.update(kwargs)
    with pytest.raises(ValidationError):
        RightsIn.model_validate(fields)


def test_rights_are_append_only_in_database(db_session, source_version):
    row = decide_rights(db_session, source_version.id, decision())
    with pytest.raises(DBAPIError, match="append-only"), db_session.begin_nested():
        db_session.execute(
            update(KnowledgeRightsDecision)
            .where(KnowledgeRightsDecision.id == row.id)
            .values(reviewer="rewritten")
        )
    assert (
        db_session.get(KnowledgeRightsDecision, row.sequence).reviewer
        == "fixture author"
    )


def test_source_version_identity_is_immutable(db_session, source_version):
    with pytest.raises(DBAPIError, match="immutable"), db_session.begin_nested():
        db_session.execute(
            update(KnowledgeSourceVersion)
            .where(KnowledgeSourceVersion.id == source_version.id)
            .values(edition="invented edition")
        )


def test_migration_is_separate_from_legacy_chunks(db_session):
    tables = inspect(db_session.bind).get_table_names()
    assert {
        "chunks",
        "knowledge_sources",
        "knowledge_source_versions",
        "knowledge_rights_decisions",
        "engineering_chunks",
        "engineering_properties",
        "knowledge_ingestion_runs",
    }.issubset(tables)
    assert (
        EngineeringChunk.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS == 1024
    )
    # Legacy URL uniqueness and search configuration remain intact.
    assert Chunk.__table__.c.embedding.type.dim == 1024
    assert "german" in str(Chunk.__table__.c.search_vector.computed.sqltext)
    assert (
        db_session.scalar(text("SELECT version_num FROM alembic_version"))
        == "0031_blueprints"
    )


def test_property_conversion_preserves_ranges_and_unknown():
    value = PropertyIn(
        block_id="table-1",
        kind="E_MPa",
        original_unit="GPa",
        original_minimum=2,
        original_maximum=3,
        page_section="p. 2",
        value_basis="mean",
    )
    assert (value.minimum, value.maximum, value.value) == (2000, 3000, None)
    assert (value.original_minimum, value.original_maximum) == (2, 3)
    unknown = PropertyIn(
        block_id="table-1", kind="E_MPa", original_unit="MPa", page_section="p. 2"
    )
    assert unknown.value is None
    with pytest.raises(ValidationError):
        PropertyIn(
            block_id="table-1",
            kind="E_MPa",
            original_unit="kg",
            original_value=20,
            page_section="p. 2",
        )
