import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { ContactShadows, Grid, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { PieceModel } from "./PieceModel";
import { DimensionOverlay } from "./DimensionOverlay";
import type { PieceSpec } from "@/lib/api";
import {
  baseOf,
  cameraPresets,
  customBuildExplode,
  layerVisible,
  type CameraPreset,
  type Layers,
  type Preset,
  type ViewMode,
} from "@/lib/inspector";

/**
 * The 3D stage for one piece version (piece-inspector), ported from the
 * predecessor's `StudioCanvas`. Loaded only by the inspector page's lazy import,
 * so no other page pays for three.js. Sizes follow the piece's overall size,
 * where the predecessor's were fixed for one design.
 */

export type InspectorCanvasProps = {
  url: string;
  spec: PieceSpec;
  mode: ViewMode;
  camera: CameraPreset;
  explode: number;
  layers: Layers;
};

function CameraRig({ preset, reach }: { preset: Preset; reach: number }) {
  const { camera } = useThree();
  const controls = useRef<{ target: THREE.Vector3; update: () => void } | null>(null);

  useEffect(() => {
    camera.position.set(...preset.pos);
    camera.lookAt(...preset.target);
    camera.updateProjectionMatrix();
    if (controls.current) {
      controls.current.target.set(...preset.target);
      controls.current.update();
    }
  }, [preset, camera]);

  return (
    <OrbitControls
      ref={controls as never}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={Math.max(0.4, reach * 0.4)}
      maxDistance={Math.max(9, reach * 6)}
      maxPolarAngle={Math.PI / 2 - 0.04}
      target={preset.target}
    />
  );
}

function Lights({ blueprint, reach }: { blueprint: boolean; reach: number }) {
  const s = Math.max(1, reach / 1.5);
  const bound = 3.2 * s;
  return (
    <>
      <hemisphereLight color={blueprint ? "#f3eee6" : "#f0e6d8"} groundColor={blueprint ? "#d4cdc2" : "#6b5a48"} intensity={blueprint ? 0.9 : 0.55} />
      <ambientLight intensity={blueprint ? 0.7 : 0.28} />
      <directionalLight
        position={[2.8 * s, 4.2 * s, 2.2 * s]}
        intensity={blueprint ? 0.35 : 1.55}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-far={12 * s}
        shadow-camera-left={-bound}
        shadow-camera-right={bound}
        shadow-camera-top={bound}
        shadow-camera-bottom={-bound}
      />
      <directionalLight position={[-2.6 * s, 1.8 * s, 1.4 * s]} intensity={blueprint ? 0.15 : 0.4} />
      <directionalLight position={[0.4 * s, 2.4 * s, -2.2 * s]} intensity={blueprint ? 0.1 : 0.35} />
    </>
  );
}

function Ground({ blueprint, reach }: { blueprint: boolean; reach: number }) {
  const size = Math.max(8, reach * 4);
  if (blueprint) {
    return (
      <Grid
        args={[size, size]}
        cellSize={0.1}
        cellThickness={0.6}
        cellColor="#d4cdc2"
        sectionSize={0.5}
        sectionThickness={1.1}
        sectionColor="#3c6568"
        fadeDistance={size}
        fadeStrength={1.4}
        position={[0, 0.001, 0]}
      />
    );
  }
  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.002, 0]} receiveShadow>
        <planeGeometry args={[size * 1.25, size * 1.25]} />
        <meshStandardMaterial color="#e4d9c8" roughness={0.92} metalness={0} />
      </mesh>
      <Grid
        args={[size, size]}
        cellSize={0.1}
        cellThickness={0.4}
        cellColor="#cdbfa9"
        sectionSize={0.5}
        sectionThickness={0.8}
        sectionColor="#b3a288"
        fadeDistance={size}
        fadeStrength={1.4}
        position={[0, 0.001, 0]}
      />
      <ContactShadows position={[0, 0, 0]} opacity={0.32} scale={Math.max(6, reach * 2.5)} blur={2.4} far={Math.max(2.5, reach)} />
    </>
  );
}

export default function InspectorCanvas({ url, spec, mode, camera, explode, layers }: InspectorCanvasProps) {
  const blueprint = mode === "blueprint";
  const base = baseOf(spec);
  const reach = Math.max(spec.overall.w, spec.overall.h, spec.overall.d) / 1000;
  // Memoised: a new preset object would move the camera back on every slider step.
  const presets = useMemo(() => cameraPresets(spec.overall, base), [spec.overall, base]);
  const offsets = useMemo(() => customBuildExplode(spec), [spec]);
  const showDimensions = layerVisible(layers, "dimensions") && mode !== "exploded";
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: presets.iso.pos, fov: 38, near: 0.05, far: Math.max(30, reach * 20) }}
      gl={{ antialias: true }}
      style={{ width: "100%", height: "100%", display: "block", background: blueprint ? "#f3eee6" : "#d9cfc0", touchAction: "none" }}
    >
      <Lights blueprint={blueprint} reach={reach} />
      <CameraRig preset={presets[camera]} reach={reach} />
      <Ground blueprint={blueprint} reach={reach} />
      <Suspense fallback={null}>
        <PieceModel url={url} layerMap={spec.layers} layers={layers} mode={mode} explode={explode} offsets={offsets} />
        {showDimensions && <DimensionOverlay overall={spec.overall} base={base} />}
      </Suspense>
    </Canvas>
  );
}
