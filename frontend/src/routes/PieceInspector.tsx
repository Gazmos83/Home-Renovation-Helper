import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, versionFile } from "../lib/api";
import type { CameraPreset, Layers, ViewMode } from "../lib/inspector";
import { Button } from "@/components/ui/button";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";
import { CutListTables } from "@/components/inspector/CutListTables";

/**
 * One piece version, inspected (piece-inspector): its model in 3D with the camera
 * buttons, modes, explode, layer switches and overall dimensions, its straight-on
 * views, and its cut list. Every figure comes from the version's own files. The 3D
 * stage is a lazy import, so three.js loads only here.
 */

const InspectorCanvas = lazy(() => import("@/components/inspector/InspectorCanvas"));

const CAMERAS: { id: CameraPreset; label: string }[] = [
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

function Choice<T extends string>({
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

function problem(error: unknown, what: string): string {
  if (error instanceof ApiError && error.status === 404) return `There is no ${what}.`;
  return error instanceof Error ? error.message : `The ${what} could not be read.`;
}

export default function PieceInspector() {
  const { packageId = "", version: versionParam = "" } = useParams();
  const version = Number(versionParam);
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
  const spec = useQuery({
    queryKey: ["spec", packageId, version],
    queryFn: () => api.pieceSpec(packageId, version),
    enabled: built,
  });

  const title = `${packageId}, version ${versionParam}`;
  let body;
  if (!Number.isInteger(version) || version < 1) body = <p>There is no version {versionParam} of {packageId}.</p>;
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
            <div className="h-[60vh] min-h-80 overflow-hidden rounded-md border">
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
    <Page>
      <p className="text-sm">
        <Link to="/pieces" className="underline">
          Back to pieces
        </Link>
      </p>
      <h1>{title}</h1>
      <section className={`${cardClass} grid gap-4`}>{body}</section>
    </Page>
  );
}
