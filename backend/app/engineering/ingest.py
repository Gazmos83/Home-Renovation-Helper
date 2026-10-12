"""Rights-gated staging/extraction and atomic evidence publication."""

import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    EngineeringChunk,
    KnowledgeIngestionRun,
    KnowledgeSourceVersion,
)
from app.embedding import embed
from app.engineering.blocks import block_text, html_blocks, markdown_blocks, pdf_blocks
from app.engineering.fetch import KnowledgeFetcher
from app.engineering.registry import (
    EvidenceRefused,
    current_rights,
    permits,
    require_rights,
    version_or_refuse,
)
from app.engineering.schemas import EvidenceBlock, Scope


def confined_path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise EvidenceRefused("local_path", "path leaves the guidelines root")
    return target


def stage_file(
    session: Session,
    version_id: UUID,
    root: Path,
    relative: str,
    *,
    max_bytes: int | None = None,
) -> KnowledgeSourceVersion:
    version = version_or_refuse(session, version_id)
    require_rights(session, version_id, Scope.RETAIN)
    target = confined_path(root, relative)
    if not target.is_file() or target.suffix.lower() not in (".pdf", ".md", ".html"):
        raise EvidenceRefused(
            "local_path", "a readable PDF/Markdown/HTML file is required"
        )
    if max_bytes is not None and target.stat().st_size > max_bytes:
        raise EvidenceRefused("file", "file exceeds the upload limit")
    # Hash in bounded chunks, even for the large reviewed CLI source path.
    digest = hashlib.sha256()
    with target.open("rb") as stream:
        first = stream.read(1024 * 1024)
        if target.suffix.lower() == ".pdf" and not first.startswith(b"%PDF-"):
            raise EvidenceRefused("file", "file is not a PDF by its bytes")
        digest.update(first)
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    hashed = digest.hexdigest()
    if version.content_hash is not None and version.content_hash != hashed:
        raise EvidenceRefused(
            "content_hash", "changed content needs a new source version"
        )
    version.content_hash, version.local_path = hashed, relative
    session.flush()
    return version


def _read_blocks(
    session: Session, settings, version: KnowledgeSourceVersion, *, fetcher=None
) -> list[EvidenceBlock]:
    rights = current_rights(session, version.id)
    if rights is None or Scope.EXTRACT.value not in rights.grants:
        raise EvidenceRefused(
            "extraction", "source remains metadata-only pending documented rights"
        )
    extract_pages = rights.grants[Scope.EXTRACT.value].get("pages")
    require_rights(session, version.id, Scope.RETAIN)
    if version.local_path:
        target = confined_path(settings.guideline_root, version.local_path)
        # Rehash before any extraction; a file changed in place is not the approved edition.
        stage_file(session, version.id, settings.guideline_root, version.local_path)
        if target.suffix.lower() == ".pdf":
            return pdf_blocks(target.read_bytes(), allowed_pages=extract_pages)
        if extract_pages is not None:
            raise EvidenceRefused(
                "extraction",
                "physical-page scopes require PDF or reviewed manual blocks",
            )
        text = target.read_text(encoding="utf-8")
        return (
            html_blocks(text)
            if target.suffix.lower() == ".html"
            else markdown_blocks(text)
        )
    url = version.attributes.get("source_url")
    if not url:
        raise EvidenceRefused("source_url", "no staged file or official URL")
    fetcher = fetcher or KnowledgeFetcher(settings)
    parts = urlsplit(url)
    with fetcher:
        rules = fetcher.fetch_rules(
            f"{parts.scheme}://{parts.netloc}", source=str(version.id)
        )
        if not rules.allows(url):
            raise EvidenceRefused("source_url", "host robots rules refuse this service")
        response = fetcher.fetch_page(url)
    content = response.content
    digest = hashlib.sha256(content).hexdigest()
    if version.content_hash is not None and version.content_hash != digest:
        raise EvidenceRefused(
            "content_hash", "changed remote document requires a new version"
        )
    version.content_hash = digest
    if content.startswith(b"%PDF-"):
        return pdf_blocks(content, allowed_pages=extract_pages)
    if extract_pages is not None:
        raise EvidenceRefused("extraction", "physical-page scopes require PDF")
    return html_blocks(response.text)


def ingest_version(
    session: Session,
    settings,
    version_id: UUID,
    *,
    reviewed_blocks: list[EvidenceBlock] | None = None,
    fetcher=None,
) -> KnowledgeIngestionRun:
    version = version_or_refuse(session, version_id)
    run = KnowledgeIngestionRun(
        version_id=version_id, state="failed", blocks=0, reused_vectors=0
    )
    session.add(run)
    session.flush()
    try:
        with session.begin_nested():
            if reviewed_blocks is not None:
                if not reviewed_blocks or any(
                    block.verification_status != "verified" for block in reviewed_blocks
                ):
                    raise EvidenceRefused(
                        "reviewed_blocks",
                        "manual ingestion requires explicitly reviewed complete blocks",
                    )
                blocks = reviewed_blocks
            else:
                blocks = _read_blocks(session, settings, version, fetcher=fetcher)
            # Only authorised blocks may be embedded; never extract a denied page.
            allowed: list[EvidenceBlock] = []
            for block in blocks:
                require_rights(session, version_id, Scope.EXTRACT, block)
                require_rights(session, version_id, Scope.RETAIN, block)
                if permits(
                    current_rights(session, version_id),
                    Scope.EMBED,
                    block_id=block.block_id,
                    pages=block.pages,
                ):
                    allowed.append(block)
            if not allowed:
                raise EvidenceRefused(
                    "local_embedding", "no authorised blocks to publish"
                )
            if len({block.block_id for block in allowed}) != len(allowed):
                raise EvidenceRefused("block_id", "duplicate block identities")
            previous = {
                chunk.content_hash: list(chunk.embedding)
                for chunk in session.scalars(
                    select(EngineeringChunk)
                    .join(KnowledgeSourceVersion)
                    .where(KnowledgeSourceVersion.source_id == version.source_id)
                )
            }
            incoming = []
            reused = 0
            # Bounded batches use the same single cached BGE-M3 embedder.
            for start in range(0, len(allowed), 4):
                batch = allowed[start : start + 4]
                texts = [block_text(block) for block in batch]
                hashes = [hashlib.sha256(text.encode()).hexdigest() for text in texts]
                changed = [
                    index
                    for index, digest in enumerate(hashes)
                    if digest not in previous
                ]
                vectors = embed([texts[index] for index in changed])
                calculated = dict(zip(changed, vectors, strict=True))
                for index, block in enumerate(batch):
                    require_rights(session, version_id, Scope.EMBED, block)
                    require_rights(session, version_id, Scope.RETAIN, block)
                    digest = hashes[index]
                    vector = previous.get(digest)
                    if vector is None:
                        vector = calculated[index]
                    else:
                        reused += 1
                    incoming.append(
                        EngineeringChunk(
                            version_id=version_id,
                            block_id=block.block_id,
                            ordinal=start + index,
                            kind=block.kind,
                            content=texts[index],
                            content_hash=digest,
                            provenance=block.model_dump(mode="json"),
                            verification_status=block.verification_status,
                            embedding=vector,
                        )
                    )
            # A fresh query here catches decisions committed during embedding.
            for block in allowed:
                require_rights(session, version_id, Scope.EMBED, block)
                require_rights(session, version_id, Scope.RETAIN, block)
            session.execute(
                delete(EngineeringChunk).where(
                    EngineeringChunk.version_id == version_id
                )
            )
            session.add_all(incoming)
            session.flush()
            version.state = "published"
            run.state, run.blocks, run.reused_vectors = (
                "published",
                len(incoming),
                reused,
            )
    except Exception as error:  # noqa: BLE001 - failed refresh preserves published rows
        run.state = "failed"
        run.reason = (
            str(error)
            if isinstance(error, EvidenceRefused)
            else f"extraction/publication failed: {type(error).__name__}"
        )
    session.flush()
    return run
