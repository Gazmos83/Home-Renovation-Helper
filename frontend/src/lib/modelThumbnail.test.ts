import { describe, expect, it } from "vitest";
import { cameraPosition, loaderFor } from "./modelThumbnail";

describe("modelThumbnail", () => {
  it("reads GLB and glTF through glTF and OBJ through OBJ, and nothing else", () => {
    expect(loaderFor("glb")).toBe("gltf");
    expect(loaderFor("gltf")).toBe("gltf");
    expect(loaderFor("obj")).toBe("obj");
    expect(() => loaderFor("fbx")).toThrow("no preview for a fbx model");
  });

  it("stands the camera on the three-quarter view, far enough to see the whole model", () => {
    const [x, y, z] = cameraPosition([0, 0, 0], 1, 35);
    const distance = Math.hypot(x, y, z);
    // The sphere fits: its radius over the distance is the sine of half the field of view, with a 10 % margin.
    expect(1 / distance).toBeCloseTo(Math.sin((17.5 * Math.PI) / 180) / 1.1, 6);
    expect((Math.asin(y / distance) * 180) / Math.PI).toBeCloseTo(25, 6);
    expect((Math.atan2(x, z) * 180) / Math.PI).toBeCloseTo(35, 6);
  });

  it("is centred on the model, and scales with its size", () => {
    const near = cameraPosition([0, 0, 0], 1);
    const far = cameraPosition([10, 2, -3], 2);
    far.forEach((v, i) => expect(v - [10, 2, -3][i]).toBeCloseTo(near[i] * 2, 9));
  });
});
