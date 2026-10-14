import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** `state` rides along with the link, e.g. so a dialog opened from the menu closes back to the grid. */
export type SubMenuItem = { id: string; label: string; to: string; state?: unknown };

/**
 * A Design Studio tab's sub-menu (studio-tile-grid): its views, or its pieces or rooms by name
 * (studio-submenu-names), labels always shown and the current one highlighted. Long names are cut short
 * with the full name on hover, and a long list scrolls on its own.
 * `column` sits between the rail and the content from 768 px wide; `row` is the tab strip above the
 * content below that. Studio renders both and CSS shows one.
 */
export function SubMenu({
  label,
  items,
  current,
  layout,
  empty,
}: {
  label: string;
  items: SubMenuItem[];
  current: string | null;
  layout: "column" | "row";
  /** Shown in place of the entries when there are none. */
  empty?: string;
}) {
  return (
    <nav
      aria-label={label}
      className={
        layout === "column"
          ? "sticky top-[var(--header-h)] hidden h-[calc(100vh-var(--header-h))] w-44 shrink-0 flex-col gap-1 self-start overflow-y-auto border-r bg-card p-2 md:flex"
          : "-mx-1 flex gap-2 overflow-x-auto border-b px-1 pb-2 md:hidden"
      }
    >
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
