import { useQuery } from "@tanstack/react-query";
import { api, type WorkflowMap } from "../../lib/api";
import { ROLE_LABELS } from "@/components/chat/roles";

const BOX_W = 150;
const BOX_H = 44;
const GAP = 16;
const ROW_Y = { homeowner: 10, foreman: 100, agents: 200 };

function label(name: string): string {
  return ROLE_LABELS[name] ?? name;
}

function Diagram({ map }: { map: WorkflowMap }) {
  const agents = map.nodes.filter((node) => node.name !== map.entry);
  const width = Math.max(agents.length * (BOX_W + GAP) + GAP, 2 * BOX_W);
  const centre = width / 2;
  const foreman = map.nodes.find((node) => node.name === map.entry);
  const handsTo = new Set(map.handoffs.filter((edge) => edge.from === map.entry).map((edge) => edge.to));
  const toolRows = Math.max(0, ...agents.map((agent) => agent.tools.length));
  const height = ROW_Y.agents + BOX_H + 24 + toolRows * 18 + 10;
  return (
    <svg
      role="img"
      aria-label="Agent workflow map"
      viewBox={`0 0 ${width} ${height}`}
      className="w-full max-w-5xl text-foreground"
    >
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
        </marker>
      </defs>
      <g fill="none" stroke="currentColor">
        <rect x={centre - BOX_W / 2} y={ROW_Y.homeowner} width={BOX_W} height={BOX_H} rx={8} />
        <rect x={centre - BOX_W / 2} y={ROW_Y.foreman} width={BOX_W} height={BOX_H} rx={8} />
        <line
          x1={centre}
          y1={ROW_Y.homeowner + BOX_H}
          x2={centre}
          y2={ROW_Y.foreman}
          markerEnd="url(#arrow)"
        />
      </g>
      <text x={centre} y={ROW_Y.homeowner + 27} textAnchor="middle" fontSize={13} fill="currentColor">
        Homeowner
      </text>
      <text x={centre} y={ROW_Y.foreman + 19} textAnchor="middle" fontSize={13} fill="currentColor">
        Foreman
      </text>
      <text x={centre} y={ROW_Y.foreman + 35} textAnchor="middle" fontSize={10} fill="currentColor">
        {foreman?.model}
      </text>
      {agents.map((agent, index) => {
        const x = GAP + index * (BOX_W + GAP);
        return (
          <g key={agent.name}>
            {handsTo.has(agent.name) && (
              <line
                x1={centre}
                y1={ROW_Y.foreman + BOX_H}
                x2={x + BOX_W / 2}
                y2={ROW_Y.agents}
                stroke="currentColor"
                markerEnd="url(#arrow)"
              />
            )}
            <rect x={x} y={ROW_Y.agents} width={BOX_W} height={BOX_H} rx={8} fill="none" stroke="currentColor" />
            <text x={x + BOX_W / 2} y={ROW_Y.agents + 19} textAnchor="middle" fontSize={13} fill="currentColor">
              {label(agent.name)}
            </text>
            <text x={x + BOX_W / 2} y={ROW_Y.agents + 35} textAnchor="middle" fontSize={9} fill="currentColor">
              {agent.model}
            </text>
            {agent.tools.map((tool, row) => (
              <text
                key={tool.name}
                x={x + 4}
                y={ROW_Y.agents + BOX_H + 18 + row * 18}
                fontSize={10}
                fill="currentColor"
                opacity={tool.enabled ? 1 : 0.45}
              >
                {tool.name}
                {tool.confirmation ? " ✓?" : ""}
                {tool.render_guard ? " ⛨" : ""}
                {tool.enabled ? "" : " (off)"}
              </text>
            ))}
          </g>
        );
      })}
    </svg>
  );
}

/** How the agents hand work to each other, read from the running graph (dev-panel-insights). */
export default function Workflow() {
  const map = useQuery({ queryKey: ["admin-workflow"], queryFn: api.workflow });
  if (map.error instanceof Error) return <>The workflow map is not available: {map.error.message}</>;
  if (!map.data) return <>Loading…</>;
  return (
    <>
      <p className="text-sm text-muted-foreground">
        The homeowner talks only to the Foreman, which hands each turn to one specialist. ✓? waits for the owner's
        confirmation; ⛨ passes the render guard; (off) is disabled globally.
      </p>
      <Diagram map={map.data} />
      <h2>Agents</h2>
      <ul className="space-y-2">
        {map.data.nodes.map((node) => (
          <li key={node.name}>
            <strong>{label(node.name)}</strong> — {node.model}
            {node.tools.length > 0 && (
              <ul className="ml-4 list-disc">
                {node.tools.map((tool) => (
                  <li key={tool.name}>
                    {tool.name} ({tool.plugin})
                    {tool.confirmation && ", waits for confirmation"}
                    {tool.render_guard && ", passes the render guard"}
                    {!tool.enabled && ", disabled"}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
