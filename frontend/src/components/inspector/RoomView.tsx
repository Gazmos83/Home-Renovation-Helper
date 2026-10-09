import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CameraPreset, Layers, ViewMode } from "@/lib/inspector";
import { Button } from "@/components/ui/button";
import { CAMERAS, Choice } from "@/components/inspector/InspectorView";

/**
 * A room composition in 3D (studio-ui): the inspector's own stage, cameras and modes,
 * with one switch per surface of the build report's surface map (each wall, floor and
 * ceiling, and the items) and "All walls". The ceiling starts off, so the room is seen
 * from above. No explode, dimensions or cut list.
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

export function RoomView({ name, model, report }: { name: string; model: string; report: string }) {
  const [mode, setMode] = useState<ViewMode>("workshop");
  const [camera, setCamera] = useState<CameraPreset>("iso");
  const [layers, setLayers] = useState<Layers | null>(null);
  const read = useQuery({ queryKey: ["composition-report", report], queryFn: () => api.compositionReport(report) });
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

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center gap-4">
        <Choice label="Camera" options={CAMERAS} value={camera} onChange={setCamera} />
        <Choice label="Mode" options={MODES} value={mode} onChange={setMode} />
      </div>
      <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Surfaces">
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
        {surfaces.map((surface) => (
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
        ))}
      </div>
      <div className="h-[60vh] min-h-80 overflow-hidden rounded-md border">
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
          />
        </Suspense>
      </div>
    </div>
  );
}
