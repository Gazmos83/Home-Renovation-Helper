"""Recommended reading for wall-hung items, and local reading of rights-eligible blocks.

Everything here is computed from the catalogue and the spec by fixed rules. Nothing
is sent to a model or exported to tracing; the routes serve it to the owner only.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EngineeringAssessment,
    EngineeringCalculationReport,
    EngineeringChunk,
    KnowledgeRightsDecision,
    KnowledgeSource,
    KnowledgeSourceVersion,
)
from app.engineering.registry import current_rights, permits
from app.engineering.schemas import Collection, EvidenceBlock, Scope

READING_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "reading_rules.yaml"
ITEM_KINDS = ("wall_shelf", "wall_module")
BLOCKS_PER_PAGE = 20
NOT_RECORDED = "not recorded"
NOTICE = (
    "Recommended reading, not a safety approval. Fixing an item to a wall depends on the "
    "wall's substrate, the anchor and the load. NOT VERIFIED."
)
NO_SOURCE = "No recorded source covers this item"
CITATION_FIELDS = (
    "publisher",
    "edition",
    "standard_or_model",
    "page_section",
    "jurisdiction",
)


class ReadingRulesError(ValueError):
    pass


class ReadingRefused(ValueError):
    pass


class _Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    applicable_furniture: list[str] = []
    collections: list[Collection] = []


def load_reading_rules(path: Path = READING_RULES_PATH) -> dict[str, _Rule]:
    """The item-kind rule table; a malformed file stops startup naming it."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ReadingRulesError(f"reading rules not found: {path}") from error
    except yaml.YAMLError as error:
        raise ReadingRulesError(f"reading rules are not valid YAML: {path}") from error
    if not isinstance(raw, Mapping):
        raise ReadingRulesError(f"{path.name}: must be a mapping of item kinds")
    unknown = sorted(str(kind) for kind in set(raw) - set(ITEM_KINDS))
    if unknown:
        raise ReadingRulesError(
            f"{path.name}: unknown item kind(s) {', '.join(unknown)}; only {', '.join(ITEM_KINDS)} are allowed"
        )
    rules = {}
    for kind in ITEM_KINDS:
        if kind not in raw:
            raise ReadingRulesError(f"{path.name}: missing item kind {kind}")
        body = raw[kind]
        if isinstance(body, Mapping) and isinstance(body.get("collections"), list):
            # Strict enums take their values, not their names; YAML gives plain strings.
            body = {**body, "collections": [_collection(path, kind, value) for value in body["collections"]]}
        try:
            rules[kind] = _Rule.model_validate(body)
        except ValidationError as error:
            raise ReadingRulesError(f"{path.name}: {kind}: {error.errors()[0]['msg']}") from error
        if not rules[kind].applicable_furniture and not rules[kind].collections:
            raise ReadingRulesError(f"{path.name}: {kind} names no furniture value or collection")
    return rules


def _collection(path: Path, kind: str, value: Any) -> Collection:
    try:
        return Collection(value)
    except ValueError as error:
        raise ReadingRulesError(f"{path.name}: {kind}: unknown collection {value!r}") from error


def wall_hung_items(spec: Mapping[str, Any]) -> list[dict[str, str]]:
    """Every wall shelf, and every module stated as `mounting: wall`; nothing is inferred from height."""
    items = [
        {"id": shelf["id"], "name": shelf["name"], "kind": "wall_shelf"}
        for shelf in spec.get("wall_shelves") or []
    ]
    items += [
        {"id": module["id"], "name": module["name"], "kind": "wall_module"}
        for module in spec.get("modules") or []
        if module.get("mounting") == "wall"
    ]
    return items


def current_versions(session: Session) -> list[tuple[KnowledgeSource, KnowledgeSourceVersion]]:
    """The newest non-superseded version of each registered source."""
    rows = session.execute(
        select(KnowledgeSource, KnowledgeSourceVersion)
        .join(KnowledgeSourceVersion, KnowledgeSourceVersion.source_id == KnowledgeSource.id)
        .where(KnowledgeSourceVersion.superseded_by.is_(None))
        .order_by(KnowledgeSourceVersion.created_at.desc())
    ).all()
    seen, current = set(), []
    for source, version in rows:
        if source.id not in seen:
            seen.add(source.id)
            current.append((source, version))
    return current


def _matched_by(rule: _Rule, version: KnowledgeSourceVersion) -> str | None:
    furniture = (version.attributes or {}).get("applicable_furniture") or []
    for value in rule.applicable_furniture:
        if value in furniture:
            return f"furniture: {value}"
    for collection in rule.collections:
        if collection.value in (version.collections or []):
            return f"collection: {collection.value}"
    return None


def reading_list(session: Session, spec: Mapping[str, Any], rules: Mapping[str, _Rule]) -> dict[str, Any]:
    items = wall_hung_items(spec)
    versions = current_versions(session)
    entries: dict[UUID, dict[str, Any]] = {}
    gaps = []
    for item in items:
        found = False
        for source, version in versions:
            matched = _matched_by(rules[item["kind"]], version)
            if matched is None:
                continue
            found = True
            entry = entries.setdefault(version.id, _entry(source, version))
            entry["items"].append(item["id"])
            entry["matched_by"][item["id"]] = matched
        if not found:
            gaps.append({"item": item["id"], "name": item["name"], "reason": NO_SOURCE})
    ordered = sorted(
        entries.values(), key=lambda entry: (entry["verification_status"] != "verified", entry["title"].lower())
    )
    return {"notice": NOTICE, "items": items, "entries": ordered, "gaps": gaps}


def _entry(source: KnowledgeSource, version: KnowledgeSourceVersion) -> dict[str, Any]:
    attributes = version.attributes or {}
    # The catalogue's public link only; a confined local file path is never shown.
    return {
        "version_id": str(version.id),
        "title": attributes.get("title") or source.title,
        **{field: attributes.get(field) or NOT_RECORDED for field in CITATION_FIELDS},
        "verification_status": version.verification_status,
        "source_url": attributes.get("source_url") or source.source_url,
        "items": [],
        # The rule that matched, per item: a source can match two items by different rules.
        "matched_by": {},
    }


def report_cited_versions(session: Session, package_id: str, version: int) -> set[UUID]:
    """Source versions cited by the evidence snapshots of a version's stored reports."""
    cited = set()
    assessments = session.scalars(
        select(EngineeringAssessment)
        .join(EngineeringCalculationReport, EngineeringCalculationReport.assessment_id == EngineeringAssessment.id)
        .where(EngineeringCalculationReport.package_id == package_id, EngineeringCalculationReport.version == version)
    )
    for assessment in assessments:
        for evidence_id in (assessment.snapshot or {}).get("evidence") or {}:
            try:
                cited.add(UUID(evidence_id.split(":", 1)[0]))
            except ValueError:
                continue
    return cited


def unreadable_reason(session: Session, version: KnowledgeSourceVersion) -> str | None:
    """Why a source version cannot be read locally at all, or None when some block may be."""
    latest = session.scalar(
        select(KnowledgeRightsDecision)
        .where(KnowledgeRightsDecision.version_id == version.id)
        .order_by(KnowledgeRightsDecision.sequence.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    if latest is None:
        return "rights pending"
    if latest.action == "revoke":
        return "rights revoked"
    if latest.expires_at is not None and latest.expires_at <= datetime.now(UTC):
        return "rights expired"
    if not all(scope.value in latest.grants for scope in (Scope.RETRIEVE, Scope.RETAIN)):
        return "rights do not permit local reading"
    if version.state != "published":
        return "no published blocks"
    return None


def read_blocks(
    session: Session, version_id: UUID, allowed: set[UUID], page: int = 1
) -> dict[str, Any]:
    """One page of a source version's blocks the current rights let the owner read here."""
    if version_id not in allowed:
        raise ReadingRefused("this source is not on the version's reading list or cited by its reports")
    version = session.get(KnowledgeSourceVersion, version_id, populate_existing=True)
    if version is None:
        raise ReadingRefused("source version not found")
    source = session.get(KnowledgeSource, version.source_id)
    link = (version.attributes or {}).get("source_url") or (source.source_url if source else None)
    base = {"version_id": str(version.id), "title": (version.attributes or {}).get("title"), "source_url": link}
    reason = unreadable_reason(session, version)
    if reason is not None:
        return {**base, "readable": False, "reason": reason, "blocks": [], "page": page, "more": False}
    rights = current_rights(session, version.id)
    chunks = session.scalars(
        select(EngineeringChunk).where(EngineeringChunk.version_id == version.id).order_by(EngineeringChunk.ordinal)
    ).all()
    permitted = []
    for chunk in chunks:
        block = EvidenceBlock.model_validate(chunk.provenance)
        if all(
            permits(rights, scope, block_id=block.block_id, pages=block.pages)
            for scope in (Scope.RETRIEVE, Scope.RETAIN)
        ):
            permitted.append((chunk, block))
    if not permitted:
        reason = "no published blocks" if not chunks else "rights do not permit reading any block"
        return {**base, "readable": False, "reason": reason, "blocks": [], "page": page, "more": False}
    start = (page - 1) * BLOCKS_PER_PAGE
    shown = permitted[start : start + BLOCKS_PER_PAGE]
    return {
        **base,
        "readable": True,
        "reason": None,
        "page": page,
        "more": start + BLOCKS_PER_PAGE < len(permitted),
        "blocks": [
            {
                "block_id": block.block_id,
                "kind": block.kind,
                "text": block.content,
                "pages": block.pages,
                "printed_pages": block.printed_pages,
                "section": block.section,
                "headers": block.headers,
                "conditions": block.conditions,
                "verification_status": chunk.verification_status,
            }
            for chunk, block in shown
        ],
    }
