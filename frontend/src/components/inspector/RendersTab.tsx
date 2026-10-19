import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, type RenderJob, type RoomRender } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FrameScrubber } from "@/components/inspector/FrameScrubber";

/** A turntable's frame `index`, from the route of its first frame (`…/frames/0`). */
function frameRoute(first: string, index: number): string {
  return first.replace(/\/0$/, `/${index}`);
}

const message = (error: unknown) => (error instanceof Error ? error.message : null);

/**
 * "Render version N now" for a built room version (render-now-blueprints-verdict-note): a plain
 * sentence with the guard's estimate first, then Start or Cancel. Start asks for a draft turntable
 * only; the guard runs in full on that request.
 */
function RenderNow({ slug, version, job }: { slug: string; version: number; job: RenderJob | null }) {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const estimate = useQuery({
    queryKey: ["room-render-estimate", slug, version],
    queryFn: () => api.roomRenderEstimate(slug, version),
    enabled: asking,
    retry: false,
  });
  const start = useMutation({
    mutationFn: () => api.startRoomRender(slug, version),
    onSuccess: () => {
      setAsking(false);
      void queryClient.invalidateQueries({ queryKey: ["room-renders", slug, version] });
    },
  });
  if (job || start.isSuccess) {
    const about = job?.estimate ?? start.data?.estimate;
    return (
      <p role="status">
        Rendering version {version}…{about ? ` ${about}` : ""}
      </p>
    );
  }
  if (!asking) {
    return (
      <div>
        <Button type="button" size="sm" onClick={() => setAsking(true)}>
          Render version {version} now
        </Button>
      </div>
    );
  }
  return (
    <div className="grid gap-2 rounded-md border p-2" role="group" aria-label={`Render version ${version}`}>
      {estimate.error ? (
        <FieldError message={message(estimate.error)} />
      ) : estimate.data ? (
        <p className="text-sm">
          This makes a quick turn-around preview of the room on this computer, so you can look at it from every
          side. It takes {estimate.data.estimate}.
        </p>
      ) : (
        <p className="text-sm">Working out how long it takes…</p>
      )}
      <div className="flex flex-wrap gap-2">
        {estimate.data && (
          <Button type="button" size="sm" disabled={start.isPending} onClick={() => start.mutate()}>
            Start
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={start.isPending}
          onClick={() => {
            setAsking(false);
            start.reset();
          }}
        >
          Cancel
        </Button>
      </div>
      <FieldError message={message(start.error)} />
    </div>
  );
}

/**
 * The room inspector's Renders tab (render-now-blueprints-verdict-note): the room version's
 * published turntable and still, newest first. A selected turntable plays in the frame scrubber.
 * While a render runs the tab follows it, then shows the new turntable selected. A built version
 * with no renders offers "Render version N now".
 */
export function RoomRendersTab({ slug, version, built }: { slug: string; version: number; built: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const renders = useQuery({
    queryKey: ["room-renders", slug, version],
    queryFn: () => api.roomRenders(slug, version),
    refetchInterval: (query) => (query.state.data?.render_job ? 3000 : false),
  });
  const job = renders.data?.render_job ?? null;
  // Once a followed render ends, select the newest turntable.
  const wasRendering = useRef(false);
  useEffect(() => {
    if (wasRendering.current && !job) {
      const turntable = (renders.data?.renders ?? []).find((item) => item.frames > 0);
      if (turntable) setSelected(turntable.render);
    }
    wasRendering.current = job !== null;
  }, [job, renders.data]);
  if (renders.error) return <FieldError message={message(renders.error)} />;
  if (!renders.data) return <p>Loading…</p>;
  const items = renders.data.renders;
  if (items.length === 0 || job) {
    return (
      <div className="grid gap-2">
        {items.length === 0 && <p>No renders of this version yet.</p>}
        {built ? <RenderNow slug={slug} version={version} job={job} /> : <p className="text-sm">This version is not built yet.</p>}
      </div>
    );
  }
  const shown: RoomRender = items.find((item) => item.render === selected) ?? items[0];
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
            onClick={() => setSelected(item.render)}
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
          <img src={shown.preview} alt={`${shown.label} of version ${version}`} className="max-h-[60vh] rounded-md border object-contain" />
        )}
      </section>
    </div>
  );
}
