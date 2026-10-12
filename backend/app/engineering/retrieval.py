"""Engineering filters/rights precede ranking in every retrieval mode."""

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, literal_column, or_, select
from sqlalchemy.orm import Session

from app.db.chunk_store import KEYWORD_WEIGHT, VECTOR_WEIGHT
from app.db.models import (
    EngineeringChunk,
    EngineeringProperty,
    KnowledgeRightsDecision,
    KnowledgeSourceVersion,
)
from app.embedding import embed_one
from app.engineering.kitchen import recommended_collections
from app.engineering.registry import current_rights, permits
from app.engineering.schemas import EvidenceBlock, Scope, SearchFilters, SearchIn

# Engineering development fixtures measured with real local BGE-M3 embeddings.
MIN_RELEVANCE = {"hybrid": 0.3, "vector": 0.5, "keyword": 0.0}


def _kitchen_collection_values(query: str, filters: SearchFilters) -> list[str] | None:
    """When no explicit collection filter is set, prefer kitchen + dual-tagged namespaces."""
    if filters.collection is not None:
        return None
    selected = recommended_collections(query)
    return [item.value for item in selected] or None


def _matches(
    version: KnowledgeSourceVersion,
    filters: SearchFilters,
    *,
    kitchen_collections: list[str] | None = None,
) -> bool:
    if (
        filters.collection is not None
        and filters.collection.value not in version.collections
    ):
        return False
    if kitchen_collections is not None and not any(
        item in version.collections for item in kitchen_collections
    ):
        return False
    if filters.edition is None and version.superseded_by is not None:
        return False
    for key, value in filters.model_dump(exclude_none=True).items():
        if key == "collection":
            continue
        if key == "furniture":
            if value not in (version.attributes.get("applicable_furniture") or []):
                return False
        elif version.attributes.get(key) != value:
            return False
    return True


def _scope_clause(scope: Scope):
    grant = KnowledgeRightsDecision.grants[scope.value]
    null_json = literal_column("'null'::jsonb")
    pages = EngineeringChunk.provenance["pages"]
    return and_(
        KnowledgeRightsDecision.grants.has_key(scope.value),  # noqa: W601 - PostgreSQL JSON key operator
        or_(
            grant["blocks"] == null_json,
            grant["blocks"].contains(func.jsonb_build_array(EngineeringChunk.block_id)),
        ),
        or_(
            grant["pages"] == null_json,
            and_(func.jsonb_array_length(pages) > 0, grant["pages"].contains(pages)),
        ),
    )


def search_statement(data: SearchIn, vector: list[float] | None, *, remote: bool):
    latest = (
        select(
            KnowledgeRightsDecision.version_id,
            func.max(KnowledgeRightsDecision.sequence).label("sequence"),
        )
        .group_by(KnowledgeRightsDecision.version_id)
        .subquery()
    )
    # Natural-language queries contain optional descriptions absent from exact
    # manuals. Match any token, then let ranking and mandatory identity filters
    # choose evidence. Parameters remain bound; user text is never SQL syntax.
    terms = " OR ".join(re.findall(r"[\w]+", data.query))
    query_parts = [
        func.websearch_to_tsquery(literal_column(f"'{language}'"), terms)
        for language in ("german", "english", "simple")
    ]
    tsquery = query_parts[0].op("||")(query_parts[1]).op("||")(query_parts[2])
    rank = func.ts_rank(EngineeringChunk.search_vector, tsquery, 32)
    similarity = (
        1 - EngineeringChunk.embedding.cosine_distance(vector)
        if vector is not None
        else None
    )
    score = (
        rank
        if data.mode == "keyword"
        else similarity
        if data.mode == "vector"
        else similarity * VECTOR_WEIGHT + rank * KEYWORD_WEIGHT
    )
    statement = (
        select(EngineeringChunk, KnowledgeSourceVersion, score.label("score"))
        .join(KnowledgeSourceVersion)
        .join(latest, latest.c.version_id == KnowledgeSourceVersion.id)
        .join(
            KnowledgeRightsDecision,
            KnowledgeRightsDecision.sequence == latest.c.sequence,
        )
    )
    statement = statement.where(
        KnowledgeSourceVersion.state == "published",
        KnowledgeRightsDecision.action == "approve",
        or_(
            KnowledgeRightsDecision.expires_at.is_(None),
            KnowledgeRightsDecision.expires_at > datetime.now(UTC),
        ),
        _scope_clause(Scope.RETAIN),
        _scope_clause(Scope.RETRIEVE),
    )
    if remote:
        statement = statement.where(_scope_clause(Scope.REMOTE))
    if data.mode == "keyword":
        statement = statement.where(
            EngineeringChunk.search_vector.bool_op("@@")(tsquery)
        )
    if data.filters.edition is None:
        statement = statement.where(KnowledgeSourceVersion.superseded_by.is_(None))
    kitchen_collections = _kitchen_collection_values(data.query, data.filters)
    if kitchen_collections is not None:
        statement = statement.where(
            or_(
                *[
                    KnowledgeSourceVersion.collections.contains([value])
                    for value in kitchen_collections
                ]
            )
        )
    for key, value in data.filters.model_dump(exclude_none=True, mode="json").items():
        if key == "collection":
            statement = statement.where(
                KnowledgeSourceVersion.collections.contains([value])
            )
        elif key == "furniture":
            statement = statement.where(
                KnowledgeSourceVersion.attributes["applicable_furniture"].contains(
                    [value]
                )
            )
        else:
            statement = statement.where(
                KnowledgeSourceVersion.attributes.contains({key: value})
            )
    return (
        statement.where(
            score
            >= (
                data.min_relevance
                if data.min_relevance is not None
                else MIN_RELEVANCE[data.mode]
            )
        )
        .order_by(score.desc(), EngineeringChunk.version_id, EngineeringChunk.ordinal)
        .limit(data.limit)
    )


def evidence_packet(
    session: Session,
    chunk: EngineeringChunk,
    version: KnowledgeSourceVersion,
    *,
    remote: bool,
) -> dict | None:
    block = EvidenceBlock.model_validate(chunk.provenance)
    rights = current_rights(session, version.id)
    if any(
        not permits(rights, scope, block_id=block.block_id, pages=block.pages)
        for scope in (
            [Scope.RETAIN, Scope.RETRIEVE, Scope.REMOTE]
            if remote
            else [Scope.RETAIN, Scope.RETRIEVE]
        )
    ):
        return None
    properties = []
    for prop in session.scalars(
        select(EngineeringProperty).where(
            EngineeringProperty.version_id == version.id,
            EngineeringProperty.block_id == chunk.block_id,
        )
    ):
        properties.append(
            {
                "id": str(prop.id),
                "verification_status": prop.verification_status,
                **prop.record,
            }
        )
    return {
        "evidence_id": f"{version.id}:{chunk.block_id}",
        "version_id": str(version.id),
        "block_id": chunk.block_id,
        "metadata": {
            **version.attributes,
            "verification_status": version.verification_status,
        },
        "historical": version.superseded_by is not None,
        "block": block.model_dump(mode="json"),
        "text": chunk.content,
        "properties": properties,
    }


def resolve_evidence(
    session: Session, evidence_id: str, *, remote: bool = True
) -> dict | None:
    try:
        version_text, block_id = evidence_id.split(":", 1)
        version_id = UUID(version_text)
    except ValueError, AttributeError:
        return None
    version = session.get(KnowledgeSourceVersion, version_id, populate_existing=True)
    if version is None or version.state != "published":
        return None
    chunk = session.scalar(
        select(EngineeringChunk).where(
            EngineeringChunk.version_id == version_id,
            EngineeringChunk.block_id == block_id,
        )
    )
    return (
        evidence_packet(session, chunk, version, remote=remote)
        if chunk is not None
        else None
    )


def property_conflicts(packets: list[dict]) -> list[dict]:
    """Preserve differing values for the same exact product/property identity.

    Different conditions or value bases may explain the difference, but cannot
    be resolved by averaging or a model choosing one source. Only already
    eligible packets may be supplied to this function.
    """
    groups = {}
    for packet in packets:
        metadata = packet["metadata"]
        for prop in packet["properties"]:
            identity = tuple(
                prop.get(field) or metadata.get(field)
                for field in ("standard_or_model", "material_grade", "thickness_mm")
            )
            if not identity[0]:
                continue
            key = (*identity, prop["kind"])
            if prop["value"] is None and prop["minimum"] is None:
                continue
            groups.setdefault(key, []).append(
                {
                    "evidence_id": packet["evidence_id"],
                    "metadata": metadata,
                    "pages": packet["block"]["pages"],
                    "property": prop,
                }
            )
    conflicts = []
    for key, entries in groups.items():
        values = {
            (
                item["property"]["value"],
                item["property"]["minimum"],
                item["property"]["maximum"],
            )
            for item in entries
        }
        if len(values) > 1:
            conflicts.append(
                {
                    "identity": dict(
                        zip(
                            (
                                "standard_or_model",
                                "material_grade",
                                "thickness_mm",
                                "kind",
                            ),
                            key,
                            strict=True,
                        )
                    ),
                    "status": "CONFLICT_REQUIRING_RESOLUTION",
                    "reason": "Different applicable values/conditions; resolve source applicability and value basis before use. Do not average or select a value as verified resistance.",
                    "records": entries,
                }
            )
    return conflicts


def with_conflicts(packets: list[dict]) -> list[dict]:
    conflicts = property_conflicts(packets)
    return [
        {
            **packet,
            "conflicts": [
                item
                for item in conflicts
                if any(
                    row["evidence_id"] == packet["evidence_id"]
                    for row in item["records"]
                )
            ],
        }
        for packet in packets
    ]


def search_engineering(
    session: Session, data: SearchIn, *, remote: bool = True
) -> dict:
    vector = embed_one(data.query) if data.mode != "keyword" else None
    packets = []
    for chunk, version, score in session.execute(
        search_statement(data, vector, remote=remote)
    ):
        packet = evidence_packet(session, chunk, version, remote=remote)
        if packet is not None:
            packet["score"] = float(score)
            packets.append(packet)
    # Catalogue hits can disclose identity and a link, never property/excerpt fields.
    metadata_only = []
    words = [word.casefold() for word in data.query.split()]
    evidence_versions = {packet["version_id"] for packet in packets}
    kitchen_collections = _kitchen_collection_values(data.query, data.filters)
    for version in session.scalars(
        select(KnowledgeSourceVersion).order_by(
            KnowledgeSourceVersion.created_at.desc()
        )
    ):
        if (
            not _matches(
                version, data.filters, kitchen_collections=kitchen_collections
            )
            or str(version.id) in evidence_versions
        ):
            continue
        attributes = version.attributes
        title = " ".join(
            str(attributes.get(key) or "")
            for key in ("title", "standard_or_model", "edition")
        )
        if not any(word in title.casefold() for word in words):
            continue
        metadata_only.append(
            {
                "version_id": str(version.id),
                "title": attributes["title"],
                "publisher": attributes["publisher"],
                "source_url": attributes["source_url"],
                "edition": version.edition,
                "reason": "No applicable content eligible for this request; metadata is not supporting evidence.",
            }
        )
        if len(metadata_only) >= data.limit:
            break
    return {
        "evidence": with_conflicts(packets),
        "metadata_only": metadata_only,
        "limitation": None
        if packets
        else "No applicable eligible engineering evidence found.",
    }
