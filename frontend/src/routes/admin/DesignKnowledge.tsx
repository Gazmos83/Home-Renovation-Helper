import { Navigate } from "react-router-dom";
import Guidelines from "./Guidelines";
import Knowledge from "./Knowledge";
import Rules from "./Rules";

/** The Design Knowledge tab's views, in the sub-menu's order (merge-guideline-pages). */
export const KNOWLEDGE_VIEWS = [
  { id: "guidelines", label: "Guidelines", body: <Guidelines /> },
  { id: "engineering", label: "Engineering Knowledge", body: <Knowledge /> },
  { id: "rules", label: "Design Rules", body: <Rules /> },
] as const;

/**
 * The developer's guidelines, engineering knowledge and design rules pages as the views of the
 * Design Studio's developer-only Design Knowledge tab, kept on the `/admin/design-knowledge/<view>`
 * route tree. Only the chosen view is shown; an unknown view opens Guidelines.
 */
export function DesignKnowledgeTab({ view = "guidelines" }: { view?: string }) {
  const chosen = KNOWLEDGE_VIEWS.find((v) => v.id === view);
  if (!chosen) return <Navigate to="/admin/design-knowledge/guidelines" replace />;
  return <div className="max-w-5xl space-y-4">{chosen.body}</div>;
}
