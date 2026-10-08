import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/api";

/** The button's words: "Review draft v1", "Review preview revision 2". */
export function reviewLabel(tier: string, version: number): string {
  return `Review ${tier} ${version === 1 ? "v1" : `revision ${version}`}`;
}

/**
 * A render notice the service posted when a render started in this conversation ended.
 * A finished render of a piece version has a button that opens the inspector beside the
 * chat; a failed one, a shell or a composition has none.
 */
export function Notice({ m, onReview }: { m: ChatMessage; onReview: (packageId: string, version: number) => void }) {
  const canReview = m.outcome === "succeeded" && m.package_id !== undefined && m.version !== undefined && m.tier;
  return (
    <section
      aria-label="Render notice"
      data-role="notice"
      data-outcome={m.outcome}
      className="mx-auto flex w-fit max-w-xl flex-col items-center gap-2 rounded-md border px-3 py-2 text-center text-sm"
    >
      <p>{m.text}</p>
      {canReview && (
        <Button type="button" size="sm" variant="outline" onClick={() => onReview(m.package_id as string, m.version as number)}>
          {reviewLabel(m.tier as string, m.version as number)}
        </Button>
      )}
    </section>
  );
}
