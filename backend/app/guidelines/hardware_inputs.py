"""The inputs a version's drilling list is calculated from, frozen into its folder.

`hardware_inputs.json` holds a copy of each data sheet the spec names (by hardware key), of the
calculator rules (the bracket rules and the pin, hinge and rail-support count rules) and of the
hardware catalog the generator draws from, so editing a sheet, a rule or the catalog later never
changes an existing version.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.blender.custom_build.derive import (
    CALCULATOR_CHECKS,
    HINGE_ID,
    SHELF_PIN_ID,
)
from app.blender.hardware_catalog import default_catalog
from app.guidelines.datasheets import sheet_for_key


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
        if rule.check in CALCULATOR_CHECKS:
            rules[rule.check] = {
                "rule_id": rule.id,
                "params": rule.params.model_dump(mode="json"),
                "source": {"publication": rule.source.publication, "section": rule.source.section, "quote": rule.source.quote},
            }
    return {"data_sheets": data_sheets, "rules": rules, "hardware_catalog": default_catalog().frozen()}


def _frozen_sheet(sheet: Any) -> dict[str, Any]:
    return {
        "kind": sheet.kind, "maker": sheet.maker, "model": sheet.model, "values": sheet.values,
        "source": sheet.citation, "source_kind": sheet.source_kind, "updated_at": sheet.updated_at.isoformat(),
    }
