import { Html } from "@react-three/drei";
import type { PieceSpec } from "@/lib/api";
import { moduleLabels, type Offsets } from "@/lib/inspector";

/**
 * Each module's name and width × height × depth in mm, at the module, in Exploded mode
 * (version-cleanup-and-inspection). The figures are the version's own `spec.json`
 * `modules`; each label moves with its module as the explode slider moves. Page text
 * (drei's `Html`), styled like the overall dimensions, so no font is fetched.
 */
export function ModuleLabels({ spec, offsets, explode }: { spec: PieceSpec; offsets: Offsets; explode: number }) {
  return (
    <group>
      {moduleLabels(spec, offsets, explode).map((label) => (
        <Html key={label.id} position={label.position} center zIndexRange={[10, 0]}>
          <span className="whitespace-nowrap rounded bg-[#f3eee6]/90 px-1 font-mono text-xs text-[#3c6568]">{label.text}</span>
        </Html>
      ))}
    </group>
  );
}
