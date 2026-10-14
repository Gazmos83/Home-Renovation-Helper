import { Activity, Brain, Gauge, Puzzle, Route, Server, ThumbsUp, Workflow as WorkflowIcon } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Page } from "@/components/Page";
import { RailLabelsToggle, railClass, railItemClass, useRailLabels } from "@/components/chat/Rail";
import ConversationCalls from "./ConversationCalls";
import Feedback from "./Feedback";
import Memory from "./Memory";
import Models from "./Models";
import Offload from "./Offload";
import Plugins from "./Plugins";
import Usage from "./Usage";
import Workflow from "./Workflow";

const TABS = [
  { id: "memory", label: "Agent Memory", icon: Brain, body: <Memory /> },
  { id: "workflow", label: "Agent Workflow", icon: WorkflowIcon, body: <Workflow /> },
  { id: "calls", label: "Agent Calls", icon: Activity, body: <ConversationCalls /> },
  { id: "offload", label: "Render Offload", icon: Server, body: <Offload /> },
  { id: "score", label: "Agent Score", icon: ThumbsUp, body: <Feedback /> },
  { id: "usage", label: "Token Usage", icon: Gauge, body: <Usage /> },
  { id: "plugins", label: "Plugins", icon: Puzzle, body: <Plugins /> },
  { id: "models", label: "Models and Routing", icon: Route, body: <Models /> },
] as const;

/**
 * The developer's agent and model pages as tabs of one page (combine-agent-settings-pages),
 * chosen from a rail at the screen's left edge that looks and hides its labels like the
 * conversation's and Pricing Overview's. Each tab is a link with its own address.
 */
export default function AgentSettings() {
  const { tab = "memory" } = useParams();
  const [expanded, toggleLabels] = useRailLabels();
  const chosen = TABS.find((t) => t.id === tab);
  if (!chosen) return <Navigate to="/admin/agents/memory" replace />;

  return (
    <div className="flex">
      <div className={railClass(expanded)}>
        <div role="tablist" aria-label="AI & Agent Settings" aria-orientation="vertical" className="flex flex-col gap-2">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <Link
                key={t.id}
                to={`/admin/agents/${t.id}`}
                role="tab"
                id={`agents-tab-${t.id}`}
                aria-label={t.label}
                aria-selected={t.id === chosen.id}
                aria-controls="agents-panel"
                className={cn(buttonVariants({ variant: "ghost", size: "sm" }), railItemClass(expanded), t.id === chosen.id && "bg-accent")}
              >
                <Icon aria-hidden size={20} className="shrink-0" />
                {/* "Models and Routing" is longer than the shared rail is wide; it wraps within the row. */}
                {expanded && (
                  <span aria-hidden className="min-w-0 whitespace-normal leading-tight">
                    {t.label}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
        <RailLabelsToggle expanded={expanded} onToggle={toggleLabels} />
      </div>
      <div className="min-w-0 flex-1">
        <Page>
          <h1>AI &amp; Agent Settings</h1>
          <div role="tabpanel" id="agents-panel" aria-labelledby={`agents-tab-${chosen.id}`} className="space-y-4">
            {chosen.body}
          </div>
        </Page>
      </div>
    </div>
  );
}
