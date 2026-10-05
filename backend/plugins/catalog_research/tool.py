"""Catalogue lookup tools (Researcher). Filled in by pricing-researcher."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.base import AgentTool, parse_args

UNAVAILABLE = (
    "this catalogue lookup is not available yet. "
    "Tell the owner the information cannot be fetched and do not invent it."
)


class SearchCatalogArgs(BaseModel):
    query: str = Field(description="what to look up in the toom catalogue")


class CheckListingArgs(BaseModel):
    url: str = Field(description="a toom product page URL")


class CompareProductsArgs(BaseModel):
    query: str = Field(description="the products or materials to compare")


def _run(model: type[BaseModel], arguments: dict[str, Any]) -> str:
    args, problem = parse_args(model, arguments)
    if args is None:
        return problem
    return UNAVAILABLE


search_catalog_knowledge = AgentTool(
    name="search_catalog_knowledge",
    description="Search the ingested toom catalogue for product facts.",
    schema=SearchCatalogArgs,
    run=lambda arguments, ctx: _run(SearchCatalogArgs, arguments),
)

check_live_listing = AgentTool(
    name="check_live_listing",
    description="Fetch a toom product page and return its current listing.",
    schema=CheckListingArgs,
    run=lambda arguments, ctx: _run(CheckListingArgs, arguments),
)

compare_products = AgentTool(
    name="compare_products",
    description="Compare products from the catalogue on size, material and price.",
    schema=CompareProductsArgs,
    run=lambda arguments, ctx: _run(CompareProductsArgs, arguments),
)
