import { PropertyBinding } from "three";
import type { PieceSpec } from "./api";

/**
 * What the piece inspector computes from a version's own `spec.json` (piece-inspector).
 *
 * Ported from the predecessor's Studio (`Model.tsx`, `StudioCanvas.tsx`), trimmed to
 * custom builds. Build millimetres are x right, y into the wall (the front faces -y)
 * and z up; the model is exported Y-up, so a build point (x, y, z) is the scene point
 * (x, z, -y), in metres.
 */

export type ViewMode = "workshop" | "blueprint" | "exploded";
export type CameraPreset = "iso" | "front" | "side" | "top";
export type Vec3 = [number, number, number];
export type Offsets = Record<string, Vec3>;
export type LayerMap = Record<string, string[]>;

/** Which layers are switched off; a name absent here is visible. */
export type Layers = Record<string, boolean>;

export function layerVisible(layers: Layers, name: string): boolean {
  return layers[name] !== false;
}

/** How far a module travels at full explode, in scene units (metres). */
const EXPLODE_DISTANCE = 0.45;

/**
 * Each module empty (`MOD_<id>`) moves away from the build's centre along the
 * direction of its own centre, both taken from the emitted module boxes. The
 * extras' empty is not a module, so it stays where it is.
 */
export function customBuildExplode(spec: Pick<PieceSpec, "modules">): Offsets {
  const modules = Object.entries(spec.modules ?? {});
  if (modules.length === 0) return {};
  const boxes = modules.map(([id, m]) => [id, { x: m.x ?? 0, y: m.y ?? 0, z: m.z ?? 0, w: m.w ?? 0, h: m.h ?? 0, d: m.d ?? 0 }] as const);
  const lo = (key: "x" | "y" | "z") => Math.min(...boxes.map(([, b]) => b[key]));
  const hi = (key: "x" | "y" | "z", size: "w" | "d" | "h") => Math.max(...boxes.map(([, b]) => b[key] + b[size]));
  const centre = { x: (lo("x") + hi("x", "w")) / 2, y: (lo("y") + hi("y", "d")) / 2, z: (lo("z") + hi("z", "h")) / 2 };
  const offsets: Offsets = {};
  for (const [id, b] of boxes) {
    const dx = b.x + b.w / 2 - centre.x;
    const dy = b.y + b.d / 2 - centre.y;
    const dz = b.z + b.h / 2 - centre.z;
    const length = Math.hypot(dx, dy, dz);
    offsets[`MOD_${id}`] =
      length === 0
        ? [0, 0, 0]
        : [(dx / length) * EXPLODE_DISTANCE, (dz / length) * EXPLODE_DISTANCE, (-dy / length) * EXPLODE_DISTANCE];
  }
  return offsets;
}

/** Never shown: the studio floor and any dimension geometry (the overlay draws its own). */
function isHidden(name: string): boolean {
  return name === "StudioFloor" || name === "Plane" || name.startsWith("DIM_") || name.startsWith("MOD_Dimensions");
}

/**
 * Which layer a loaded mesh belongs to: `hide`, a layer name, or `keep` for a mesh
 * the map does not name (shown, so an unexpected object is visible, not missing).
 * The loader cleans node names, so the map's names are cleaned the same way.
 */
export function layerOf(name: string, layerMap: LayerMap): string {
  if (isHidden(name)) return "hide";
  for (const [layer, names] of Object.entries(layerMap)) {
    if (names.some((listed) => PropertyBinding.sanitizeNodeName(listed) === name)) return layer;
  }
  return "keep";
}

/** The lowest module's floor height in metres: where a wall cabinet hangs. */
export function baseOf(spec: Pick<PieceSpec, "modules">): number {
  const heights = Object.values(spec.modules ?? {}).map((m) => m.z ?? 0);
  return heights.length ? Math.min(...heights) / 1000 : 0;
}

export type Preset = { pos: Vec3; target: Vec3 };

/** The piece inspector's Iso direction: from the front right, a little above. */
export const PIECE_ISO: Vec3 = [2.7, 0.8, 3.25];

/** The four cameras, framed on the piece's overall size and aimed at its centre. */
export function cameraPresets(overall: PieceSpec["overall"], base = 0, isoDirection: Vec3 = PIECE_ISO): Record<CameraPreset, Preset> {
  const reach = Math.max(overall.w, overall.h, overall.d) / 1000;
  const target: Vec3 = [0, base + overall.h / 2000, 0];
  const distance = Math.max(1.4, reach * 1.9);
  const at = (direction: Vec3): Vec3 => {
    const length = Math.hypot(...direction);
    return [
      target[0] + (direction[0] / length) * distance,
      target[1] + (direction[1] / length) * distance,
      target[2] + (direction[2] / length) * distance,
    ];
  };
  return {
    iso: { pos: at(isoDirection), target },
    front: { pos: at([0, 0, 1]), target },
    side: { pos: at([1, 0, 0]), target },
    // A hair off vertical, so the orbit controls keep their up direction.
    top: { pos: at([0, 1, 0.001]), target },
  };
}
