import { Navigate } from "react-router-dom";
import ConversationCalls from "./ConversationCalls";
import Feedback from "./Feedback";
import Memory from "./Memory";
import Models from "./Models";
import Offload from "./Offload";
import Plugins from "./Plugins";
import Usage from "./Usage";
import Workflow from "./Workflow";

/** The AI & Agent Settings tab's views, in the sub-menu's order (studio-pricing-and-agent-settings-tabs). */
export const AGENT_VIEWS = [
  { id: "memory", label: "Agent Memory", body: <Memory /> },
  { id: "workflow", label: "Agent Workflow", body: <Workflow /> },
  { id: "calls", label: "Agent Calls", body: <ConversationCalls /> },
  { id: "offload", label: "Render Offload", body: <Offload /> },
  { id: "score", label: "Agent Score", body: <Feedback /> },
  { id: "usage", label: "Token Usage", body: <Usage /> },
  { id: "plugins", label: "Plugins", body: <Plugins /> },
  { id: "models", label: "Models and Routing", body: <Models /> },
] as const;

/**
 * The developer's agent and model pages as the views of the Design Studio's developer-only
 * AI & Agent Settings tab, kept on the `/admin/agents/<view>` route tree. Only the chosen view is
 * shown, at the width the AI & Agent Settings page gave it; an unknown view opens Agent Memory.
 */
export function AgentSettingsTab({ view = "memory" }: { view?: string }) {
  const chosen = AGENT_VIEWS.find((v) => v.id === view);
  if (!chosen) return <Navigate to="/admin/agents/memory" replace />;
  return <div className="max-w-5xl space-y-4">{chosen.body}</div>;
}
