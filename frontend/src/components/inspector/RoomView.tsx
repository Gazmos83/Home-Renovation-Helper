import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CompositionVersion } from "@/lib/api";
import type { CameraPreset, Layers, ViewMode } from "@/lib/inspector";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { CAMERAS, Choice, StageSection } from "@/components/inspector/InspectorView";
import { RoomDimensions } from "@/components/inspector/RoomDimensions";

/**
 * A room composition in 3D (studio-ui): the inspector's own stage, cameras and modes,
 * with one switch per surface of the build report's surface map (each wall, floor and
 * ceiling, and the items) and "All walls". The ceiling starts off, so the room is seen
 * from above. A "dimensions" switch, off at first, labels each wall's length and each
 * room's ceiling height from the version's own plan (project-room-inspection). No explode
 * or cut list. The switches sit in a column right of the stage under Views, Room and
 * Furniture (inspector-side-column).
 */

const InspectorCanvas = lazy(() => import("@/components/inspector/InspectorCanvas"));

const MODES: { id: ViewMode; label: string }[] = [
  { id: "workshop", label: "Workshop" },
  { id: "blueprint", label: "Blueprint" },
];

// From the front right and well above, so the room is seen into with its ceiling off.
const ROOM_ISO: [number, number, number] = [2.7, 3.6, 3.25];

const isWall = (surface: string) => /(^|: )wall \d+$/.test(surface);
const isCeiling = (surface: string) => /(^|: )ceiling$/.test(surface);

/** The newest listed versions of a composition, newest first (project-room-inspection). */
export function VersionSelect({
  name,
  versions,
  value,
  onChange,
}: {
  name: string;
  versions: CompositionVersion[];
  value: number;
  onChange: (version: number) => void;
}) {
  return (
    <Select
      aria-label={`Version of ${name}`}
      className="w-auto"
      value={String(value)}
      onChange={(event) => onChange(Number(event.target.value))}
    >
      {versions.map((v) => (
        <option key={v.version} value={v.version}>
          {v.approved_at ? `Version ${v.version} (approved)` : `Version ${v.version}`}
        </option>
      ))}
    </Select>
  );
}

export function RoomView({
  name,
  model,
  report,
  dimensions,
  apartment = false,
}: {
  name: string;
  model: string;
  report: string;
  /** The version's dimensions route; without it the switch is not offered. */
  dimensions?: string | null;
  apartment?: boolean;
}) {
  const [mode, setMode] = useState<ViewMode>("workshop");
  const [camera, setCamera] = useState<CameraPreset>("iso");
  const [layers, setLayers] = useState<Layers | null>(null);
  const [measured, setMeasured] = useState(false);
  const read = useQuery({ queryKey: ["composition-report", report], queryFn: () => api.compositionReport(report) });
  // Read only once the owner switches dimensions on.
  const sizes = useQuery({
    queryKey: ["composition-dimensions", dimensions],
    queryFn: () => api.compositionDimensions(dimensions as string),
    enabled: measured && Boolean(dimensions),
  });
  // Kept stable across switches: a new frame would move the camera back to its preset.
  const frame = useMemo(() => {
    if (!read.data) return null;
    const { min, max } = read.data.extent_mm;
    return {
      spec: { overall: { w: max[0] - min[0], h: max[2] - min[2], d: max[1] - min[1] }, layers: read.data.surfaces },
      // The model is in the plan's frame (x, y in mm, exported Y-up): move its centre to the stage's.
      offset: [-(min[0] + max[0]) / 2000, 0, (min[1] + max[1]) / 2000] as [number, number, number],
    };
  }, [read.data]);

  if (read.error) return <p>The 3D view of {name} could not be read.</p>;
  if (!read.data || !frame) return <p>Loading…</p>;
  const surfaces = Object.keys(read.data.surfaces);
  const walls = surfaces.filter(isWall);
  // The ceiling starts off; the overlay of a piece's dimensions never shows here.
  const shown: Layers = layers ?? Object.fromEntries(surfaces.filter(isCeiling).map((s) => [s, false]));
  const on = (surface: string) => shown[surface] !== false;
  const allWalls = walls.length > 0 && walls.every(on);

  // The items switch belongs to Furniture.
  const roomSurfaces = surfaces.filter((surface) => surface !== "items");
  const furniture = surfaces.includes("items");
  const toggle = (surface: string) => (
    <Button
      key={surface}
      type="button"
      size="sm"
      variant={on(surface) ? "default" : "outline"}
      aria-pressed={on(surface)}
      onClick={() => setLayers({ ...shown, [surface]: !on(surface) })}
    >
      {surface}
    </Button>
  );

  return (
    <div className="grid gap-2">
      {measured && sizes.error && <p className="text-sm">The dimensions of {name} could not be read.</p>}
      <div className="flex h-[60vh] min-h-80 gap-3">
        <div className="min-w-0 flex-1 overflow-hidden rounded-md border">
          <Suspense fallback={<p className="p-4">Loading the model…</p>}>
            <InspectorCanvas
              url={model}
              spec={frame.spec}
              mode={mode}
              camera={camera}
              explode={0}
              layers={{ ...shown, dimensions: false }}
              offset={frame.offset}
              isoDirection={ROOM_ISO}
              overlay={measured && sizes.data ? <RoomDimensions dimensions={sizes.data} apartment={apartment} /> : undefined}
            />
          </Suspense>
        </div>
        <div className="grid w-max shrink-0 content-start gap-3 overflow-y-auto [&_button]:h-6 [&_button]:px-2" data-role="stage-column">
          <StageSection title="Views">
            <Choice label="Camera" options={CAMERAS} value={camera} onChange={setCamera} stacked />
            <Choice label="Mode" options={MODES} value={mode} onChange={setMode} stacked />
          </StageSection>
          <StageSection title="Room">
            <div className="grid gap-1" role="group" aria-label="Surfaces">
              {walls.length > 0 && (
                <Button
                  type="button"
                  size="sm"
                  variant={allWalls ? "default" : "outline"}
                  aria-pressed={allWalls}
                  onClick={() => setLayers({ ...shown, ...Object.fromEntries(walls.map((w) => [w, !allWalls])) })}
                >
                  All walls
                </Button>
              )}
              {roomSurfaces.map(toggle)}
              {dimensions && (
                <Button
                  type="button"
                  size="sm"
                  variant={measured ? "default" : "outline"}
                  aria-pressed={measured}
                  onClick={() => setMeasured(!measured)}
                >
                  dimensions
                </Button>
              )}
            </div>
          </StageSection>
          {furniture && (
            <StageSection title="Furniture">
              <div className="grid gap-1" role="group" aria-label="Furniture">
                {toggle("items")}
              </div>
            </StageSection>
          )}
        </div>
      </div>
    </div>
  );
}
