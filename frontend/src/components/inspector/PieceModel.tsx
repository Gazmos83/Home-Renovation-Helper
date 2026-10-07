import { useEffect, useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { layerOf, layerVisible, type LayerMap, type Layers, type Offsets, type ViewMode } from "@/lib/inspector";

/**
 * A built version's `model.glb`, as the owner inspects it (piece-inspector).
 *
 * Ported from the predecessor's `CabinetModel`: a mesh belongs to the layer that
 * names it in the version's `spec.json`, the exploded view moves the generator's
 * module empties (their parts follow as children), and Blueprint draws each part's
 * edges on a flat cream material. Part selection was not carried over.
 */
export function PieceModel({
  url,
  layerMap,
  layers,
  mode,
  explode,
  offsets,
}: {
  url: string;
  layerMap: LayerMap;
  layers: Layers;
  mode: ViewMode;
  /** 0 to 1: how far along the exploded offsets the modules are. */
  explode: number;
  offsets: Offsets;
}) {
  // Draco off: the generator exports plain glTF, and drei would otherwise fetch a
  // decoder from a public CDN.
  const { scene } = useGLTF(url, false);
  const amount = mode === "exploded" ? explode : 0;

  const cream = useMemo(() => new THREE.MeshBasicMaterial({ color: 0xf3eee6, toneMapped: false }), []);

  const root = useMemo(() => {
    const copy = scene.clone(true);
    copy.traverse((o) => {
      o.userData.rest = o.position.clone();
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh) {
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        mesh.userData.origMat = materials.map((m) => {
          const clone = m.clone();
          if ("envMapIntensity" in clone) (clone as THREE.MeshStandardMaterial).envMapIntensity = 0.6;
          return clone;
        });
      }
    });
    return copy;
  }, [scene]);

  // Blueprint's line drawing: each part's edges, shown only in that mode.
  useEffect(() => {
    const edges: THREE.LineSegments[] = [];
    root.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh || !mesh.geometry) return;
      const lines = new THREE.LineSegments(
        new THREE.EdgesGeometry(mesh.geometry, 28),
        new THREE.LineBasicMaterial({ color: 0x1c1814, transparent: true, opacity: 0.8 }),
      );
      lines.name = `edge:${mesh.name}`;
      mesh.add(lines);
      edges.push(lines);
    });
    return () => {
      for (const e of edges) {
        e.parent?.remove(e);
        e.geometry.dispose();
        (e.material as THREE.Material).dispose();
      }
    };
  }, [root]);

  useFrame(() => {
    const blueprint = mode === "blueprint";
    root.traverse((o) => {
      const rest: THREE.Vector3 | undefined = o.userData.rest;
      const offset = offsets[o.name];
      if (rest) {
        if (offset && amount > 0) {
          o.position.set(rest.x + offset[0] * amount, rest.y + offset[1] * amount, rest.z + offset[2] * amount);
        } else {
          o.position.copy(rest);
        }
      }
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const layer = layerOf(mesh.name, layerMap);
      if (layer === "hide") {
        mesh.visible = false;
        return;
      }
      mesh.visible = layer === "keep" || layerVisible(layers, layer);
      const original = mesh.userData.origMat as THREE.Material[] | undefined;
      if (blueprint) mesh.material = cream;
      else if (original) mesh.material = original.length === 1 ? original[0]! : original;
      mesh.traverse((child) => {
        if ((child as THREE.LineSegments).isLineSegments) child.visible = blueprint;
      });
    });
  });

  useEffect(() => () => cream.dispose(), [cream]);

  return <primitive object={root} />;
}
