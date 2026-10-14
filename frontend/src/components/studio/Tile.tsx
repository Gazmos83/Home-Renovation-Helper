import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * One item of a Design Studio grid (studio-tile-grid, style A): the picture fills the top, kept whole,
 * with a badge in its corner; the name and one line of detail below. The whole tile is one button.
 */
export function Tile({
  name,
  detail,
  picture,
  placeholder: Placeholder,
  badge,
  onOpen,
  onPrefetch,
}: {
  name: string;
  detail?: string;
  picture?: string | null;
  placeholder: LucideIcon;
  badge?: ReactNode;
  onOpen: () => void;
  onPrefetch?: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={name}
      onClick={onOpen}
      onPointerEnter={onPrefetch}
      onFocus={onPrefetch}
      className={cn(
        "flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-lg border bg-card text-left text-card-foreground shadow-sm",
        "hover:ring-2 hover:ring-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <span className="relative flex min-h-0 flex-1 items-center justify-center bg-muted">
        {picture ? (
          <img src={picture} alt="" className="size-full object-contain p-2" />
        ) : (
          <Placeholder aria-hidden data-testid="tile-placeholder" size={32} className="text-muted-foreground" />
        )}
        {badge && <span className="absolute right-1 top-1">{badge}</span>}
      </span>
      <span className="grid gap-0.5 p-2">
        <span className="truncate text-sm font-medium">{name}</span>
        {detail && <span className="truncate text-xs text-muted-foreground">{detail}</span>}
      </span>
    </button>
  );
}
