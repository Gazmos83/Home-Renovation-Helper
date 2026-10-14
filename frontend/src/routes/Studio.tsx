import { Armchair, Package, Ruler } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Page } from "@/components/Page";
import { RailLabelsToggle, railClass, railItemClass, useRailLabels } from "@/components/chat/Rail";
import ModelLibrary from "./ModelLibrary";
import Pieces from "./Pieces";
import Rooms from "./Rooms";

const TABS = [
  { id: "pieces", label: "Pieces", icon: Armchair, body: <Pieces /> },
  { id: "rooms", label: "Measured Rooms", icon: Ruler, body: <Rooms /> },
  { id: "models", label: "Model Library", icon: Package, body: <ModelLibrary /> },
] as const;

/**
 * Pieces, measured rooms and the model library as tabs of one page (combine-design-studio-pages),
 * chosen from a rail at the screen's left edge that looks and hides its labels like the
 * conversation's and Pricing Overview's. Each tab is a link with its own address.
 */
export default function Studio() {
  const { tab = "pieces" } = useParams();
  const [expanded, toggleLabels] = useRailLabels();
  const chosen = TABS.find((t) => t.id === tab);
  if (!chosen) return <Navigate to="/studio/pieces" replace />;

  return (
    <div className="flex">
      <div className={railClass(expanded)}>
        <div role="tablist" aria-label="Design Studio" aria-orientation="vertical" className="flex flex-col gap-2">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <Link
                key={t.id}
                to={`/studio/${t.id}`}
                role="tab"
                id={`studio-tab-${t.id}`}
                aria-label={t.label}
                aria-selected={t.id === chosen.id}
                aria-controls="studio-panel"
                className={cn(buttonVariants({ variant: "ghost", size: "sm" }), railItemClass(expanded), t.id === chosen.id && "bg-accent")}
              >
                <Icon aria-hidden size={20} className="shrink-0" />
                {/* "Measured Rooms" and "Model Library" are as long as the shared rail is wide; they wrap within the row. */}
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
          <h1>Design Studio</h1>
          <div role="tabpanel" id="studio-panel" aria-labelledby={`studio-tab-${chosen.id}`} className="space-y-4">
            {chosen.body}
          </div>
        </Page>
      </div>
    </div>
  );
}
