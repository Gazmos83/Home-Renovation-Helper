import { Button, buttonVariants } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/api";

/**
 * A notice the service posted when a render or a build started in this conversation ended.
 * A finished build has an "Inspect version N" button opening the version beside the chat; a failed
 * one or a deleted version has none. A piece render's notice is text only: renders belong to rooms
 * now, and the piece inspector has no Renders tab (render-now-blueprints-verdict-note). A revision notice is no longer posted (studio-navigation-tidy);
 * one already in the history shows as its text with no button. A finished room render carries
 * links to its viewer or still, opening in a new tab (room-render-notices).
 */
export function Notice({
  m,
  onReview,
}: {
  m: ChatMessage;
  /** Open a built version beside the chat. */
  onReview: (packageId: string, version: number) => void;
}) {
  const build = m.kind === "build";
  const revision = m.kind === "revision";
  const linked = m.outcome === "succeeded" && m.package_id !== undefined && m.version !== undefined;
  const canOpen = linked && build;
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
          Inspect version {m.version}
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
