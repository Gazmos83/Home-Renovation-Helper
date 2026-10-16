import { cn } from "@/lib/utils";
import { ROLE_LABELS } from "./roles";

/** Stands in the reply's place while a turn runs, naming who is working. */
export function WaitingBubble({ working, tool, compact = false }: { working: string | null; tool: string | null; compact?: boolean }) {
  const who = working ? `${ROLE_LABELS[working] ?? working} is working` : "The Foreman is working";
  return (
    <div className="mr-auto max-w-[80%]" data-side="left">
      <div role="status" className={cn("inline-flex items-center gap-2 rounded-2xl border-2 bg-card font-chat", compact ? "px-3 py-1.5" : "px-4 py-3")}>
        <span>{who}…</span>
        <span aria-hidden className="inline-flex gap-1">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
        {tool && <span className="text-sm text-muted-foreground">({tool})</span>}
      </div>
    </div>
  );
}
