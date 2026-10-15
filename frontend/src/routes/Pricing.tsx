import { Navigate } from "react-router-dom";
import PriceList from "./PriceList";
import Remnants from "./Remnants";
import Snapshots from "./Snapshots";

/** The Pricing tab's views, in the sub-menu's order (studio-pricing-and-agent-settings-tabs). */
export const PRICING_VIEWS = [
  { id: "prices", label: "Prices", body: <PriceList /> },
  { id: "snapshots", label: "Snapshots", body: <Snapshots /> },
  { id: "remnants", label: "Remnants", body: <Remnants /> },
] as const;

/**
 * Prices, snapshots and remnants as the views of the Design Studio's Pricing tab, chosen from its
 * sub-menu. Only the chosen view is shown, at the width the Pricing Overview page gave it; an unknown
 * view opens Prices.
 */
export function PricingTab({ view = "prices" }: { view?: string }) {
  const chosen = PRICING_VIEWS.find((v) => v.id === view);
  if (!chosen) return <Navigate to="/studio/pricing/prices" replace />;
  return <div className="max-w-5xl space-y-4">{chosen.body}</div>;
}
