import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, versionFile } from "@/lib/api";
import type { CameraPreset, Layers, ViewMode } from "@/lib/inspector";
import { Button } from "@/components/ui/button";
import { cardClass } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { CutListTables } from "@/components/inspector/CutListTables";

/**
 * One piece version, inspected (piece-inspector): its model in 3D with the camera
 * buttons, modes, explode, layer switches and overall dimensions, its straight-on
 * views, and its cut list. Every figure comes from the version's own files. The 3D
 * stage is a lazy import, so three.js loads only when a model is shown. The inspector
 * page and the conversation's split view both render this one component.
 *
 * With `onChoose`, a version switcher lists every version of the piece, and the view
 * follows a newer version created while it is open: the newest seen at mount (or at
 * the owner's last choice) is remembered, and a larger one is switched to.
 */

const InspectorCanvas = lazy(() => import("@/components/inspector/InspectorCanvas"));

export const CAMERAS: { id: CameraPreset; label: string }[] = [
  { id: "iso", label: "Iso" },
  { id: "front", label: "Front" },
  { id: "side", label: "Side" },
  { id: "top", label: "Plan" },
];

const MODES: { id: ViewMode; label: string }[] = [
  { id: "workshop", label: "Workshop" },
  { id: "blueprint", label: "Blueprint" },
  { id: "exploded", label: "Exploded" },
];

const VIEWS = [
  { file: "front.png", label: "Front", shows: "width and height" },
  { file: "side.png", label: "Side", shows: "depth and height" },
  { file: "top.png", label: "Top", shows: "width and depth" },
];

export function Choice<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { id: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1" role="group" aria-label={label}>
      {options.map((option) => (
        <Button
          key={option.id}
          type="button"
          size="sm"
          variant={option.id === value ? "default" : "outline"}
          aria-pressed={option.id === value}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </Button>
      ))}
    </div>
  );
}

function buildState(status: string | null, version: number): string {
  if (status === "queued" || status === "running") return `Version ${version} is building. The model appears here when the build finishes.`;
  if (status === "failed") return `Version ${version}'s build failed, so there is no model to inspect.`;
  return `Version ${version} is not built yet, so there is no model to inspect.`;
}

function stateWord(status: string | null): string {
  if (status === "succeeded") return "built";
  if (status === "queued" || status === "running") return "building";
  if (status === "failed") return "build failed";
  return "not built";
}

/** Polls the piece's versions while open; how often, in milliseconds. */
const VERSION_POLL_MS = 3000;

function problem(error: unknown, what: string): string {
  if (error instanceof ApiError && error.status === 404) return `There is no ${what}.`;
  return error instanceof Error ? error.message : `The ${what} could not be read.`;
}

export function InspectorView({
  packageId,
  version,
  compact = false,
  versionLabel = String(version),
  onChoose,
}: {
  packageId: string;
  version: number;
  compact?: boolean;
  /** What to call the version when it is not a number, as the address spelled it. */
  versionLabel?: string;
  /** Show another version: the owner's choice in the switcher, or a newer version followed. */
  onChoose?: (version: number) => void;
}) {
  const [tab, setTab] = useState<"model" | "cutlist">("model");
  const [mode, setMode] = useState<ViewMode>("workshop");
  const [camera, setCamera] = useState<CameraPreset>("iso");
  const [explode, setExplode] = useState(0.6);
  const [layers, setLayers] = useState<Layers>({});

  const info = useQuery({
    queryKey: ["version", packageId, version],
    queryFn: () => api.version(packageId, version),
    enabled: Number.isInteger(version) && version > 0,
    refetchInterval: (query) => (["queued", "running"].includes(query.state.data?.status ?? "") ? 3000 : false),
  });
  const built = info.data?.status === "succeeded";

  const versions = useQuery({
    queryKey: ["piece-versions", packageId],
    queryFn: () => api.piece(packageId),
    enabled: Boolean(onChoose),
    refetchInterval: VERSION_POLL_MS,
  });
  const listed = versions.data?.versions ?? [];
  const newest = listed.length ? Math.max(...listed.map((v) => v.version)) : null;
  const baseline = useRef<number | null>(null);
  const [followed, setFollowed] = useState<number | null>(null);
  useEffect(() => {
    if (newest === null || !onChoose) return;
    if (baseline.current === null) baseline.current = newest;
    else if (newest > baseline.current) {
      baseline.current = newest;
      setFollowed(newest);
      onChoose(newest);
    }
  }, [newest, onChoose]);

  function choose(next: number) {
    if (newest !== null) baseline.current = newest;
    setFollowed(null);
    onChoose?.(next);
  }

  const switcher = onChoose && listed.length > 0 && (
    <div className="flex flex-wrap items-center gap-2">
      <Select
        aria-label="Version"
        className="w-auto"
        value={String(version)}
        onChange={(event) => choose(Number(event.target.value))}
      >
        {listed.map((v) => (
          <option key={v.version} value={v.version}>
            {`Version ${v.version}, ${stateWord(v.status)}${v.approved_at ? ", approved" : ""}`}
          </option>
        ))}
      </Select>
      {followed === version && (
        <p role="status" className="text-sm">
          Showing version {version}, the newest
        </p>
      )}
    </div>
  );
  const spec = useQuery({
    queryKey: ["spec", packageId, version],
    queryFn: () => api.pieceSpec(packageId, version),
    enabled: built,
  });

  let body;
  if (!Number.isInteger(version) || version < 1) body = <p>There is no version {versionLabel} of {packageId}.</p>;
  else if (info.error) body = <p>{problem(info.error, `version ${version} of ${packageId}`)}</p>;
  else if (!info.data) body = <p>Loading…</p>;
  else if (!built) body = <p>{buildState(info.data.status, version)}</p>;
  else if (spec.error) body = <p>{problem(spec.error, `spec.json for version ${version}`)}</p>;
  else if (!spec.data) body = <p>Loading…</p>;
  else {
    const files = info.data.files ?? [];
    const views = VIEWS.filter((view) => files.includes(view.file));
    const layerNames = [...Object.keys(spec.data.layers), "dimensions"];
    const { w, h, d } = spec.data.overall;
    body = (
      <>
        <Choice
          label="Inspector tabs"
          options={[
            { id: "model", label: "Model" },
            { id: "cutlist", label: "Cut list" },
          ]}
          value={tab}
          onChange={setTab}
        />
        {tab === "cutlist" ? (
          <CutListTables spec={spec.data} />
        ) : (
          <>
            <p className="text-sm">
              Overall: W {w} mm × H {h} mm × D {d} mm
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <Choice label="Camera" options={CAMERAS} value={camera} onChange={setCamera} />
              <Choice label="Mode" options={MODES} value={mode} onChange={setMode} />
              {mode === "exploded" && (
                <label className="flex items-center gap-2 text-sm">
                  Explode
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={explode}
                    onChange={(event) => setExplode(Number(event.target.value))}
                  />
                </label>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Layers">
              {layerNames.map((name) => {
                const on = layers[name] !== false;
                return (
                  <Button
                    key={name}
                    type="button"
                    size="sm"
                    variant={on ? "default" : "outline"}
                    aria-pressed={on}
                    onClick={() => setLayers((current) => ({ ...current, [name]: !on }))}
                  >
                    {name}
                  </Button>
                );
              })}
            </div>
            <div className={cn("min-h-80 overflow-hidden rounded-md border", compact ? "h-[50vh]" : "h-[60vh]")}>
              <Suspense fallback={<p className="p-4">Loading the model…</p>}>
                <InspectorCanvas
                  url={versionFile(packageId, version, "model.glb")}
                  spec={spec.data}
                  mode={mode}
                  camera={camera}
                  explode={explode}
                  layers={layers}
                />
              </Suspense>
            </div>
            {views.length > 0 && (
              <section aria-label="Straight-on views" className="grid gap-2">
                <h2>Straight-on views</h2>
                <div className="grid gap-4 sm:grid-cols-3">
                  {views.map((view) => (
                    <figure key={view.file} className="grid gap-1">
                      <a href={versionFile(packageId, version, view.file)} target="_blank" rel="noreferrer">
                        <img
                          src={versionFile(packageId, version, view.file)}
                          alt={`${view.label} view of ${packageId} version ${version}`}
                          className="rounded-md border"
                        />
                      </a>
                      <figcaption className="text-sm text-muted-foreground">
                        {view.label}: {view.shows}
                      </figcaption>
                    </figure>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </>
    );
  }

  return (
    <section className={`${cardClass} grid gap-4`}>
      {switcher}
      {body}
    </section>
  );
}
