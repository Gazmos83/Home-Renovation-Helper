import { useQuery } from "@tanstack/react-query";
import { Armchair, Package, Ruler } from "lucide-react";
import { Link, Navigate, useLocation, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { isOpen, roomEntries } from "../lib/rooms";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Page } from "@/components/Page";
import { RailLabelsToggle, railClass, railItemClass, useRailLabels } from "@/components/chat/Rail";
import { SubMenu, type SubMenuItem } from "@/components/studio/SubMenu";
import { useStudioDialog } from "@/components/studio/useStudioDialog";
import ModelLibrary from "./ModelLibrary";
import Pieces from "./Pieces";
import Rooms from "./Rooms";

const TABS = [
  { id: "pieces", label: "Pieces", icon: Armchair, body: <Pieces /> },
  { id: "rooms", label: "Measured Rooms", icon: Ruler, body: <Rooms /> },
  { id: "models", label: "Model Library", icon: Package, body: <ModelLibrary /> },
] as const;

type Menu = { items: SubMenuItem[]; current: string | null; empty?: string };

/**
 * The chosen tab's sub-menu. Pieces and Measured Rooms list their items by name, each opening its dialog
 * like its tile does (studio-submenu-names); the lists are the tabs' own queries, so no extra request.
 * Model Library keeps its two views, "Upload model" highlighted while its dialog is open (studio-tile-grid).
 */
function useSubMenu(tab: string): Menu {
  const { search } = useLocation();
  const dialog = useStudioDialog(tab);
  const pieces = useQuery({ queryKey: ["pieces"], queryFn: api.pieces, enabled: tab === "pieces" });
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: api.rooms, enabled: tab === "rooms" });
  const compositions = useQuery({ queryKey: ["compositions"], queryFn: api.compositions, enabled: tab === "rooms" });
  const opening = { fromGrid: true };
  const to = (segments: string[]) => `/studio/${tab}/${segments.map(encodeURIComponent).join("/")}${search}`;

  if (tab === "pieces") {
    return {
      items: (pieces.data ?? []).map((piece) => ({
        id: piece.package_id,
        label: piece.package_id,
        to: to([piece.package_id]),
        state: opening,
      })),
      current: dialog.segments.length === 1 ? dialog.segments[0] : null,
      empty: pieces.data ? "No pieces yet" : undefined,
    };
  }
  if (tab === "rooms") {
    const entries = roomEntries(rooms.data, compositions.data, Boolean(rooms.data || rooms.error));
    const open = entries.find((entry) => isOpen(entry, dialog.segments));
    return {
      items: entries.map((entry) => ({
        id: entry.segments.join("/"),
        label: entry.name,
        to: to(entry.segments),
        state: opening,
      })),
      current: open ? open.segments.join("/") : null,
      empty: rooms.data ? "No rooms yet" : undefined,
    };
  }
  return {
    items: [
      { id: "all", label: "Uploaded models", to: dialog.grid },
      { id: "upload", label: "Upload model", to: to(["upload"]), state: opening },
    ],
    current: dialog.segments[0] === "upload" ? "upload" : "all",
  };
}

/**
 * Pieces, measured rooms and the model library as tabs of one page (combine-design-studio-pages),
 * chosen from a rail at the screen's left edge that looks and hides its labels like the
 * conversation's and Pricing Overview's. Each tab is a link with its own address. Beside the rail, the
 * tab's sub-menu; below 768 px it is a row above the content (studio-tile-grid, studio-submenu-names).
 */
export default function Studio() {
  const { tab = "pieces" } = useParams();
  const [expanded, toggleLabels] = useRailLabels();
  const menu = useSubMenu(tab);
  const chosen = TABS.find((t) => t.id === tab);
  if (!chosen) return <Navigate to="/studio/pieces" replace />;
  const menuLabel = chosen.id === "models" ? `${chosen.label} views` : chosen.label;

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
      <SubMenu label={menuLabel} {...menu} layout="column" />
      <div className="min-w-0 flex-1">
        <Page wide>
          <h1>Design Studio</h1>
          <SubMenu label={menuLabel} {...menu} layout="row" />
          <div role="tabpanel" id="studio-panel" aria-labelledby={`studio-tab-${chosen.id}`} className="space-y-4">
            {chosen.body}
          </div>
        </Page>
      </div>
    </div>
  );
}
