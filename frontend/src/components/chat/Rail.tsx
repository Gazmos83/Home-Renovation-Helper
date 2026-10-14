import { Box, ChevronsLeft, ChevronsRight, ClipboardList, DoorOpen, NotebookPen, Ruler, Wrench, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type Panel = { id: string; label: string; icon: "tools" | "brief" | "project" | "piece" | "room" | "notes"; content: ReactNode };

const ICONS = { tools: Wrench, brief: ClipboardList, project: Ruler, piece: Box, room: DoorOpen, notes: NotebookPen };
const EXPANDED_KEY = "studio.rail.expanded";

// Remembered per browser; a browser that cannot store it shows the rail collapsed.
function readExpanded(): boolean {
  try {
    return window.localStorage.getItem(EXPANDED_KEY) === "true";
  } catch {
    return false;
  }
}

function writeExpanded(value: boolean) {
  try {
    window.localStorage.setItem(EXPANDED_KEY, String(value));
  } catch {
    // Not remembered; the rail still changes.
  }
}

/** Whether a rail shows its labels, remembered in the browser and shared by every rail. */
export function useRailLabels(): [boolean, () => void] {
  const [expanded, setExpanded] = useState(readExpanded);
  return [
    expanded,
    () => {
      writeExpanded(!expanded);
      setExpanded(!expanded);
    },
  ];
}

/** The rail column pinned at the screen's left edge below the header. */
export function railClass(expanded: boolean) {
  return cn(
    "sticky top-[var(--header-h)] flex h-[calc(100vh-var(--header-h))] shrink-0 flex-col gap-2 self-start border-r bg-card p-1 pt-2",
    expanded ? "w-36 items-stretch" : "w-12 items-center",
  );
}

/** One icon of a rail, with its label beside it when expanded. */
export function railItemClass(expanded: boolean) {
  return expanded ? "h-10 justify-start gap-2 px-2" : "size-10 p-0";
}

/** The rail's "Show labels" / "Hide labels" switch, at the rail's foot. */
export function RailLabelsToggle({ expanded, onToggle }: { expanded: boolean; onToggle: () => void }) {
  const Toggle = expanded ? ChevronsLeft : ChevronsRight;
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className={cn("mt-auto", railItemClass(expanded))}
      aria-label={expanded ? "Hide labels" : "Show labels"}
      aria-expanded={expanded}
      onClick={onToggle}
    >
      <Toggle aria-hidden size={20} className="shrink-0" />
      {expanded && <span aria-hidden>Hide labels</span>}
    </Button>
  );
}

/**
 * The panel rail, pinned at the screen's left edge below the header. Icons only, or with
 * their labels beside them when expanded (remembered in the browser). Choosing an icon
 * opens its panel as a flyout beside the rail; choosing it again, choosing another,
 * Escape or the close button closes or switches it. Focus moves into the flyout and back
 * to its icon.
 */
export function Rail({ panels, open, onOpen }: { panels: Panel[]; open: string | null; onOpen: (id: string | null) => void }) {
  const flyout = useRef<HTMLElement>(null);
  const icons = useRef<Record<string, HTMLButtonElement | null>>({});
  const last = useRef<string | null>(null);
  const [expanded, toggleLabels] = useRailLabels();

  useEffect(() => {
    if (open) {
      last.current = open;
      flyout.current?.focus();
    } else if (last.current) {
      icons.current[last.current]?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpen(null);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open, onOpen]);

  const shown = panels.find((p) => p.id === open);
  return (
    <>
      <nav
        aria-label="Panels"
        className={railClass(expanded)}
      >
        {panels.map((panel) => {
          const Icon = ICONS[panel.icon];
          return (
            <Button
              key={panel.id}
              ref={(button) => {
                icons.current[panel.id] = button;
              }}
              type="button"
              variant="ghost"
              size="sm"
              className={cn(railItemClass(expanded), open === panel.id && "bg-accent")}
              aria-label={panel.label}
              aria-expanded={open === panel.id}
              onClick={() => onOpen(open === panel.id ? null : panel.id)}
            >
              <Icon aria-hidden size={20} className="shrink-0" />
              {expanded && <span aria-hidden>{panel.label}</span>}
            </Button>
          );
        })}
        <RailLabelsToggle expanded={expanded} onToggle={toggleLabels} />
      </nav>
      {shown && (
        <section
          ref={flyout}
          role="dialog"
          aria-label={shown.label}
          tabIndex={-1}
          className={cn(
            "fixed top-[calc(var(--header-h)+0.5rem)] z-30 max-h-[calc(100vh-var(--header-h)-1rem)] w-[min(26rem,calc(100vw-5rem))] space-y-3 overflow-y-auto rounded-xl border bg-card p-4 shadow-lg focus:outline-none",
            expanded ? "left-[9.5rem]" : "left-14",
          )}
        >
          <div className="flex items-center justify-between">
            <h2>{shown.label}</h2>
            <Button type="button" variant="ghost" size="sm" aria-label={`Close ${shown.label}`} onClick={() => onOpen(null)}>
              <X aria-hidden size={16} />
            </Button>
          </div>
          {shown.content}
        </section>
      )}
    </>
  );
}
