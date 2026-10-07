import { Html, Line } from "@react-three/drei";
import type { PieceSpec } from "@/lib/api";
import type { Vec3 } from "@/lib/inspector";

/**
 * The overall width, height and depth drawn beside the model, in mm (piece-inspector).
 *
 * Ported from the predecessor's `DimensionOverlay`. The figures are the version's
 * own `overall`; the labels are page text (drei's `Html`) rather than 3D text, which
 * would fetch a font from a public CDN.
 */

const INK = "#3c6568";

function Dim({ a, b, label, offset }: { a: Vec3; b: Vec3; label: string; offset: Vec3 }) {
  const oa: Vec3 = [a[0] + offset[0], a[1] + offset[1], a[2] + offset[2]];
  const ob: Vec3 = [b[0] + offset[0], b[1] + offset[1], b[2] + offset[2]];
  const mid: Vec3 = [(oa[0] + ob[0]) / 2, (oa[1] + ob[1]) / 2, (oa[2] + ob[2]) / 2];
  return (
    <group>
      <Line points={[a, oa]} color={INK} lineWidth={1} />
      <Line points={[b, ob]} color={INK} lineWidth={1} />
      <Line points={[oa, ob]} color={INK} lineWidth={1.5} />
      <Html position={mid} center zIndexRange={[10, 0]}>
        <span className="whitespace-nowrap rounded bg-[#f3eee6]/90 px-1 font-mono text-xs text-[#3c6568]">{label}</span>
      </Html>
    </group>
  );
}

export function DimensionOverlay({ overall, base }: { overall: PieceSpec["overall"]; base: number }) {
  const w = overall.w / 1000;
  const h = overall.h / 1000;
  const d = overall.d / 1000;
  const reach = Math.max(w, h, d);
  const gap = Math.max(0.12, reach * 0.06);
  // The front face is half the depth forward of the model's centre.
  const front = d / 2;
  return (
    <group>
      <Dim a={[-w / 2, base, front]} b={[w / 2, base, front]} offset={[0, -gap, gap]} label={`${overall.w} mm`} />
      <Dim a={[-w / 2, base, front]} b={[-w / 2, base + h, front]} offset={[-gap, 0, gap]} label={`${overall.h} mm`} />
      <Dim a={[w / 2, base, front]} b={[w / 2, base, front - d]} offset={[gap, 0, 0]} label={`${overall.d} mm`} />
    </group>
  );
}
