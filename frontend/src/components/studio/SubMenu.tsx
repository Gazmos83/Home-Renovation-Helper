import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** `state` rides along with the link, e.g. so a dialog opened from the menu closes back to the grid. */
export type SubMenuItem = { id: string; label: string; to: string; state?: unknown };

/**
 * A Design Studio tab's sub-menu (studio-tile-grid): its views, or its pieces or rooms by name
 * (studio-submenu-names), labels always shown and the current one highlighted. Long names are cut short
 * with the full name on hover, and a long list scrolls on its own.
 * `column` sits between the rail and the content from 768 px wide; `row` is the tab strip above the
 * content below that. Studio renders both and CSS shows one.
 * The column has an "x" (`onClose`) and stays open when an entry is chosen; the row ignores the "x"
 * (studio-navigation-tidy).
 */
export function SubMenu({
  label,
  items,
  current,
  layout,
  empty,
  lead,
  onClose,
}: {
  label: string;
  items: SubMenuItem[];
  current: string | null;
  layout: "column" | "row";
  /** Shown in place of the entries when there are none. */
  empty?: string;
  /** An action shown before the entries, e.g. "New conversation". */
  lead?: ReactNode;
  /** Column only: the "x" at its top. */
  onClose?: () => void;
}) {
  const column = layout === "column";
  return (
    <nav
      aria-label={label}
      className={
        layout === "column"
          ? "sticky top-[var(--header-h)] hidden h-[calc(100vh-var(--header-h)-var(--footer-h))] w-44 shrink-0 flex-col gap-1 self-start overflow-y-auto border-r bg-card p-2 md:flex"
          : "-mx-1 flex gap-2 overflow-x-auto border-b px-1 pb-2 md:hidden"
      }
    >
      {column && onClose && (
        <div className="flex justify-end">
          <Button type="button" variant="ghost" size="sm" className="size-8 p-0" aria-label={`Close ${label}`} onClick={onClose}>
            <X aria-hidden size={16} />
          </Button>
        </div>
      )}
      {lead}
      {items.length === 0 && empty && <p className="px-2 py-1.5 text-sm text-muted-foreground">{empty}</p>}
      {items.map((item) => (
        <Link
          key={item.id}
          to={item.to}
          state={item.state}
          title={item.label}
          aria-current={item.id === current ? "page" : undefined}
          className={cn(
            buttonVariants({ variant: "ghost", size: "sm" }),
            layout === "column" ? "min-w-0 shrink-0 justify-start" : "max-w-48 shrink-0",
            item.id === current && "bg-accent font-semibold",
          )}
        >
          <span className="truncate">{item.label}</span>
        </Link>
      ))}
    </nav>
  );
}
