import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import EngineeringChunk
from app.engineering.ingest import ingest_version
from app.engineering.registry import add_property, decide_rights, register_source
from app.engineering.retrieval import resolve_evidence, search_engineering
from app.engineering.schemas import (
    Collection,
    EvidenceBlock,
    PropertyIn,
    RightsIn,
    Scope,
    SearchIn,
    SourceIn,
)


def publish(
    session,
    root,
    *,
    title="TEST Board",
    model="TEST P2",
    remote=True,
    denied=False,
    edition="1",
    text="TEST board elasticity E 2000 MPa dry service at 18 mm",
):
    version = register_source(
        session,
        SourceIn(
            key=f"fixture-{uuid4().hex}",
            collections=[Collection.MATERIALS],
            metadata={
                "title": title,
                "standard_or_model": model,
                "edition": edition,
                "jurisdiction": "DE",
                "applicable_furniture": ["shelf"],
                "material_grade": "P2",
                "thickness_mm": 18,
            },
        ),
    )
    grants = {scope: {} for scope in Scope if scope != Scope.COMMERCIAL}
    if not remote:
        del grants[Scope.REMOTE]
    decide_rights(
        session,
        version.id,
        RightsIn(
            action="approve",
            reviewer="fixture author",
            evidence="Original synthetic test text permits stated operations",
            grants=grants,
        ),
    )
    block = EvidenceBlock(
        block_id="row-1",
        kind="table",
        content=text,
        pages=[1],
        section="Properties",
        headers=["Grade P2 | E (MPa) | thickness 18 mm"],
        conditions=["Dry service; synthetic example only"],
        verification_status="verified",
        reviewed_by="fixture author",
    )
    run = ingest_version(
        session,
        SimpleNamespace(guideline_root=root),
        version.id,
        reviewed_blocks=[block],
    )
    assert run.state == "published", run.reason
    if denied:
        decide_rights(
            session,
            version.id,
            RightsIn(
                action="revoke",
                reviewer="fixture author",
                evidence="Withdrawn before retrieval",
            ),
        )
    return version


@pytest.mark.parametrize("mode", ["hybrid", "vector", "keyword"])
def test_rights_and_exact_filters_precede_limit(
    db_session, tmp_path, fake_embedder, mode
):
    wrong = publish(
        db_session,
        tmp_path,
        model="TEST P3",
        text="TEST board elasticity E 2000 MPa dry service",
    )
    denied = publish(
        db_session,
        tmp_path,
        denied=True,
        text="TEST board elasticity E 2000 MPa dry service",
    )
    eligible = publish(
        db_session, tmp_path, text="TEST board elasticity E 2100 MPa dry service"
    )
    data = SearchIn(
        query="TEST board elasticity",
        mode=mode,
        limit=1,
        min_relevance=0,  # Fake vectors test eligibility, not real-model calibration.
        filters={
            "standard_or_model": "TEST P2",
            "material_grade": "P2",
            "thickness_mm": 18,
            "jurisdiction": "DE",
            "furniture": "shelf",
            "collection": Collection.MATERIALS,
        },
    )
    result = search_engineering(db_session, data)
    assert [hit["version_id"] for hit in result["evidence"]] == [str(eligible.id)]
    assert not any(
        hit["version_id"] in (str(wrong.id), str(denied.id))
        for hit in result["evidence"]
    )
    assert "MPa" in result["evidence"][0]["text"] and result["evidence"][0]["block"][
        "pages"
    ] == [1]


def test_local_only_property_text_stays_out_of_remote_results(
    db_session, tmp_path, fake_embedder
):
    version = publish(db_session, tmp_path, remote=False)
    query = SearchIn(query="TEST board", mode="keyword")
    local = search_engineering(db_session, query, remote=False)
    assert len(local["evidence"]) == 1
    remote = search_engineering(db_session, query, remote=True)
    assert remote["evidence"] == [] and remote["metadata_only"]
    assert "2000" not in str(remote) and "properties" not in str(remote)
    assert resolve_evidence(db_session, f"{version.id}:row-1", remote=True) is None


def test_remote_block_and_page_scope_deny_unknown_or_partial_coverage(
    db_session, tmp_path, fake_embedder
):
    version = publish(db_session, tmp_path)
    grants = {scope: {} for scope in Scope if scope != Scope.COMMERCIAL}
    grants[Scope.REMOTE] = {"blocks": ["another-row"], "pages": [1]}
    decide_rights(
        db_session,
        version.id,
        RightsIn(
            action="approve",
            reviewer="fixture author",
            evidence="Narrowed permitted blocks",
            grants=grants,
        ),
    )
    assert (
        search_engineering(db_session, SearchIn(query="TEST", mode="keyword"))[
            "evidence"
        ]
        == []
    )
    grants[Scope.REMOTE] = {"blocks": ["row-1"], "pages": [2]}
    decide_rights(
        db_session,
        version.id,
        RightsIn(
            action="approve",
            reviewer="fixture author",
            evidence="Narrowed permitted pages",
            grants=grants,
        ),
    )
    assert (
        search_engineering(db_session, SearchIn(query="TEST", mode="vector"))[
            "evidence"
        ]
        == []
    )


def test_conflicting_evidence_is_not_averaged(db_session, tmp_path, fake_embedder):
    first = publish(db_session, tmp_path, text="TEST P2 board E 2000 MPa dry service")
    second = publish(
        db_session, tmp_path, text="TEST P2 board E 2500 MPa different test condition"
    )
    properties = []
    for version, value, condition in (
        (first, 2000, "dry only"),
        (second, 2500, "different test condition"),
    ):
        properties.append(
            add_property(
                db_session,
                version.id,
                PropertyIn(
                    block_id="row-1",
                    kind="E_MPa",
                    original_value=value,
                    original_unit="MPa",
                    value_basis="mean",
                    standard_or_model="TEST P2",
                    material_grade="P2",
                    thickness_mm=18,
                    page_section="p. 1",
                    conditions={"service": condition},
                ),
            )
        )
    result = search_engineering(
        db_session, SearchIn(query="TEST board", mode="keyword")
    )
    assert len(result["evidence"]) == 2
    assert any("2000" in hit["text"] for hit in result["evidence"])
    assert any("2500" in hit["text"] for hit in result["evidence"])
    assert all(
        hit["conflicts"][0]["status"] == "CONFLICT_REQUIRING_RESOLUTION"
        for hit in result["evidence"]
    )
    from app.engineering.chat import render_answer

    allowed = [hit["evidence_id"] for hit in result["evidence"]]
    # Choosing only one record in a model envelope cannot hide its competitor.
    raw = json.dumps(
        {"evidence_ids": [f"{first.id}:row-1"], "property_ids": [str(properties[0].id)]}
    )
    rendered = render_answer(
        raw, db_session, allowed, "engineering elasticity", enabled=True
    )
    assert all(
        text in rendered
        for text in (
            "Conflict requiring resolution",
            "2000",
            "2500",
            "dry only",
            "different test condition",
        )
    )
    decide_rights(
        db_session,
        second.id,
        RightsIn(
            action="revoke", reviewer="fixture author", evidence="test withdrawal"
        ),
    )
    after_revoke = render_answer(
        raw, db_session, allowed, "engineering elasticity", enabled=True
    )
    assert (
        "2500" not in after_revoke
        and "Conflict requiring resolution" not in after_revoke
    )


def test_superseded_edition_requires_explicit_historical_filter(
    db_session, tmp_path, fake_embedder
):
    old = publish(db_session, tmp_path, edition="1")
    new = publish(db_session, tmp_path, edition="2")
    old.superseded_by = new.id
    db_session.flush()
    current = search_engineering(
        db_session, SearchIn(query="TEST board", mode="keyword")
    )
    assert [hit["version_id"] for hit in current["evidence"]] == [str(new.id)]
    historical = search_engineering(
        db_session,
        SearchIn(query="TEST board", mode="keyword", filters={"edition": "1"}),
    )
    assert historical["evidence"][0]["historical"] is True


def test_revoked_content_is_retained_but_never_returned(
    db_session, tmp_path, fake_embedder
):
    version = publish(db_session, tmp_path, denied=True)
    assert (
        db_session.scalar(
            select(EngineeringChunk).where(EngineeringChunk.version_id == version.id)
        )
        is not None
    )
    assert resolve_evidence(db_session, f"{version.id}:row-1") is None
    assert (
        search_engineering(db_session, SearchIn(query="TEST", mode="keyword"))[
            "evidence"
        ]
        == []
    )
