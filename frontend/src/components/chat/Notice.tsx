import { Button, buttonVariants } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/api";

/** The button's words: "Review draft v1", "Review final revision 2". */
export function reviewLabel(tier: string, version: number): string {
  return `Review ${tier} ${version === 1 ? "v1" : `revision ${version}`}`;
}

/**
 * A notice the service posted when a render or a build started in this conversation ended.
 * A finished render of a piece version has a Review button, opening the inspector beside the
 * chat on its Renders tab, and a finished build an "Inspect version N" button opening it; a failed one, a
 * shell or a deleted version has none. A revision notice is no longer posted (studio-navigation-tidy);
 * one already in the history shows as its text with no button. A finished room render carries
 * links to its viewer or still, opening in a new tab (room-render-notices).
 */
export function Notice({
  m,
  onReview,
}: {
  m: ChatMessage;
  /** Open the version beside the chat; a render's tier opens its Renders tab on that render (two-tier-renders). */
  onReview: (packageId: string, version: number, tier?: string) => void;
}) {
  const build = m.kind === "build";
  const revision = m.kind === "revision";
  const linked = m.outcome === "succeeded" && m.package_id !== undefined && m.version !== undefined;
  const canOpen = linked && !revision && (build || Boolean(m.tier));
  return (
    <section
      aria-label={revision ? "Revision notice" : build ? "Build notice" : "Render notice"}
      data-role="notice"
      data-outcome={m.outcome}
      className="mx-auto flex w-fit max-w-xl flex-col items-center gap-2 rounded-md border px-3 py-2 text-center text-sm"
    >
      <p>{m.text}</p>
      {canOpen && (
        <Button type="button" size="sm" variant="outline" onClick={() =>
            onReview(m.package_id as string, m.version as number, build ? undefined : (m.tier as string))
          }>
          {build ? `Inspect version ${m.version}` : reviewLabel(m.tier as string, m.version as number)}
        </Button>
      )}
      {m.outcome === "succeeded" &&
        (m.links ?? []).map((link) => (
          <a
            key={link.href}
            href={link.href}
            target="_blank"
            rel="noreferrer"
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            {link.label}
          </a>
        ))}
    </section>
  );
}
