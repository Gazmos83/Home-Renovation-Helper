import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type Side = "left" | "right" | "center";

/**
 * One chat bubble: replies from the left, the owner from the right, forms in the centre. `compact`
 * (the "Piece, room and chat above" layout) puts every bubble on the left as a light bubble with its
 * speaker inline before the text (workspace-chat-above-layout).
 */
export function Bubble({ side, speaker, children, className, compact = false, ...rest }: {
  side: Side;
  speaker?: string;
  children: ReactNode;
  className?: string;
  compact?: boolean;
  "data-role"?: string;
}) {
  if (compact) {
    return (
      <div className="mr-auto max-w-full" data-side="left" {...rest}>
        <div className={cn("flex items-start gap-2 rounded-xl border bg-card px-3 py-1.5", className)}>
          {speaker && <span className="shrink-0 pt-0.5 font-heading text-sm font-semibold">{speaker}:</span>}
          <div className="min-w-0 flex-1">{children}</div>
        </div>
      </div>
    );
  }
  return (
    <div
      className={cn(
        "max-w-[80%] space-y-1",
        side === "right" && "ml-auto",
        side === "left" && "mr-auto",
        side === "center" && "mx-auto w-full",
      )}
      data-side={side}
      {...rest}
    >
      {speaker && (
        <div className={cn("font-heading text-xs tracking-wide text-muted-foreground uppercase", side === "right" && "text-right")}>
          {speaker}
        </div>
      )}
      <div
        className={cn(
          "rounded-2xl px-4 py-3",
          side === "right" && "bg-primary text-primary-foreground",
          side === "left" && "border bg-card",
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}
