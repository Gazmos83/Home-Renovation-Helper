"""Developer panel: the agent workflow map (dev-panel-insights).

Nodes and hand-offs are read from the running Foreman graph, each agent's model
from the routing in force, and its tools from the loaded plugin manifests with
their global state. Only the two markers the graph cannot show are written down
here, in `GUARDED_TOOLS`: the tools whose renders pass the render guard. A tool
with a preview waits for the owner's confirmation (`interrupt()`), which the
tool itself declares. A test holds every listed tool against the loaded plugins.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.gate import require_dev
from app.plugins.enablement import global_enabled

router = APIRouter(prefix="/admin/workflow", tags=["admin"], dependencies=[Depends(require_dev)])

# The tools whose renders pass the render guard (CLAUDE.md §6); every other render-free tool does not.
GUARDED_TOOLS: Final = frozenset({"render_turntable", "render_detail"})
HOMEOWNER: Final = "homeowner"
INTERNAL_NODES: Final = frozenset({"__start__", "__end__", "load_house"})


@router.get("")
def workflow(request: Request) -> dict[str, Any]:
    graph = request.app.state.graph
    if graph is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"failure_class": "graph_unavailable", "reason": "the agent graph is not running"},
        )
    drawn = graph.get_graph()
    agents = [name for name in drawn.nodes if name not in INTERNAL_NODES]
    handoffs = [
        {"from": edge.source, "to": edge.target}
        for edge in drawn.edges
        if edge.source in agents and edge.target in agents
    ]
    routing = request.app.state.routing
    plugins = request.app.state.plugins
    with Session(request.app.state.engine) as session:
        nodes = []
        for name in agents:
            tools = []
            for plugin in plugins.by_name.values():
                if name not in plugin.agents:
                    continue
                enabled = global_enabled(session, plugins, plugin.name)
                for tool_name in plugin.manifest.tools:
                    tool = plugin.tools.get(tool_name) if plugin.tools else None
                    tools.append(
                        {
                            "name": tool_name,
                            "plugin": plugin.name,
                            "enabled": enabled,
                            "confirmation": bool(tool is not None and tool.gated),
                            "render_guard": tool_name in GUARDED_TOOLS,
                        }
                    )
            nodes.append({"name": name, "model": routing.model_for(name), "tools": tools})
    return {
        "homeowner": HOMEOWNER,
        "entry": "foreman",
        "nodes": nodes,
        "handoffs": [{"from": HOMEOWNER, "to": "foreman"}, *handoffs],
    }
