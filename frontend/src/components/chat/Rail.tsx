import { Ruler, Wrench, X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type Panel = { id: string; label: string; icon: "tools" | "project"; content: ReactNode };

const ICONS = { tools: Wrench, project: Ruler };

/**
 * A narrow rail of panel icons beside the chat. Choosing an icon opens its panel as a
 * flyout over the chat; choosing it again, choosing another, Escape or the close button
 * closes or switches it. Focus moves into the flyout and back to its icon.
 */
export function Rail({ panels, open, onOpen }: { panels: Panel[]; open: string | null; onOpen: (id: string | null) => void }) {
  const flyout = useRef<HTMLElement>(null);
  const icons = useRef<Record<string, HTMLButtonElement | null>>({});
  const last = useRef<string | null>(null);

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
      <nav aria-label="Panels" className="flex w-12 shrink-0 flex-col items-center gap-2 pt-1">
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
              className={cn("size-10 p-0", open === panel.id && "bg-accent")}
              aria-label={panel.label}
              aria-expanded={open === panel.id}
              onClick={() => onOpen(open === panel.id ? null : panel.id)}
            >
              <Icon aria-hidden size={20} />
            </Button>
          );
        })}
      </nav>
      {shown && (
        <section
          ref={flyout}
          role="dialog"
          aria-label={shown.label}
          tabIndex={-1}
          className="absolute top-0 left-14 z-20 max-h-[80vh] w-[min(26rem,calc(100%-4rem))] space-y-3 overflow-y-auto rounded-xl border bg-card p-4 shadow-lg focus:outline-none"
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
