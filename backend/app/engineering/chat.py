"""Typed claims, complete evidence packets and safe request copies."""

import json
import re
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.prompts import Passage, neutralise, wrap_passages
from app.db.models import (
    EngineeringAssessment,
    EngineeringEvidenceUse,
    KnowledgeSourceVersion,
)
from app.engineering.retrieval import (
    property_conflicts,
    resolve_evidence,
    with_conflicts,
)
from app.engineering.schemas import StrictModel

_ENGINEERING = re.compile(
    r"\b(engineering|structural|deflection|creep|anchorage|anchor|tipping|load[- ]?capacity|load[- ]?bearing|allowable span|safe|safety|bending strength|elasticity|tragfähig\w*|traglast|belastbarkeit|durchbiegung|verankerung|kippsicher\w*|wandbefestigung|festigkeit|elastizitätsmodul|sicher|sicherheit|"
    r"kitchen cabinet|wall cabinet|base cabinet|drawer|runner|hinge|worktop|countertop|"
    r"küchenschrank|kuechenschrank|schublade|scharnier|arbeitsplatte|oberschrank|unterschrank|"
    r"vollauszug|spülmaschine|spuelmaschine|backofen)\b|"
    r"\b(?:hold|carry|support|halten|tragen|belasten)\b.{0,80}\b\d+\s*(?:kg|kN|N)\b",
    re.IGNORECASE,
)
_REVISION = re.compile(
    r"\b(revise|change|widen|make|resize|add|remove|ändern|verbreitern|vergrößern|hinzufügen)\b",
    re.IGNORECASE,
)
INSUFFICIENT = "NOT VERIFIED. Numerical engineering calculation is not implemented. No capacity or conformity is established."


def engineering_intent(text: str) -> bool:
    from app.engineering.kitchen import kitchen_intents

    return bool(_ENGINEERING.search(text)) or bool(kitchen_intents(text))


def revision_intent(text: str) -> bool:
    return bool(_REVISION.search(text))


class EngineeringAnswer(StrictModel):
    """Selections, never model-authored values/statuses or free-form safety claims."""

    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    property_ids: list[str] = Field(default_factory=list, max_length=20)
    report_ids: list[UUID] = Field(default_factory=list, max_length=20)
    owner_assumptions: list[str] = Field(default_factory=list, max_length=20)


ANSWER_NOTE = (
    "This is an engineering turn. Use engineering evidence, never legacy or remembered ratings. "
    "Final text MUST be only JSON matching this contract: "
    + json.dumps(EngineeringAnswer.model_json_schema())
    + ". Select only evidence/property IDs returned by eligible tools in this turn. "
    "owner_assumptions must be exact substrings of the current owner's message. "
    "Code renders values, verification status, sources and missing inputs. "
    "Select report IDs only from the calculation/report tool in this turn; never reproduce remembered arithmetic. Unreviewed methods are unavailable. Keep ordinary confirmed revision tools available."
)


def wrapped_packet(packet: dict) -> str:
    metadata = packet["metadata"]
    return wrap_passages(
        [
            Passage(
                content=json.dumps(packet, ensure_ascii=False),
                title=metadata["title"],
                url=neutralise(
                    metadata.get("source_url") or "metadata-only local source"
                )
                .replace('"', "'")
                .replace("\n", " "),
                section=packet["block"].get("section") or "",
                scraped_at=metadata.get("retrieved_at") or "unknown",
            )
        ]
    )


def remember_evidence(
    session: Session, thread_id: UUID | None, packet: dict, package_id: str | None
) -> None:
    if thread_id is not None:
        session.add(
            EngineeringEvidenceUse(
                thread_id=thread_id,
                version_id=UUID(packet["version_id"]),
                block_id=packet["block_id"],
                qualifications={
                    "package_id": package_id,
                    "pages": packet["block"]["pages"],
                    "source_verification": packet["metadata"]["verification_status"],
                },
            )
        )


def has_engineering_history(session: Session, thread_id: UUID | None) -> bool:
    return thread_id is not None and (
        session.scalar(
            select(EngineeringEvidenceUse.id)
            .where(EngineeringEvidenceUse.thread_id == thread_id)
            .limit(1)
        )
        is not None
        or session.scalar(
            select(EngineeringAssessment.id)
            .where(EngineeringAssessment.thread_id == thread_id)
            .limit(1)
        )
        is not None
    )


def request_history(
    session: Session,
    messages: list,
    *,
    engineering: bool,
    enabled: bool,
    routing: bool = False,
    render_root=None,
) -> list:
    """Rebuild marked tool text at the final request boundary; stored history stays intact.

    Engineering turns use their current owner exchange rather than unassociated
    old guideline answers. Later ordinary turns omit earlier marked exchanges.
    """
    latest_owner = max(
        (index for index, msg in enumerate(messages) if isinstance(msg, HumanMessage)),
        default=0,
    )
    marked_turn = False
    legacy_source_turns: set[int] = set()
    turn_start = 0
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            turn_start = index
        if isinstance(message, AIMessage) and any(
            call.get("name") in {"search_guidelines", "search_catalog_knowledge"}
            for call in message.tool_calls
        ):
            legacy_source_turns.add(turn_start)
    turn_start = 0
    copied = []
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            marked_turn = bool(message.additional_kwargs.get("engineering"))
            turn_start = index
        marker = message.additional_kwargs.get("engineering")
        if engineering and index < latest_owner:
            continue
        if routing and turn_start in legacy_source_turns and index < latest_owner:
            continue
        if not engineering and index < latest_owner and (marker or marked_turn):
            continue
        if (
            marker
            and isinstance(message, ToolMessage)
            and message.additional_kwargs.get("engineering_report_ids")
        ):
            from app.engineering.reports import report_copy

            packets = [
                packet
                for identifier in message.additional_kwargs["engineering_report_ids"]
                if render_root is not None
                and (
                    packet := report_copy(
                        session, render_root, UUID(identifier), remote=True
                    )
                )
                is not None
            ]
            text = (
                "\n\n".join(
                    wrap_passages(
                        [
                            Passage(
                                content=json.dumps(packet, ensure_ascii=False),
                                title="Engineering report " + packet["report_id"],
                                url="local immutable assessment",
                                scraped_at="recorded snapshot",
                            )
                        ]
                    )
                    for packet in packets
                )
                or "Engineering report unavailable for this request; NOT VERIFIED."
            )
            copied.append(message.model_copy(update={"content": neutralise(text)}))
        elif (
            marker
            and isinstance(message, ToolMessage)
            and message.additional_kwargs.get("engineering_source")
        ):
            ids = message.additional_kwargs.get("engineering_evidence_ids") or []
            packets = [
                packet
                for evidence_id in ids
                if enabled
                and (packet := resolve_evidence(session, evidence_id)) is not None
            ]
            text = (
                "\n\n".join(
                    wrapped_packet(packet) for packet in with_conflicts(packets)
                )
                or "Engineering evidence is currently unavailable/ineligible; NOT VERIFIED."
            )
            metadata_ids = (
                message.additional_kwargs.get("engineering_metadata_ids") or []
            )
            text += metadata_links(session, metadata_ids)
            copied.append(message.model_copy(update={"content": text}))
        elif marker and isinstance(message, AIMessage) and not message.tool_calls:
            if index >= latest_owner:
                copied.append(message.model_copy(update={"content": INSUFFICIENT}))
        else:
            copied.append(message)
    return copied


def missing_inputs(text: str) -> list[str]:
    from app.engineering.kitchen import (
        KitchenIntent,
        kitchen_intents,
        refuses_cross_manufacturer,
        refuses_din_compliance_claim,
    )

    missing = [
        "exact material product/grade and reviewed properties",
        "declared loads and support/load distribution",
        "load duration and service conditions",
        "reviewed calculation method and acceptance criteria",
    ]
    lower = text.casefold()
    intents = set(kitchen_intents(text))
    if any(
        word in lower
        for word in ("wall", "anchor", "hanger", "wand", "dübel", "veranker")
    ) or KitchenIntent.HANGER_ANCHOR in intents:
        missing.extend(
            [
                "wall substrate and exact anchor/approval",
                "fixing geometry and load transfer; hanger rating does not verify the wall",
                "DIN EN 15939 tests hanging devices, not the wall substrate or anchors",
            ]
        )
    if any(
        word in lower
        for word in ("tv", "entertainment", "climb", "television", "kind", "kipp")
    ):
        missing.append(
            "TV/accessory masses, centre of gravity and foreseeable child-climbing/tipping cases"
        )
    if (
        any(
            word in lower
            for word in (
                "countertop",
                "worktop",
                "quartz",
                "ceramic",
                "arbeitsplatte",
                "steinplatte",
            )
        )
        or KitchenIntent.WORKTOP in intents
    ):
        missing.append(
            "exact countertop product/thickness and overhang, cutout and support instructions"
        )
    if any(
        word in lower for word in ("murphy", "wall bed", "folding bed", "schrankbett")
    ):
        missing.extend(
            [
                "matching mechanism manual/revision and full wall/anchor assessment",
                "qualified review of crush, impact and unintended deployment risks",
            ]
        )
    if KitchenIntent.DRAWER in intents or any(
        word in lower for word in ("runner", "auszug", "führung", "fuehrung")
    ):
        missing.extend(
            [
                "exact runner series/variant, revision and mounting geometry",
                "declared load conditions, drawer self-weight, box joints and cabinet support",
                "a runner rating alone does not certify the drawer or cabinet",
            ]
        )
    if KitchenIntent.HINGE in intents:
        missing.extend(
            [
                "door mass/dimensions, hinge type/count and manufacturer mounting instructions",
                "hinge count must not be inferred from door height alone",
            ]
        )
    if KitchenIntent.MOISTURE in intents or KitchenIntent.SINK_UNIT in intents:
        missing.extend(
            [
                "board moisture class (e.g. P2 vs humid-rated), sealed cut edges and exposure zone",
                "sink/dishwasher leak and steam/heat conditions",
            ]
        )
    if KitchenIntent.APPLIANCE in intents:
        missing.append(
            "exact appliance brand/model and manufacturer installation/ventilation clearances"
        )
    if (
        KitchenIntent.BASE_WALL_CABINET in intents
        or KitchenIntent.SINK_UNIT in intents
        or (
            "kitchen" in lower
            and any(word in lower for word in ("shelf", "regal", "boden", "p2", "p3"))
        )
    ):
        missing.extend(
            [
                "panel grade/thickness, span/support conditions and joint load path",
                "verified E/strength and creep criteria for the stated span",
                "no default claim that 18 mm is adequate without verified properties",
            ]
        )
    if refuses_cross_manufacturer(text):
        missing.append(
            "exact same-manufacturer part evidence; cross-manufacturer rating substitution is refused"
        )
    if refuses_din_compliance_claim(text):
        missing.append(
            "documented applicable tests and evidence; indexed DIN editions do not confirm compliance"
        )
    return missing


def metadata_links(session: Session, identifiers: list[str]) -> str:
    links = []
    for identifier in identifiers:
        try:
            version = session.get(KnowledgeSourceVersion, UUID(identifier))
        except ValueError:
            continue
        if version is not None:
            meta = version.attributes
            links.append(
                f"Metadata only: {meta['title']}; edition {meta.get('edition') or 'unknown'}; {meta.get('source_url') or 'no official URL'}. Clauses/property values have not been verified."
            )
    return "\n\n" + "\n\n".join(links) if links else ""


def render_answer(
    raw: str,
    session: Session,
    allowed_ids: list[str],
    owner_text: str,
    *,
    enabled: bool,
    metadata_ids: list[str] | None = None,
    report_ids: list[str] | None = None,
    calculators_enabled: bool = False,
    render_root=None,
) -> str:
    try:
        answer = EngineeringAnswer.model_validate_json(raw)
        if answer.report_ids and (
            not calculators_enabled
            or not set(map(str, answer.report_ids)).issubset(report_ids or [])
        ):
            raise ValueError("unsupported or unavailable report")
        if not set(answer.evidence_ids).issubset(allowed_ids) or any(
            item not in owner_text for item in answer.owner_assumptions
        ):
            raise ValueError("unsupported evidence/assumption")
        packets = (
            [
                resolve_evidence(session, evidence_id)
                for evidence_id in answer.evidence_ids
            ]
            if enabled
            else []
        )
        if any(packet is None for packet in packets):
            raise ValueError("ineligible evidence")
        properties = {
            prop["id"]: (packet, prop)
            for packet in packets
            for prop in packet["properties"]
        }
        if not set(answer.property_ids).issubset(properties):
            raise ValueError("unsupported property")
    except ValidationError, ValueError:
        return (
            INSUFFICIENT
            + " Invalid or unsupported engineering answer was rejected.\nMissing inputs: "
            + "; ".join(missing_inputs(owner_text))
            + metadata_links(session, metadata_ids or [])
        )
    lines = [
        INSUFFICIENT,
        "Preliminary design advice; a visual/design approval does not authorise installation.",
    ]
    if not enabled:
        lines.append("Engineering lookup is switched off or unavailable.")
    elif not packets:
        lines.append(
            "No applicable eligible supporting evidence was selected. Metadata links do not establish verification."
        )
    if answer.owner_assumptions:
        lines.append(
            "Owner-supplied assumptions (unverified): "
            + "; ".join(answer.owner_assumptions)
        )
    for packet in packets:
        metadata, block = packet["metadata"], packet["block"]
        citation = f"{metadata['title']}; edition {metadata.get('edition') or 'unknown'}; pages {block['pages'] or 'n/a'}; section {block.get('section') or 'unknown'}"
        lines.append(
            f"Evidence: {citation}; source verification: {metadata['verification_status']}; block: {block['verification_status']}."
        )
        lines.append(
            f"Product/model: {metadata.get('standard_or_model') or 'unknown'}; grade: {metadata.get('material_grade') or 'unknown'}; thickness: {metadata.get('thickness_mm') or 'unknown'} mm."
        )
        if metadata.get("source_url"):
            lines.append("Source: " + metadata["source_url"])
        if packet["historical"]:
            lines.append(
                "Historical edition; applicability to the current product is unresolved."
            )
    for property_id in answer.property_ids:
        packet, prop = properties[property_id]
        unit = {
            "E_MPa": "MPa",
            "bending_strength_MPa": "MPa",
            "density_kg_m3": "kg/m³",
            "capacity_N": "N",
            "thickness_mm": "mm",
            "allowable_span_mm": "mm",
        }[prop["kind"]]
        value = (
            prop["value"]
            if prop["value"] is not None
            else f"{prop['minimum']}–{prop['maximum']}"
            if prop["minimum"] is not None
            else "unknown"
        )
        lines.append(
            f"{prop['kind']}: {value} {unit}; {prop['verification_status']}; basis {prop['value_basis']}; {prop['page_section']}; conditions {json.dumps(prop['conditions'], ensure_ascii=False)}; original {prop['original_value'] if prop['original_value'] is not None else [prop['original_minimum'], prop['original_maximum']]} {prop['original_unit']}."
        )
    lines.append("Missing inputs/review: " + "; ".join(missing_inputs(owner_text)))
    # A model selecting one property cannot hide a conflict in the eligible
    # evidence returned this turn. Recheck rights for every competing record.
    current_packets = [
        packet
        for identifier in allowed_ids
        if enabled and (packet := resolve_evidence(session, identifier)) is not None
    ]
    for conflict in property_conflicts(current_packets):
        lines.append(
            "Conflict requiring resolution (code-detected; all values and conditions retained):\n"
            + json.dumps(conflict, ensure_ascii=False, indent=2)
        )
    lines.append(
        "Legal/standard applicability requires a project-specific check; indexed standards are not proof of conformity."
    )
    if answer.report_ids:
        from app.engineering.reports import report_copy

        for identifier in answer.report_ids:
            report = (
                report_copy(session, render_root, identifier, remote=True)
                if render_root is not None
                else None
            )
            if report is None or report.get("evidence_unavailable"):
                lines.append(
                    "Report evidence currently unavailable/ineligible; NOT VERIFIED."
                )
                continue
            lines.append(
                "Engineering report (code-generated, not installation approval):\n"
                + json.dumps(report, ensure_ascii=False, indent=2)
            )
    return "\n\n".join(lines) + metadata_links(session, metadata_ids or [])
