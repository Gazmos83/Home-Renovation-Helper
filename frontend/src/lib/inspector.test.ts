import { baseOf, cameraPresets, customBuildExplode, layerOf, layerVisible } from "./inspector";

describe("customBuildExplode", () => {
  it("moves two side-by-side modules apart along x and leaves the extras alone", () => {
    const offsets = customBuildExplode({
      modules: {
        left: { x: 0, y: 0, z: 0, w: 600, h: 700, d: 400 },
        right: { x: 600, y: 0, z: 0, w: 600, h: 700, d: 400 },
      },
    });
    expect(offsets["MOD_left"]).toEqual([-0.45, 0, -0]);
    expect(offsets["MOD_right"]).toEqual([0.45, 0, -0]);
    expect(offsets["MOD_extras"]).toBeUndefined();
  });

  it("gives nothing for a build without modules", () => {
    expect(customBuildExplode({})).toEqual({});
  });
});

describe("layerOf", () => {
  const map = { carcass: ["side", "side#2"], fronts: ["door"] };

  it("finds a copy by its #2 name", () => {
    expect(layerOf("side#2", map)).toBe("carcass");
    expect(layerOf("door", map)).toBe("fronts");
  });

  it("keeps a mesh the map does not name and hides the floor and dimensions", () => {
    expect(layerOf("mystery", map)).toBe("keep");
    expect(layerOf("StudioFloor", map)).toBe("hide");
    expect(layerOf("DIM_OverallW", map)).toBe("hide");
  });

  it("reads a layer as visible until it is switched off", () => {
    expect(layerVisible({}, "fronts")).toBe(true);
    expect(layerVisible({ fronts: false }, "fronts")).toBe(false);
  });
});

describe("cameraPresets", () => {
  const overall = { w: 3000, h: 2900, d: 450 };

  it("looks at the piece's centre, the front camera straight along -z", () => {
    const presets = cameraPresets(overall, 0.1);
    const { pos, target } = presets.front;
    expect(target).toEqual([0, 1.55, 0]);
    expect(pos[0]).toBeCloseTo(0);
    expect(pos[1]).toBeCloseTo(target[1]);
    expect(pos[2]).toBeGreaterThan(0);
  });

  it("puts the side camera on +x and the plan camera above", () => {
    const presets = cameraPresets(overall);
    expect(presets.side.pos[0]).toBeGreaterThan(0);
    expect(presets.side.pos[2]).toBeCloseTo(0);
    expect(presets.top.pos[1]).toBeGreaterThan(presets.top.target[1] + 1);
  });

  it("takes the base from the lowest module", () => {
    expect(baseOf({ modules: { a: { z: 900 }, b: { z: 1200 } } })).toBe(0.9);
    expect(baseOf({})).toBe(0);
  });
});
