"""The inputs a version's drilling list is calculated from, frozen into its folder.

`hardware_inputs.json` holds a copy of each data sheet the spec names (by hardware key) and of the
two bracket rules, so editing a sheet or a rule later never changes an existing version.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.blender.custom_build.derive import (
    BRACKET_COUNT_CHECK,
    BRACKET_SPACING_CHECK,
    HINGE_ID,
    SHELF_PIN_ID,
)
from app.guidelines.datasheets import sheet_for_key

BRACKET_CHECKS = (BRACKET_COUNT_CHECK, BRACKET_SPACING_CHECK)


def named_keys(spec: Mapping[str, Any]) -> tuple[list[str], bool]:
    """(the hinge and shelf-pin keys the spec names, in order; whether it has wall shelves)."""
    keys: list[str] = []
    for module in spec.get("modules") or []:
        if module.get("adjustable_shelves"):
            keys.append(module.get("shelf_pin") or SHELF_PIN_ID)
        keys.extend((front.get("hinge") or HINGE_ID) for front in module.get("fronts") or [] if front["type"] == "door")
    return list(dict.fromkeys(keys)), bool(spec.get("wall_shelves"))


def freeze_inputs(session: Session, design_rules: Iterable[Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    keys, _ = named_keys(spec)
    data_sheets: dict[str, Any] = {}
    for key in keys:
        sheet = sheet_for_key(session, key)
        if sheet is None:
            continue
        data_sheets[key] = _frozen_sheet(sheet)
        plate = (sheet.values or {}).get("plate_item")
        if plate and (plate_sheet := sheet_for_key(session, plate)) is not None:
            data_sheets[plate] = _frozen_sheet(plate_sheet)
    rules: dict[str, Any] = {}
    for rule in design_rules:
        if rule.check in BRACKET_CHECKS:
            rules[rule.check] = {
                "rule_id": rule.id,
                "params": rule.params.model_dump(mode="json"),
                "source": {"publication": rule.source.publication, "section": rule.source.section, "quote": rule.source.quote},
            }
    return {"data_sheets": data_sheets, "rules": rules}


def _frozen_sheet(sheet: Any) -> dict[str, Any]:
    return {
        "kind": sheet.kind, "maker": sheet.maker, "model": sheet.model, "values": sheet.values,
        "source": sheet.citation, "source_kind": sheet.source_kind, "updated_at": sheet.updated_at.isoformat(),
    }
