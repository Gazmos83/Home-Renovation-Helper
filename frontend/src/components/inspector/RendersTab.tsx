import { useQuery } from "@tanstack/react-query";
import { api, type RenderItem } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RenderRating } from "@/components/RenderRating";
import { FrameScrubber } from "@/components/inspector/FrameScrubber";

/** The newest finished first; a render with no finish time last. */
export function newestFirst(items: RenderItem[]): RenderItem[] {
  return [...items].sort((a, b) => (b.finished_at ?? "").localeCompare(a.finished_at ?? ""));
}

/** The render to show: the one named, else the newest of the hinted tier, else the newest. */
export function chooseRender(items: RenderItem[], named: string | null, tierHint: string | null): RenderItem | null {
  return (
    items.find((item) => item.render === named) ??
    items.find((item) => tierHint !== null && item.tier === tierHint) ??
    items[0] ??
    null
  );
}

/** A turntable's frame `index`, from the route of its first frame (`…/frames/0`). */
function frameRoute(first: string, index: number): string {
  return first.replace(/\/0$/, `/${index}`);
}

/**
 * The inspector's Renders tab (two-tier-renders): every published render of the version,
 * newest first, with its tier and the owner's rating. A selected turntable plays in the
 * frame scrubber, a still shows its picture. Mounted only while the tab is shown, so no
 * frame is fetched before.
 */
export function RendersTab({
  packageId,
  version,
  selected,
  tierHint,
  onSelect,
}: {
  packageId: string;
  version: number;
  selected: string | null;
  tierHint: string | null;
  onSelect: (render: string) => void;
}) {
  const renders = useQuery({
    queryKey: ["renders", packageId, version],
    queryFn: () => api.renders(packageId, version),
  });
  if (renders.error) return <FieldError message={renders.error instanceof Error ? renders.error.message : null} />;
  if (!renders.data) return <p>Loading…</p>;
  const items = newestFirst(renders.data);
  if (items.length === 0) return <p>No renders of this version yet.</p>;
  const shown = chooseRender(items, selected, tierHint) as RenderItem;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Renders">
        {items.map((item) => (
          <Button
            key={item.render}
            type="button"
            size="sm"
            variant={item.render === shown.render ? "default" : "outline"}
            aria-pressed={item.render === shown.render}
            onClick={() => onSelect(item.render)}
          >
            {item.label}
            {item.tier && <span className="ml-1 opacity-80">· {item.tier}</span>}
          </Button>
        ))}
      </div>
      <section aria-label={shown.label} className="grid gap-2">
        <div className="flex items-center gap-2">
          <h3>{shown.label}</h3>
          {shown.tier && <Badge variant="secondary">{shown.tier}</Badge>}
        </div>
        {shown.frames > 0 ? (
          <FrameScrubber
            key={shown.render}
            label={shown.label}
            count={shown.frames}
            frameUrl={(index) => frameRoute(shown.preview, index)}
          />
        ) : (
          <img
            src={shown.preview}
            alt={`${shown.label} of ${packageId} version ${version}`}
            className="max-h-[60vh] rounded-md border object-contain"
          />
        )}
        <RenderRating key={`rating-${shown.render}`} packageId={packageId} version={version} item={shown} />
      </section>
    </div>
  );
}
