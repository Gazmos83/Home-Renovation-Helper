import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type Side = "left" | "right" | "center";

/** One chat bubble: replies from the left, the owner from the right, forms in the centre. */
export function Bubble({ side, speaker, children, className, ...rest }: {
  side: Side;
  speaker?: string;
  children: ReactNode;
  className?: string;
  "data-role"?: string;
}) {
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
