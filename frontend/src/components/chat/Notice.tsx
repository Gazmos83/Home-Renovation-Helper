import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/api";

/** The button's words: "Review draft v1", "Review preview revision 2". */
export function reviewLabel(tier: string, version: number): string {
  return `Review ${tier} ${version === 1 ? "v1" : `revision ${version}`}`;
}

/**
 * A notice the service posted when a render or a build started in this conversation ended.
 * A finished render of a piece version has a Review button, and a finished build an
 * "Inspect version N" button, both opening the inspector beside the chat; a failed one, a
 * shell, a composition or a deleted version has none. A revision notice (revision-link-button)
 * is posted when the version is created and always has an "Open version N" button.
 */
export function Notice({ m, onReview }: { m: ChatMessage; onReview: (packageId: string, version: number) => void }) {
  const build = m.kind === "build";
  const revision = m.kind === "revision";
  const linked = m.outcome === "succeeded" && m.package_id !== undefined && m.version !== undefined;
  const canOpen = linked && (build || revision || Boolean(m.tier));
  return (
    <section
      aria-label={revision ? "Revision notice" : build ? "Build notice" : "Render notice"}
      data-role="notice"
      data-outcome={m.outcome}
      className="mx-auto flex w-fit max-w-xl flex-col items-center gap-2 rounded-md border px-3 py-2 text-center text-sm"
    >
      <p>{m.text}</p>
      {canOpen && (
        <Button type="button" size="sm" variant="outline" onClick={() => onReview(m.package_id as string, m.version as number)}>
          {revision
            ? `Open version ${m.version}`
            : build
              ? `Inspect version ${m.version}`
              : reviewLabel(m.tier as string, m.version as number)}
        </Button>
      )}
    </section>
  );
}
