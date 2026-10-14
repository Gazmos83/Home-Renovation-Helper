import { Camera, Layers, Tag } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Page } from "@/components/Page";
import { RailLabelsToggle, railClass, railItemClass, useRailLabels } from "@/components/chat/Rail";
import PriceList from "./PriceList";
import Remnants from "./Remnants";
import Snapshots from "./Snapshots";

const TABS = [
  { id: "prices", label: "Prices", icon: Tag, body: <PriceList /> },
  { id: "snapshots", label: "Snapshots", icon: Camera, body: <Snapshots /> },
  { id: "remnants", label: "Remnants", icon: Layers, body: <Remnants /> },
] as const;

/**
 * Prices, snapshots and remnants as tabs of one page (combine-pricing-pages), chosen from a
 * rail at the screen's left edge that looks and hides its labels like the conversation's.
 * Each tab is a link with its own address.
 */
export default function Pricing() {
  const { tab = "prices" } = useParams();
  const [expanded, toggleLabels] = useRailLabels();
  const chosen = TABS.find((t) => t.id === tab);
  if (!chosen) return <Navigate to="/pricing/prices" replace />;

  return (
    <div className="flex">
      <div className={railClass(expanded)}>
        <div role="tablist" aria-label="Pricing Overview" aria-orientation="vertical" className="flex flex-col gap-2">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <Link
                key={t.id}
                to={`/pricing/${t.id}`}
                role="tab"
                id={`pricing-tab-${t.id}`}
                aria-label={t.label}
                aria-selected={t.id === chosen.id}
                aria-controls="pricing-panel"
                className={cn(buttonVariants({ variant: "ghost", size: "sm" }), railItemClass(expanded), t.id === chosen.id && "bg-accent")}
              >
                <Icon aria-hidden size={20} className="shrink-0" />
                {expanded && <span aria-hidden>{t.label}</span>}
              </Link>
            );
          })}
        </div>
        <RailLabelsToggle expanded={expanded} onToggle={toggleLabels} />
      </div>
      <div className="min-w-0 flex-1">
        <Page>
          <h1>Pricing Overview</h1>
          <div role="tabpanel" id="pricing-panel" aria-labelledby={`pricing-tab-${chosen.id}`} className="space-y-4">
            {chosen.body}
          </div>
        </Page>
      </div>
    </div>
  );
}
