"""`price_cut_list` and `manage_remnants` (Researcher). Filled in by pricing-researcher."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.base import AgentTool, ToolContext, parse_args

UNAVAILABLE = (
    "this pricing tool is not available yet: the price list has not been loaded. "
    "Tell the owner this cannot be done yet and do not invent a price."
)


class PriceCutListArgs(BaseModel):
    package_id: str
    version: int | None = Field(default=None, description="a version number; the latest when left out")


class ManageRemnantsArgs(BaseModel):
    action: str = Field(description="'add' or 'remove'")
    material: str | None = None
    length_mm: float | None = None
    width_mm: float | None = None
    thickness_mm: float | None = None
    remnant_id: str | None = None


def run_price(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(PriceCutListArgs, arguments)
    if args is None:
        return problem
    return UNAVAILABLE


def run_remnants(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(ManageRemnantsArgs, arguments)
    if args is None:
        return problem
    return UNAVAILABLE


price_cut_list = AgentTool(
    name="price_cut_list",
    description="Price a version's cut list from the toom price list. Never guess a price.",
    schema=PriceCutListArgs,
    run=run_price,
)

manage_remnants = AgentTool(
    name="manage_remnants",
    description="Add or remove a remnant on the rack used when pricing a cut list.",
    schema=ManageRemnantsArgs,
    run=run_remnants,
)
