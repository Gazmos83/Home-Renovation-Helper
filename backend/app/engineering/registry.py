"""Source registry and fail-closed, current, operation-specific rights."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EngineeringChunk,
    EngineeringProperty,
    KnowledgeRightsDecision,
    KnowledgeSource,
    KnowledgeSourceVersion,
)
from app.engineering.schemas import (
    EvidenceBlock,
    PropertyIn,
    ReviewIn,
    RightsIn,
    Scope,
    SourceIn,
    with_dual_tags,
)


class EvidenceRefused(ValueError):
    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


def register_source(session: Session, source: SourceIn) -> KnowledgeSourceVersion:
    known = session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.key == source.key)
    )
    if known is None:
        known = KnowledgeSource(
            key=source.key,
            title=source.metadata.title,
            publisher=source.metadata.publisher,
            source_url=source.metadata.source_url,
        )
        session.add(known)
        session.flush()
    # Metadata flags never authorise embedding; only documented Scope.EMBED rights do.
    if source.metadata.approved_for_embedding:
        raise EvidenceRefused(
            "approved_for_embedding",
            "registration cannot self-approve embedding; record Scope.EMBED rights separately",
        )
    version = KnowledgeSourceVersion(
        source_id=known.id,
        edition=source.metadata.edition,
        attributes=source.metadata.model_dump(mode="json"),
        collections=[item.value for item in with_dual_tags(source.collections)],
        verification_status="unverified",
    )
    # Metadata cannot self-approve a source through a submitted verification field.
    if source.metadata.verification_status != "unverified":
        raise EvidenceRefused(
            "verification_status",
            "registration is unverified; use explicit technical review",
        )
    session.add(version)
    session.flush()
    return version


def version_or_refuse(session: Session, version_id: UUID) -> KnowledgeSourceVersion:
    version = session.get(KnowledgeSourceVersion, version_id)
    if version is None:
        raise EvidenceRefused("version_id", "source version not found")
    return version


def decide_rights(
    session: Session, version_id: UUID, decision: RightsIn
) -> KnowledgeRightsDecision:
    version_or_refuse(session, version_id)
    row = KnowledgeRightsDecision(
        version_id=version_id,
        **decision.model_dump(mode="python", exclude={"grants"}),
        grants={
            key.value: value.model_dump(mode="json")
            for key, value in decision.grants.items()
        },
    )
    session.add(row)
    session.flush()
    return row


def current_rights(
    session: Session, version_id: UUID
) -> KnowledgeRightsDecision | None:
    # populate_existing prevents cached decisions surviving a late request check.
    row = session.scalar(
        select(KnowledgeRightsDecision)
        .where(KnowledgeRightsDecision.version_id == version_id)
        .order_by(KnowledgeRightsDecision.sequence.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    if (
        row is None
        or row.action != "approve"
        or (row.expires_at is not None and row.expires_at <= datetime.now(UTC))
    ):
        return None
    return row


def permits(
    decision: KnowledgeRightsDecision | None,
    scope: Scope,
    *,
    block_id: str | None = None,
    pages: list[int] | None = None,
) -> bool:
    if decision is None or scope.value not in decision.grants:
        return False
    grant = decision.grants[scope.value]
    permitted_blocks = grant.get("blocks")
    permitted_pages = grant.get("pages")
    if permitted_blocks is not None and (
        block_id is None or block_id not in permitted_blocks
    ):
        return False
    return not (
        permitted_pages is not None
        and (not pages or not set(pages).issubset(permitted_pages))
    )


def require_rights(
    session: Session, version_id: UUID, scope: Scope, block: EvidenceBlock | None = None
) -> None:
    if not permits(
        current_rights(session, version_id),
        scope,
        block_id=block.block_id if block else None,
        pages=block.pages if block else None,
    ):
        raise EvidenceRefused(
            scope.value, "current documented rights do not permit this operation/block"
        )


def review_source(
    session: Session, version_id: UUID, review: ReviewIn
) -> KnowledgeSourceVersion:
    version = version_or_refuse(session, version_id)
    version.verification_status, version.reviewed_by, version.reviewed_at = (
        review.status,
        review.reviewer,
        datetime.now(UTC),
    )
    session.flush()
    return version


def add_property(
    session: Session, version_id: UUID, data: PropertyIn
) -> EngineeringProperty:
    version = version_or_refuse(session, version_id)
    chunk = session.scalar(
        select(EngineeringChunk).where(
            EngineeringChunk.version_id == version_id,
            EngineeringChunk.block_id == data.block_id,
        )
    )
    if chunk is None:
        raise EvidenceRefused("block_id", "property requires an ingested source block")
    block = EvidenceBlock.model_validate(chunk.provenance)
    require_rights(session, version_id, Scope.RETAIN, block)
    for field in ("standard_or_model", "material_grade", "thickness_mm"):
        known = version.attributes.get(field)
        provided = getattr(data, field)
        if known is not None and provided != known:
            raise EvidenceRefused(
                field, "property identity must match its source version"
            )
    prop = EngineeringProperty(
        version_id=version_id,
        block_id=data.block_id,
        kind=data.kind,
        record=data.model_dump(mode="json"),
        verification_status="unverified",
    )
    session.add(prop)
    session.flush()
    return prop


def review_property(
    session: Session, property_id: UUID, review: ReviewIn
) -> EngineeringProperty:
    prop = session.get(EngineeringProperty, property_id)
    if prop is None:
        raise EvidenceRefused("property_id", "property not found")
    if review.status == "verified":
        data = PropertyIn.model_validate(prop.record)
        chunk = session.scalar(
            select(EngineeringChunk).where(
                EngineeringChunk.version_id == prop.version_id,
                EngineeringChunk.block_id == prop.block_id,
            )
        )
        if (
            chunk is None
            or chunk.verification_status == "needs_review"
            or data.value_basis == "unknown"
            or all(item is None for item in (data.value, data.minimum, data.maximum))
        ):
            raise EvidenceRefused(
                "verification_status",
                "resolve block ambiguity, value and value basis before verification",
            )
    prop.verification_status, prop.reviewed_by, prop.reviewed_at = (
        review.status,
        review.reviewer,
        datetime.now(UTC),
    )
    session.flush()
    return prop


def edit_property(
    session: Session, property_id: UUID, data: PropertyIn
) -> EngineeringProperty:
    """Edit an unverified candidate; reviewed records require a new candidate.

    Resetting a reviewed value in place would change evidence already selected
    by a conversation or an assessment. Those records keep their own identity.
    """
    prop = session.get(EngineeringProperty, property_id)
    if prop is None:
        raise EvidenceRefused("property_id", "property not found")
    if prop.reviewed_by is not None:
        raise EvidenceRefused("property_id", "reviewed records require a new candidate")
    with session.begin_nested():
        candidate = add_property(session, prop.version_id, data)
        prop.block_id, prop.kind, prop.record = (
            candidate.block_id,
            candidate.kind,
            candidate.record,
        )
        session.delete(candidate)
        session.flush()
    return prop
