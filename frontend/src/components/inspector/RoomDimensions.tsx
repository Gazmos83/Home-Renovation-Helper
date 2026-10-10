import { Html, Line } from "@react-three/drei";
import type { RoomDimensions as Dimensions } from "@/lib/api";
import { planToStage } from "@/lib/inspector";

/**
 * A room composition's wall lengths and ceiling heights in its 3D view (project-room-inspection).
 * Each wall is a line along it just above the floor with its length; each room's ceiling is a
 * vertical line at a point inside the room with its height. Labels are page text, as in
 * `DimensionOverlay`. Drawn in the model's frame (plan mm), inside the view's offset.
 */

const INK = "#3c6568";
// Just above the floor, so a wall's line is not hidden in it.
const WALL_LINE_MM = 40;

function Label({ text }: { text: string }) {
  return (
    <span className="whitespace-nowrap rounded bg-[#f3eee6]/90 px-1 font-mono text-xs text-[#3c6568]">{text}</span>
  );
}

export function RoomDimensions({ dimensions, apartment }: { dimensions: Dimensions; apartment: boolean }) {
  return (
    <group>
      {dimensions.walls.map((wall) => {
        const a = planToStage(wall.from[0], wall.from[1], WALL_LINE_MM);
        const b = planToStage(wall.to[0], wall.to[1], WALL_LINE_MM);
        const mid = planToStage((wall.from[0] + wall.to[0]) / 2, (wall.from[1] + wall.to[1]) / 2, WALL_LINE_MM);
        return (
          <group key={wall.label}>
            <Line points={[a, b]} color={INK} lineWidth={1.5} />
            <Html position={mid} center zIndexRange={[10, 0]}>
              <Label text={`${wall.label}: ${wall.length_mm} mm`} />
            </Html>
          </group>
        );
      })}
      {dimensions.ceilings.map((ceiling) => (
        <group key={ceiling.room}>
          <Line
            points={[planToStage(ceiling.at[0], ceiling.at[1]), planToStage(ceiling.at[0], ceiling.at[1], ceiling.height_mm)]}
            color={INK}
            lineWidth={1}
            dashed
            dashSize={0.08}
            gapSize={0.05}
          />
          <Html position={planToStage(ceiling.at[0], ceiling.at[1], ceiling.height_mm / 2)} center zIndexRange={[10, 0]}>
            <Label text={`${apartment ? `${ceiling.room}: ` : ""}ceiling ${ceiling.height_mm} mm`} />
          </Html>
        </group>
      ))}
    </group>
  );
}
