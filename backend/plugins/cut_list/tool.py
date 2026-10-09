"""`cut_list` (Designer): a version's derived parts and hardware, no process.

Read-only and pure: the rows are derived from the version's stored document by
the rule table, so no Blender process starts.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.base import AgentTool, ToolContext, parse_args
from app.agent.tools.shared import read_input, version_folder
from app.blender import storage
from app.blender.custom_build import derive as custom_derive


class CutListArgs(BaseModel):
    package_id: str
    version: int | None = Field(default=None, description="a version number; the latest when left out")


def run(arguments: dict[str, Any], ctx: ToolContext) -> str:
    args, problem = parse_args(CutListArgs, arguments)
    if args is None:
        return problem
    folder, number, problem = version_folder(ctx.deps, args.package_id, args.version)
    if folder is None:
        return problem
    document = read_input(folder)
    if document is None:
        return f"version {number} of {args.package_id!r} has no readable document"
    inputs = storage.read_hardware_inputs(folder)
    parts, hardware, _assembly = custom_derive.derive(document, inputs)
    lines = [f"Cut list for {args.package_id} version {number}:"]
    for part in parts:
        lines.append(
            f"- {part['id']}: {part['qty']} × {part['l']} × {part['w']} × {part['t']} mm, "
            f"{part['material']}"
        )
    lines.append(f"Parts: {len(parts)} rows, {sum(p['qty'] for p in parts)} pieces in all")
    lines.append("Hardware:")
    for item in hardware:
        lines.append(f"- {item['item']} ({item['id']}): {item['qty'] if item['qty'] != '' else 'no quantity'}")
    counted = [h["qty"] for h in hardware if h["qty"] != ""]
    lines.append(f"Hardware: {len(hardware)} lines, {sum(counted)} items in all")
    unknown = [h["id"] for h in hardware if h["qty"] == ""]
    if unknown:
        lines.append(f"Hardware with no quantity (a value is missing): {', '.join(unknown)}")
    lines += custom_derive.drilling_lines(None if inputs is None else custom_derive.drilling(document, inputs))
    return "\n".join(lines)


cut_list = AgentTool(
    name="cut_list",
    description="List a version's derived cut-list parts and hardware with totals. Starts no process.",
    schema=CutListArgs,
    run=run,
)
