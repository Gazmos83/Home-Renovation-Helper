import { useQuery } from "@tanstack/react-query";
import { Armchair, BookOpen, MessagesSquare, Package, Plus, Ruler, Settings, Tag } from "lucide-react";
import { Fragment, type ReactNode } from "react";
import { Link, Navigate, useLocation, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { isOpen, roomEntries } from "../lib/rooms";
import { cn } from "@/lib/utils";
import { Button, buttonVariants } from "@/components/ui/button";
import { Page } from "@/components/Page";
import { RailLabelsToggle, railClass, railItemClass, useRailLabels } from "@/components/chat/Rail";
import { LayoutMenu } from "@/components/studio/LayoutMenu";
import { SubMenu, type SubMenuItem } from "@/components/studio/SubMenu";
import { useStudioDialog } from "@/components/studio/useStudioDialog";
import ModelLibrary from "./ModelLibrary";
import Pieces from "./Pieces";
import { PRICING_VIEWS, PricingTab } from "./Pricing";
import Rooms from "./Rooms";
import Workspace, { useNewConversation } from "./Workspace";
import { AGENT_VIEWS, AgentSettingsTab } from "./admin/AgentSettings";
import { DesignKnowledgeTab, KNOWLEDGE_VIEWS } from "./admin/DesignKnowledge";

type Tab = {
  id: string;
  label: string;
  icon: typeof Armchair;
  /** Where the tab's addresses start; the developer tabs keep the developer route tree. */
  base: string;
  body: (view: string | undefined) => ReactNode;
  /** Shown only when the developer gate answers. */
  dev?: true;
};

const TABS: Tab[] = [
  { id: "workspace", label: "Workspace", icon: MessagesSquare, base: "/studio/workspace", body: (view) => <Workspace threadId={view} /> },
  { id: "pieces", label: "Pieces", icon: Armchair, base: "/studio/pieces", body: () => <Pieces /> },
  { id: "rooms", label: "Measured Rooms", icon: Ruler, base: "/studio/rooms", body: () => <Rooms /> },
  { id: "models", label: "Model Library", icon: Package, base: "/studio/models", body: () => <ModelLibrary /> },
  { id: "pricing", label: "Pricing", icon: Tag, base: "/studio/pricing", body: (view) => <PricingTab view={view} /> },
  {
    id: "agents",
    label: "AI & Agent Settings",
    icon: Settings,
    base: "/admin/agents",
    body: (view) => <AgentSettingsTab view={view} />,
    dev: true,
  },
  {
    id: "design-knowledge",
    label: "Design Knowledge",
    icon: BookOpen,
    base: "/admin/design-knowledge",
    body: (view) => <DesignKnowledgeTab view={view} />,
    dev: true,
  },
];

type Menu = { items: SubMenuItem[]; current: string | null; empty?: string };

/** The Workspace sub-menu's first entry: starts a conversation instead of opening one. */
function NewConversation({ layout }: { layout: "column" | "row" }) {
  const create = useNewConversation();
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={cn(layout === "column" ? "mb-1 w-full justify-start" : "shrink-0")}
      disabled={create.isPending}
      onClick={() => create.mutate()}
    >
      <Plus aria-hidden size={16} />
      New conversation
    </Button>
  );
}

/**
 * The chosen tab's sub-menu. Pieces and Measured Rooms list their items by name, each opening its dialog
 * like its tile does (studio-submenu-names); the lists are the tabs' own queries, so no extra request.
 * Model Library keeps its two views, "Upload model" highlighted while its dialog is open (studio-tile-grid).
 */
function useSubMenu(tab: string, view: string | undefined): Menu {
  const { search } = useLocation();
  const dialog = useStudioDialog(tab);
  const threads = useQuery({ queryKey: ["threads"], queryFn: api.threads, enabled: tab === "workspace" });
  const pieces = useQuery({ queryKey: ["pieces"], queryFn: api.pieces, enabled: tab === "pieces" });
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: api.rooms, enabled: tab === "rooms" });
  const compositions = useQuery({ queryKey: ["compositions"], queryFn: api.compositions, enabled: tab === "rooms" });
  const opening = { fromGrid: true };
  const to = (segments: string[]) => `/studio/${tab}/${segments.map(encodeURIComponent).join("/")}${search}`;

  if (tab === "workspace") {
    return {
      items: (threads.data ?? []).map((thread) => ({
        id: thread.thread_id,
        label: thread.title || "Untitled",
        to: `/studio/workspace/${thread.thread_id}`,
      })),
      current: view ?? null,
      empty: threads.data ? "No conversations yet" : undefined,
    };
  }
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
  if (tab === "pricing") {
    return {
      items: PRICING_VIEWS.map((v) => ({ id: v.id, label: v.label, to: `/studio/pricing/${v.id}` })),
      current: view ?? "prices",
    };
  }
  if (tab === "agents") {
    return {
      items: AGENT_VIEWS.map((v) => ({ id: v.id, label: v.label, to: `/admin/agents/${v.id}` })),
      current: view ?? "memory",
    };
  }
  if (tab === "design-knowledge") {
    return {
      items: KNOWLEDGE_VIEWS.map((v) => ({ id: v.id, label: v.label, to: `/admin/design-knowledge/${v.id}` })),
      current: view ?? "guidelines",
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
 * Pieces, measured rooms, the model library, pricing and, for the developer, AI & agent settings and
 * design knowledge as tabs of one page (combine-design-studio-pages, studio-pricing-and-agent-settings-tabs,
 * merge-guideline-pages), chosen from a rail at the screen's left edge that looks and hides its labels
 * like the conversation's. Each tab is a link with its own address. Beside the rail, the tab's sub-menu;
 * below 768 px it is a row above the content (studio-tile-grid, studio-submenu-names).
 *
 * `fixedTab` serves a developer tab from its own route tree (`/admin/agents/:tab`,
 * `/admin/design-knowledge/:tab`), where `:tab` names the view; on `/studio/:tab/*` the view is the first
 * path segment after the tab.
 */
export default function Studio({ dev = false, fixedTab }: { dev?: boolean; fixedTab?: string }) {
  const params = useParams();
  const tab = fixedTab ?? params.tab ?? "pieces";
  const view = fixedTab ? params.tab : params["*"]?.split("/")[0] || undefined;
  const [expanded, toggleLabels] = useRailLabels();
  const menu = useSubMenu(tab, view);
  const tabs = TABS.filter((t) => dev || !t.dev);
  const chosen = tabs.find((t) => t.id === tab);
  if (!chosen) return <Navigate to="/studio/pieces" replace />;
  const menuLabel =
    chosen.id === "workspace" ? "Conversations" : ["pieces", "rooms"].includes(chosen.id) ? chosen.label : `${chosen.label} views`;
  const lead = chosen.id === "workspace" ? (layout: "column" | "row") => <NewConversation layout={layout} /> : undefined;

  return (
    <div className="flex">
      <div className={railClass(expanded)}>
        <div role="tablist" aria-label="Design Studio" aria-orientation="vertical" className="flex flex-col gap-2">
          {tabs.map((t, index) => {
            const Icon = t.icon;
            return (
              <Fragment key={t.id}>
                {/* The developer tabs sit below a divider after the owner tabs. */}
                {t.dev && !tabs[index - 1]?.dev && <div aria-hidden data-rail-divider className="mx-1 h-px bg-border" />}
                <Link
                  to={t.base}
                  role="tab"
                  id={`studio-tab-${t.id}`}
                  aria-label={t.label}
                  aria-selected={t.id === chosen.id}
                  aria-controls="studio-panel"
                  className={cn(buttonVariants({ variant: "ghost", size: "sm" }), railItemClass(expanded), t.id === chosen.id && "bg-accent")}
                >
                  <Icon aria-hidden size={20} className="shrink-0" />
                  {/* "Measured Rooms", "Model Library" and "AI & Agent Settings" are as long as the shared rail is wide; they wrap within the row. */}
                  {expanded && (
                    <span aria-hidden className="min-w-0 whitespace-normal leading-tight">
                      {t.label}
                    </span>
                  )}
                </Link>
              </Fragment>
            );
          })}
        </div>
        <RailLabelsToggle expanded={expanded} onToggle={toggleLabels} />
      </div>
      <SubMenu label={menuLabel} {...menu} layout="column" lead={lead?.("column")} />
      <div className="min-w-0 flex-1">
        <Page wide>
          <div className="flex items-center justify-between gap-2">
            <h1>Design Studio</h1>
            {chosen.id === "workspace" && view && <LayoutMenu />}
          </div>
          <SubMenu label={menuLabel} {...menu} layout="row" lead={lead?.("row")} />
          <div role="tabpanel" id="studio-panel" aria-labelledby={`studio-tab-${chosen.id}`} className="space-y-4">
            {chosen.body(view)}
          </div>
        </Page>
      </div>
    </div>
  );
}
