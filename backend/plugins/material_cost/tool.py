"""`price_cut_list` and `manage_remnants` (Researcher).

Pricing reads a version's derived cut list and writes an immutable record: every
line without a price is listed by name and marks it incomplete, never guessed.
The rack changes only on the owner's `yes`; listing is free.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.tools.base import (
    AgentTool,
    Confirmation,
    ToolContext,
    ToolOutput,
    parse_args,
)
from app.agent.tools.shared import NOT_APPROVED, version_folder
from app.pricing import remnants
from app.pricing.errors import NotFound, Refused
from app.pricing.pricing import describe_pricing
from app.pricing.pricing import price_cut_list as price
from app.pricing.store import UnknownStore


class PriceCutListArgs(BaseModel):
    package_id: str
    version: int | None = Field(default=None, description="a version number; the latest when left out")
    delivery_key: str | None = Field(default=None, description="a delivery option's key, e.g. delivery:10km")
    cut_charge_mode: Literal["shared", "per_cut"] | None = Field(
        default=None, description="'shared' (the workshop's own saw) or 'per_cut' (the store's tariff); ask the owner when open"
    )


class ManageRemnantsArgs(BaseModel):
    action: Literal["list", "add", "remove"]
    material_key: str | None = Field(default=None, description="a price-list material key, e.g. panel:oak-veneer-birch:18")
    length_mm: int | None = None
    width_mm: int | None = None
    grain_axis: Literal["length", "width"] | None = None
    quantity: int = 1
    remnant_id: str | None = Field(default=None, description="the id of a rack row, for remove")


def euros(cents: int | None) -> str:
    return "unpriced" if cents is None else f"{cents // 100},{cents % 100:02d} EUR"


def summarise(row_dict: dict[str, Any]) -> str:
    result = row_dict["result"]
    heading = (
        f"Pricing {row_dict['id']} for {row_dict['package_id']} version {row_dict['version']} "
        f"(home store {row_dict['store_key']}, {row_dict['computed_at'][:10]}):"
    )
    parts = (
        f"- materials {euros(row_dict['materials_cents'])}; hardware {euros(row_dict['hardware_cents'])}; "
        f"edge band {euros(row_dict['banding_cents'])}; cutting {euros(row_dict['cut_service_cents'])}; "
        f"delivery {euros(row_dict['delivery_cents'])}"
    )
    lines = [heading, parts, f"- total {euros(row_dict['total_cents'])}"]
    for key, material in result["materials"].items():
        if "sheet_count" in material:
            lines.append(
                f"- {key}: {material['sheet_count']} sheet(s) at {material['utilisation_percent']:g}% use, "
                f"{euros(material['cost_cents'])}"
            )
    if result.get("cut_charge_choice_open"):
        lines.append("- the cut charge is open: ask whether the fee is 'shared' or 'per_cut'")
    if row_dict["custom_count"] or row_dict["undetermined_count"] or row_dict["review_count"]:
        lines.append(
            f"- cuts: {row_dict['custom_count']} need custom work, {row_dict['undetermined_count']} undetermined, "
            f"{row_dict['review_count']} to review"
        )
    if row_dict["complete"]:
        lines.append("- the pricing is complete")
    else:
        lines.append("- the pricing is INCOMPLETE; these lines have no price and none is guessed:")
        for item in result["unpriced"]:
            what = item.get("part_id") or item.get("id") or item.get("material_key") or item.get("key") or item["kind"]
            lines.append(f"  - {item['kind']} {what}: {item['reason']}")
        for item in result["unfitting"]:
            lines.append(f"  - part {item['part_id']} does not fit any {item['material_key']} sheet")
    return "\n".join(lines)


def run_price(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(PriceCutListArgs, arguments)
    if args is None:
        return problem
    folder, number, problem = version_folder(ctx.deps, args.package_id, args.version)
    if folder is None or number is None:
        return problem
    settings = ctx.deps.settings
    with ctx.deps.session() as session:
        try:
            row = price(
                session, settings.render_root, args.package_id, number, settings,
                delivery_key=args.delivery_key, cut_charge_mode=args.cut_charge_mode,
            )
        except UnknownStore as error:
            return f"{error}. Tell the owner the home store has to be captured before a cut list can be priced."
        except Refused as error:
            return f"the cut list cannot be priced: {error}"
        session.commit()
        return summarise(describe_pricing(row))


def _rack_line(row) -> str:
    return (
        f"- {row.id}: {row.quantity} × {row.material_key}, {row.length_mm} × {row.width_mm} mm, "
        f"grain along its {row.grain_axis}"
    )


def preview_remnants(arguments: dict[str, Any], ctx: ToolContext) -> Confirmation | str | None:
    args, problem = parse_args(ManageRemnantsArgs, arguments)
    if args is None:
        return problem
    if args.action == "list":
        return None
    if args.action == "add":
        missing = [
            name for name in ("material_key", "length_mm", "width_mm", "grain_axis")
            if getattr(args, name) is None
        ]
        if missing:
            return f"to add a remnant give its {', '.join(missing)}"
        try:
            remnants.check_new(args.material_key, args.length_mm, args.width_mm, args.grain_axis, args.quantity)
        except Refused as error:
            return str(error)
        return Confirmation(
            subject="remnant",
            summary=(
                f"Add to the remnant rack: {args.quantity} × {args.material_key}, "
                f"{args.length_mm} × {args.width_mm} mm, grain along its {args.grain_axis}"
            ),
            proposal={"action": "add", **args.model_dump(exclude={"action", "remnant_id"})},
        )
    if not args.remnant_id:
        return "to remove a remnant give its remnant_id (list the rack first)"
    with ctx.deps.session() as session:
        found = next((r for r in remnants.list_remnants(session) if str(r.id) == args.remnant_id), None)
    if found is None:
        return f"there is no remnant {args.remnant_id} on the rack"
    return Confirmation(
        subject="remnant",
        summary=f"Remove from the remnant rack: {found.quantity} × {found.material_key}, {found.length_mm} × {found.width_mm} mm",
        proposal={"action": "remove", "remnant_id": args.remnant_id},
    )


def run_remnants(arguments: dict[str, Any], ctx: ToolContext) -> ToolOutput | str:
    args, problem = parse_args(ManageRemnantsArgs, arguments)
    if args is None:
        return problem
    with ctx.deps.session() as session:
        if args.action == "list":
            rack = remnants.list_remnants(session)
            return "The remnant rack:\n" + "\n".join(_rack_line(r) for r in rack) if rack else "The remnant rack is empty."
        if not ctx.approved:
            return NOT_APPROVED
        try:
            if args.action == "add":
                row = remnants.add_remnant(
                    session, material_key=args.material_key or "", length_mm=args.length_mm or 0,
                    width_mm=args.width_mm or 0, grain_axis=args.grain_axis or "", quantity=args.quantity,
                )
                session.commit()
                return f"Added to the rack: {args.quantity} × {row.material_key} ({row.id})."
            from uuid import UUID

            remnants.remove_remnant(session, UUID(args.remnant_id or ""))
            session.commit()
            return "Removed from the rack."
        except (Refused, NotFound, ValueError) as error:
            session.rollback()
            return f"the rack was not changed: {error}"


price_cut_list = AgentTool(
    name="price_cut_list",
    description=(
        "Price a piece version's cut list and hardware from the price list and the home store. "
        "Reports totals in euros and lists every line without a price; never guess a price. "
        "If the cut charge is open, ask the owner whether it is 'shared' or 'per_cut'."
    ),
    schema=PriceCutListArgs,
    run=run_price,
)

manage_remnants = AgentTool(
    name="manage_remnants",
    description=(
        "List the workshop remnant rack, or add or remove a remnant. Adding and removing wait for "
        "the owner's yes; pricing uses the rack but never changes it."
    ),
    schema=ManageRemnantsArgs,
    run=run_remnants,
    preview=preview_remnants,
)
