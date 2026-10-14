import {
  Box3,
  DirectionalLight,
  HemisphereLight,
  LoadingManager,
  Mesh,
  PerspectiveCamera,
  Scene,
  Sphere,
  Vector3,
  WebGLRenderer,
  type Material,
  type Object3D,
  type Texture,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MTLLoader } from "three/examples/jsm/loaders/MTLLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { modelFile, type ModelAsset } from "./api";

/**
 * A library model's preview picture, drawn once in the owner's browser (studio-tile-grid): no Blender, no
 * render. One off-screen frame from a fixed three-quarter view on a plain background, as a PNG.
 */
export const THUMBNAIL_PX = 384;
const AZIMUTH_DEG = 35;
const ELEVATION_DEG = 25;
const FOV_DEG = 35;
const BACKGROUND = 0xf4f4f5;
const TEXTURE_WAIT_MS = 10_000;

/** Which loader reads a model of this kind: GLB and glTF zips through glTF, OBJ zips through OBJ + MTL. */
export function loaderFor(kind: string): "gltf" | "obj" {
  if (kind === "glb" || kind === "gltf") return "gltf";
  if (kind === "obj") return "obj";
  throw new Error(`no preview for a ${kind} model`);
}

/**
 * Where the camera stands to see a sphere of `radius` around `center` whole, from the three-quarter view:
 * far enough that the sphere fits the field of view, with a 10 % margin.
 */
export function cameraPosition(center: [number, number, number], radius: number, fovDeg = FOV_DEG): [number, number, number] {
  const distance = (radius / Math.sin(((fovDeg / 2) * Math.PI) / 180)) * 1.1;
  const azimuth = (AZIMUTH_DEG * Math.PI) / 180;
  const elevation = (ELEVATION_DEG * Math.PI) / 180;
  return [
    center[0] + distance * Math.cos(elevation) * Math.sin(azimuth),
    center[1] + distance * Math.sin(elevation),
    center[2] + distance * Math.cos(elevation) * Math.cos(azimuth),
  ];
}

async function load(model: ModelAsset): Promise<Object3D> {
  const url = modelFile(model.model_id, model.entry);
  if (loaderFor(model.kind) === "gltf") return (await new GLTFLoader().loadAsync(url)).scene;
  const base = url.slice(0, url.lastIndexOf("/") + 1);
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw new Error(`the model file could not be read (${response.status})`);
  const text = await response.text();
  const obj = new OBJLoader();
  // OBJLoader does not follow `mtllib` itself; without its materials the model is drawn untextured.
  const mtllib = /^\s*mtllib\s+(.+?)\s*$/m.exec(text)?.[1];
  if (mtllib) {
    try {
      const manager = new LoadingManager();
      const materials = await new MTLLoader(manager).setPath(base).loadAsync(mtllib);
      // MTL textures load in the background; drawn before they arrive, the model comes out black.
      const texturesLoaded = new Promise<void>((resolve) => {
        manager.onLoad = () => resolve();
      });
      materials.preload();
      obj.setMaterials(materials);
      const textured = Object.values(materials.materials).some((material) =>
        Object.values(material).some((value) => (value as Texture | null)?.isTexture),
      );
      if (textured) await Promise.race([texturesLoaded, new Promise((resolve) => setTimeout(resolve, TEXTURE_WAIT_MS))]);
    } catch {
      // Drawn without its materials rather than not at all.
    }
  }
  return obj.parse(text);
}

function dispose(root: Object3D) {
  root.traverse((node) => {
    if (!(node instanceof Mesh)) return;
    node.geometry.dispose();
    for (const material of ([] as Material[]).concat(node.material)) {
      for (const value of Object.values(material)) {
        if (value && typeof value === "object" && (value as Texture).isTexture) (value as Texture).dispose();
      }
      material.dispose();
    }
  });
}

/** Draw `model` (it must read `ready`) and return the PNG. One WebGL context, released before returning. */
export async function drawModel(model: ModelAsset): Promise<Blob> {
  const object = await load(model);
  const renderer = new WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  try {
    const box = new Box3().setFromObject(object);
    if (box.isEmpty()) throw new Error("the model has nothing to draw");
    const sphere = box.getBoundingSphere(new Sphere());
    const scene = new Scene();
    scene.add(object);
    scene.add(new HemisphereLight(0xffffff, 0x8a8a8a, 2.5));
    const sun = new DirectionalLight(0xffffff, 2);
    sun.position.copy(sphere.center).add(new Vector3(3, 5, 4).multiplyScalar(sphere.radius));
    scene.add(sun);
    const camera = new PerspectiveCamera(FOV_DEG, 1, sphere.radius / 100, sphere.radius * 100);
    camera.position.set(...cameraPosition(sphere.center.toArray(), sphere.radius));
    camera.lookAt(sphere.center);
    renderer.setPixelRatio(1);
    renderer.setSize(THUMBNAIL_PX, THUMBNAIL_PX, false);
    renderer.setClearColor(BACKGROUND);
    renderer.render(scene, camera);
    return await new Promise<Blob>((resolve, reject) =>
      renderer.domElement.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("no picture"))), "image/png"),
    );
  } finally {
    dispose(object);
    renderer.dispose();
    renderer.forceContextLoss();
  }
}
