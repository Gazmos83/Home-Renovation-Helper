"""Developer-only engineering metadata, documented rights and evidence review."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.gate import require_dev
from app.db.models import (
    EngineeringChunk,
    EngineeringProperty,
    KnowledgeRightsDecision,
    KnowledgeSource,
    KnowledgeSourceVersion,
)
from app.engineering.catalogue import unregistered
from app.engineering.fetch import KnowledgeFetcher
from app.engineering.ingest import confined_path, ingest_version, stage_file
from app.engineering.registry import (
    EvidenceRefused,
    add_property,
    current_rights,
    decide_rights,
    edit_property,
    register_source,
    require_rights,
    review_property,
    review_source,
    version_or_refuse,
)
from app.engineering.retrieval import search_engineering
from app.engineering.schemas import (
    EvidenceBlock,
    PropertyIn,
    ReviewIn,
    RightsIn,
    Scope,
    SearchIn,
    SourceIn,
)

router = APIRouter(
    prefix="/admin/knowledge", tags=["admin"], dependencies=[Depends(require_dev)]
)


def _refused(error: EvidenceRefused) -> HTTPException:
    return HTTPException(
        422,
        detail={
            "failure_class": "engineering_evidence_refused",
            "field": error.field,
            "reason": error.reason,
        },
    )


def _out(session: Session, version: KnowledgeSourceVersion) -> dict:
    source = session.get(KnowledgeSource, version.source_id)
    rights = current_rights(session, version.id)
    return {
        "id": str(version.id),
        "key": source.key,
        "metadata": version.attributes,
        "collections": version.collections,
        "state": version.state,
        "verification_status": version.verification_status,
        "reviewed_by": version.reviewed_by,
        "rights_status": "approved" if rights else "pending_or_revoked",
        "grants": rights.grants if rights else {},
        "rights": [
            {
                "id": str(row.id),
                "action": row.action,
                "grants": row.grants,
                "evidence": row.evidence,
                "reviewer": row.reviewer,
                "expires_at": row.expires_at,
                "created_at": row.created_at,
            }
            for row in session.scalars(
                select(KnowledgeRightsDecision)
                .where(KnowledgeRightsDecision.version_id == version.id)
                .order_by(KnowledgeRightsDecision.sequence.desc())
            )
        ],
        "passages": session.scalar(
            select(func.count())
            .select_from(EngineeringChunk)
            .where(EngineeringChunk.version_id == version.id)
        ),
        "properties": [
            {
                "id": str(prop.id),
                "verification_status": prop.verification_status,
                "reviewed_by": prop.reviewed_by,
                **prop.record,
            }
            for prop in session.scalars(
                select(EngineeringProperty).where(
                    EngineeringProperty.version_id == version.id
                )
            )
        ],
        "local_path": version.local_path,
        "content_hash": version.content_hash,
        "superseded_by": str(version.superseded_by) if version.superseded_by else None,
    }


@router.get("")
def sources(request: Request) -> list[dict]:
    with Session(request.app.state.engine) as session:
        return [
            _out(session, version)
            for version in session.scalars(
                select(KnowledgeSourceVersion).order_by(
                    KnowledgeSourceVersion.created_at.desc()
                )
            )
        ]


@router.get("/catalogue")
def catalogue(request: Request) -> list[dict]:
    with Session(request.app.state.engine) as session:
        return [
            {"key": source.key, "metadata": source.metadata.model_dump(mode="json")}
            for source in unregistered(session)
        ]


@router.post("/catalogue/{key}/register", status_code=201)
def register_catalogue_entry(key: str, request: Request) -> dict:
    with Session(request.app.state.engine) as session:
        source = next((item for item in unregistered(session) if item.key == key), None)
        if source is None:
            raise HTTPException(
                404, detail="no unregistered catalogue entry has that key"
            )
        try:
            version = register_source(session, source)
            session.commit()
            return _out(session, version)
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("", status_code=201)
def register(data: SourceIn, request: Request) -> dict:
    from app.engineering.registry import register_source

    with Session(request.app.state.engine) as session:
        try:
            version = register_source(session, data)
            session.commit()
            return _out(session, version)
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("/search")
def preview(data: SearchIn, request: Request) -> dict:
    with Session(request.app.state.engine) as session:
        return search_engineering(session, data, remote=False)


@router.post("/{version_id}/rights")
def rights(version_id: UUID, data: RightsIn, request: Request) -> dict:
    with Session(request.app.state.engine) as session:
        try:
            decide_rights(session, version_id, data)
            session.commit()
            return _out(session, version_or_refuse(session, version_id))
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("/{version_id}/review")
def technical_review(version_id: UUID, data: ReviewIn, request: Request) -> dict:
    with Session(request.app.state.engine) as session:
        try:
            version = review_source(session, version_id, data)
            session.commit()
            return _out(session, version)
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("/{version_id}/file")
def upload(
    version_id: UUID, request: Request, file: Annotated[UploadFile, File()]
) -> dict:
    settings = request.app.state.settings
    with Session(request.app.state.engine) as session:
        try:
            version_or_refuse(session, version_id)
            require_rights(session, version_id, Scope.RETAIN)
            content = file.file.read(settings.guideline_upload_max_bytes + 1)
            if len(
                content
            ) > settings.guideline_upload_max_bytes or not content.startswith(b"%PDF-"):
                raise EvidenceRefused(
                    "file", "PDF bytes within the existing upload limit are required"
                )
            relative = f"knowledge/{version_id}/source.pdf"
            target = confined_path(settings.guideline_root, relative)
            if target.exists():
                raise EvidenceRefused(
                    "file",
                    "file already staged; changed content requires another version",
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            try:
                version = stage_file(
                    session,
                    version_id,
                    settings.guideline_root,
                    relative,
                    max_bytes=settings.guideline_upload_max_bytes,
                )
                session.commit()
            except Exception:
                target.unlink(missing_ok=True)
                raise
            return _out(session, version)
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("/{version_id}/ingest")
def ingest(
    version_id: UUID,
    request: Request,
    reviewed_blocks: list[EvidenceBlock] | None = None,
) -> dict:
    with Session(request.app.state.engine) as session:
        try:
            run = ingest_version(
                session,
                request.app.state.settings,
                version_id,
                reviewed_blocks=reviewed_blocks,
            )
            session.commit()
            return {
                "id": str(run.id),
                "state": run.state,
                "blocks": run.blocks,
                "reused_vectors": run.reused_vectors,
                "reason": run.reason,
            }
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("/{version_id}/ingest-link")
def ingest_link(version_id: UUID, request: Request) -> dict:
    settings = request.app.state.settings
    with Session(request.app.state.engine) as session:
        try:
            version = version_or_refuse(session, version_id)
            if not version.attributes.get("source_url"):
                raise EvidenceRefused("source_url", "this version has no official link")
            if version.local_path:
                raise EvidenceRefused(
                    "local_path", "a file is already staged; use authorised ingestion"
                )
            run = ingest_version(
                session,
                settings,
                version_id,
                fetcher=KnowledgeFetcher(
                    settings, max_bytes=settings.engineering_link_max_bytes
                ),
            )
            session.commit()
            return {
                "id": str(run.id),
                "state": run.state,
                "blocks": run.blocks,
                "reused_vectors": run.reused_vectors,
                "reason": run.reason,
            }
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("/{version_id}/properties", status_code=201)
def property_candidate(version_id: UUID, data: PropertyIn, request: Request) -> dict:
    with Session(request.app.state.engine) as session:
        try:
            add_property(session, version_id, data)
            session.commit()
            return _out(session, version_or_refuse(session, version_id))
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("/properties/{property_id}/review")
def property_review(property_id: UUID, data: ReviewIn, request: Request) -> dict:
    with Session(request.app.state.engine) as session:
        try:
            prop = review_property(session, property_id, data)
            session.commit()
            return _out(session, version_or_refuse(session, prop.version_id))
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.put("/properties/{property_id}")
def property_edit(property_id: UUID, data: PropertyIn, request: Request) -> dict:
    with Session(request.app.state.engine) as session:
        try:
            prop = edit_property(session, property_id, data)
            session.commit()
            return _out(session, version_or_refuse(session, prop.version_id))
        except EvidenceRefused as error:
            raise _refused(error) from None


@router.post("/{version_id}/supersede/{replacement_id}")
def supersede(version_id: UUID, replacement_id: UUID, request: Request) -> dict:
    with Session(request.app.state.engine) as session:
        try:
            old, new = (
                version_or_refuse(session, version_id),
                version_or_refuse(session, replacement_id),
            )
            if (
                old.id == new.id
                or old.source_id != new.source_id
                or new.state != "published"
                or new.superseded_by is not None
            ):
                raise EvidenceRefused(
                    "replacement_id",
                    "replacement must be another published edition of the same source",
                )
            old.superseded_by = new.id
            session.commit()
            return _out(session, old)
        except EvidenceRefused as error:
            raise _refused(error) from None
