import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import PieceInspector from "./PieceInspector";

/**
 * piece-inspector: the page reads the version and its spec.json; the 3D stage is
 * stubbed (no WebGL in jsdom) so the test sees the props it is given.
 */
vi.mock("@/components/inspector/InspectorCanvas", () => ({
  default: (props: Record<string, unknown>) => (
    <div data-testid="canvas" data-props={JSON.stringify(props)} />
  ),
}));

const SPEC = {
  name: "Murphy bed",
  units: "mm",
  overall: { w: 3000, h: 2900, d: 450 },
  modules: { "left-base": { x: 20, y: 50, z: 100, w: 610, h: 650, d: 400 } },
  layers: { carcass: ["side", "side#2"], backs: [], shelves: [], fronts: ["door"], extras: [] },
  parts: [
    { id: "side", name: "Side", qty: 2, l: 650, w: 394, t: 18, material: "18 mm oak", grain: "length", banding: "front edge", notes: "Rule: sides", module: "left-base" },
    { id: "door", name: "Door", qty: 1, l: 646, w: 606, t: 18, material: "18 mm oak", grain: "length", banding: "all", notes: "", module: "left-base" },
  ],
  hardware: [{ id: "confirmat-7x50", item: "Confirmat screw 7×50 mm", qty: 96, notes: "Rule: 8 per carcass" }],
};

const FILES_WITH_VIEWS = ["cutlist.csv", "front.png", "model.glb", "screenshot.png", "side.png", "spec.json", "top.png"];

function serve(status = "succeeded", files = FILES_WITH_VIEWS) {
  return stubFetch((call) => {
    if (call === "GET /packages/murphy-bed/versions/1") {
      return { body: { package_id: "murphy-bed", version: 1, status, approved_at: null, files } };
    }
    if (call === "GET /packages/murphy-bed/versions/1/files/spec.json") return { body: SPEC };
    return undefined;
  });
}

function show(path = "/pieces/murphy-bed/versions/1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/pieces/:packageId/versions/:version" element={<PieceInspector />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function canvasProps() {
  const canvas = await screen.findByTestId("canvas");
  return JSON.parse(canvas.dataset.props ?? "{}") as Record<string, unknown>;
}

test("a built version shows its overall size, its layers and the model", async () => {
  serve();
  show();
  expect(await screen.findByText("Overall: W 3000 mm × H 2900 mm × D 450 mm")).toBeInTheDocument();
  const layers = screen.getByRole("group", { name: "Layers" });
  expect([...layers.querySelectorAll("button")].map((b) => b.textContent)).toEqual([
    "carcass", "backs", "shelves", "fronts", "extras", "dimensions",
  ]);
  const props = await canvasProps();
  expect(props.url).toBe("/packages/murphy-bed/versions/1/files/model.glb");
  expect(props).toMatchObject({ mode: "workshop", camera: "iso", layers: {} });
});

test("the camera, mode and layer controls reach the 3D stage", async () => {
  serve();
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Front" }));
  await user.click(screen.getByRole("button", { name: "Exploded" }));
  await user.click(screen.getByRole("button", { name: "fronts" }));
  expect(screen.getByRole("slider")).toBeInTheDocument();
  expect(await canvasProps()).toMatchObject({ camera: "front", mode: "exploded", layers: { fronts: false } });
  expect(screen.getByRole("button", { name: "fronts" })).toHaveAttribute("aria-pressed", "false");
});

test("the straight-on views are shown with what each measures", async () => {
  serve();
  show();
  const views = await screen.findByRole("region", { name: "Straight-on views" });
  expect(views.querySelectorAll("img")).toHaveLength(3);
  expect(screen.getByAltText("Front view of murphy-bed version 1")).toHaveAttribute(
    "src", "/packages/murphy-bed/versions/1/files/front.png",
  );
  expect(screen.getByText("Top: width and depth")).toBeInTheDocument();
});

test("a version built before the views shows the model without them", async () => {
  serve("succeeded", ["model.glb", "screenshot.png", "spec.json"]);
  show();
  await screen.findByTestId("canvas");
  expect(screen.queryByRole("region", { name: "Straight-on views" })).not.toBeInTheDocument();
});

test("the cut list tab lists every part and hardware row", async () => {
  serve();
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Cut list" }));
  const cut = screen.getByRole("region", { name: "Cut list" });
  expect(cut.querySelectorAll("tbody tr")).toHaveLength(2);
  expect(screen.getByText("Rule: sides")).toBeInTheDocument();
  expect(screen.getByText("2 parts, 3 pieces. All dimensions in mm.")).toBeInTheDocument();
  expect(screen.getByText("Confirmat screw 7×50 mm")).toBeInTheDocument();
  expect(screen.queryByTestId("canvas")).not.toBeInTheDocument();
});

test("the Files tab offers the version's files for download", async () => {
  serve("succeeded", [...FILES_WITH_VIEWS, "model.blend", "hardware.csv", "status.json"]);
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Files" }));
  const panel = within(screen.getByRole("region", { name: "Download the package (version 1)" }));
  expect(panel.getAllByRole("link")).toHaveLength(9);
  const blend = panel.getByRole("link", { name: "Download Blender file (version 1)" });
  expect(blend).toHaveAttribute("href", "/packages/murphy-bed/versions/1/files/model.blend");
  expect(blend).toHaveAttribute("download", "murphy-bed-v1.blend");
  expect(panel.getByRole("link", { name: "Download Hardware (CSV) (version 1)" })).toHaveAttribute("download", "murphy-bed-v1-hardware.csv");
  expect(screen.queryByTestId("canvas")).not.toBeInTheDocument();
});

test("a building version shows its state and no model", async () => {
  serve("running", []);
  show();
  expect(await screen.findByText(/Version 1 is building/)).toBeInTheDocument();
  expect(screen.queryByTestId("canvas")).not.toBeInTheDocument();
});

test("a missing version is named in plain words", async () => {
  stubFetch(() => undefined);
  show("/pieces/murphy-bed/versions/7");
  expect(await screen.findByText("There is no version 7 of murphy-bed.")).toBeInTheDocument();
});

test("the cut list is filtered by module, each named as the design names it", async () => {
  const spec = {
    ...SPEC,
    module_names: { "left-base": "Left lower cabinet", "bed-cabinet": "Bed cabinet" },
    parts: [
      ...SPEC.parts,
      { id: "bed-side", name: "Side", qty: 2, l: 2900, w: 430, t: 18, material: "18 mm oak", grain: "length", banding: "front edge", notes: "", module: "bed-cabinet" },
      { id: "panel", name: "Loose panel", qty: 1, l: 500, w: 300, t: 12, material: "12 mm birch", grain: "none", banding: "none", notes: "", module: "extras" },
    ],
  };
  stubFetch((call) => {
    if (call === "GET /packages/murphy-bed/versions/1") {
      return { body: { package_id: "murphy-bed", version: 1, status: "succeeded", approved_at: null, files: [] } };
    }
    if (call === "GET /packages/murphy-bed/versions/1/files/spec.json") return { body: spec };
    return undefined;
  });
  show();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Cut list" }));
  const filter = screen.getByRole("group", { name: "Filter by module" });
  expect([...filter.querySelectorAll("button")].map((b) => b.textContent)).toEqual([
    "All", "Left lower cabinet", "Bed cabinet", "Extra parts",
  ]);
  const cut = screen.getByRole("region", { name: "Cut list" });
  expect(cut.querySelectorAll("tbody tr")).toHaveLength(4);

  await user.click(screen.getByRole("button", { name: "Left lower cabinet" }));
  expect(cut.querySelectorAll("tbody tr")).toHaveLength(2);
  expect(screen.getByText("Left lower cabinet: 2 parts, 3 pieces. All dimensions in mm.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Left lower cabinet" })).toHaveAttribute("aria-pressed", "true");
  expect([...cut.querySelectorAll("tbody tr td:nth-child(10)")].map((td) => td.textContent)).toEqual([
    "Left lower cabinet", "Left lower cabinet",
  ]);

  await user.click(screen.getByRole("button", { name: "Bed cabinet" }));
  expect(cut.querySelectorAll("tbody tr")).toHaveLength(1);
  expect(screen.getByText("Bed cabinet: 1 part, 2 pieces. All dimensions in mm.")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "All" }));
  expect(cut.querySelectorAll("tbody tr")).toHaveLength(4);
  expect(screen.getByText("4 parts, 6 pieces. All dimensions in mm.")).toBeInTheDocument();
});

test("a single-module version has no module filter", async () => {
  serve();
  show();
  await userEvent.setup().click(await screen.findByRole("button", { name: "Cut list" }));
  expect(screen.queryByRole("group", { name: "Filter by module" })).not.toBeInTheDocument();
});


// --- the version switcher (app-check-2026-10-09) ------------------------------------------

test("choosing an older version shows it and puts it in the address", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /packages/murphy-bed")
      return {
        body: {
          package_id: "murphy-bed",
          versions: [3, 2, 1].map((v) => ({
            package_id: "murphy-bed", version: v, status: "succeeded",
            approved_at: v === 2 ? "2026-10-08T10:00:00+00:00" : null,
          })),
        },
      };
    const read = /^GET \/packages\/murphy-bed\/versions\/(\d)$/.exec(call);
    if (read)
      return { body: { package_id: "murphy-bed", version: Number(read[1]), status: "succeeded", approved_at: null, files: FILES_WITH_VIEWS } };
    if (/^GET \/packages\/murphy-bed\/versions\/\d\/files\/spec.json$/.test(call)) return { body: SPEC };
  });
  show("/pieces/murphy-bed/versions/3");
  const switcher = await screen.findByRole("combobox", { name: "Version" });
  expect([...switcher.querySelectorAll("option")].map((o) => o.textContent)).toEqual([
    "Version 3, built", "Version 2, built, approved", "Version 1, built",
  ]);
  await user.selectOptions(switcher, "1");
  expect(await screen.findByRole("heading", { name: "murphy-bed, version 1" })).toBeInTheDocument();
  await waitFor(async () => expect((await canvasProps()).url).toBe("/packages/murphy-bed/versions/1/files/model.glb"));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});


// --- no Renders tab on a piece: renders belong to the room inspector (render-now-blueprints-verdict-note) ---

test("the piece inspector page offers no Renders tab and opens an old renders address on the Model tab", async () => {
  serve();
  show("/pieces/murphy-bed/versions/1?tab=renders");
  const tabs = within(await screen.findByRole("group", { name: "Inspector tabs" }));
  expect(tabs.queryByRole("button", { name: "Renders" })).not.toBeInTheDocument();
  expect(tabs.getByRole("button", { name: "Model" })).toHaveAttribute("aria-pressed", "true");
});

test("a version that is not built still shows its verdict above the build state", async () => {
  stubFetch((call) => {
    if (call === "GET /packages/murphy-bed/versions/1") {
      return { body: { package_id: "murphy-bed", version: 1, status: "running", approved_at: null, files: [] } };
    }
    if (call === "GET /packages/murphy-bed/versions/1/verdict") {
      return { body: { verdict: { verdict: "mismatch", note: "doors too short", status: "open", updated_at: "x" } } };
    }
    return undefined;
  });
  show();
  const section = await screen.findByRole("region", { name: "Verdict" });
  expect(await within(section).findByText("doors too short")).toBeInTheDocument();
  expect(screen.queryByTestId("canvas")).not.toBeInTheDocument();
});

// --- size warnings (piece-size-room-warning) ---

test("a version too big for its room shows the warning and still offers its tabs (Warning in the inspector)", async () => {
  const warning = "Too big for Wohnen: 2600 mm tall, the ceiling is 2500 mm.";
  stubFetch((call) => {
    if (call === "GET /packages/murphy-bed/versions/1")
      return { body: { package_id: "murphy-bed", version: 1, status: "succeeded", approved_at: null, files: FILES_WITH_VIEWS, size_warnings: [warning] } };
    if (call === "GET /packages/murphy-bed/versions/1/files/spec.json") return { body: SPEC };
    return undefined;
  });
  show();
  expect(await screen.findByText(warning)).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Cut list" })).toBeEnabled();
});

test("a version that fits shows no size warning", async () => {
  serve();
  show();
  await screen.findByTestId("canvas");
  expect(screen.queryByText(/Too big for/)).not.toBeInTheDocument();
});

// --- side column (inspector-side-column) -------------------------------------------------------

test("the stage controls sit in open Views and Parts sections (Piece controls grouped)", async () => {
  serve();
  show();
  const user = userEvent.setup();
  const parts = (await screen.findByRole("group", { name: "Layers" })).closest("details")!;
  const views = screen.getByRole("group", { name: "Camera" }).closest("details")!;
  expect(views.querySelector("summary")).toHaveTextContent("Views");
  expect(parts.querySelector("summary")).toHaveTextContent("Parts");
  expect(views).toHaveAttribute("open");
  expect(parts).toHaveAttribute("open");
  expect(within(views).getByRole("group", { name: "Mode" })).toBeInTheDocument();
  expect(screen.queryByRole("slider")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Exploded" }));
  expect(within(views).getByRole("slider")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Workshop" }));
  expect(screen.queryByRole("slider")).not.toBeInTheDocument();
});

test("folding a section keeps its switches (Folding keeps switches)", async () => {
  serve();
  show();
  const user = userEvent.setup();
  const layers = await screen.findByRole("group", { name: "Layers" });
  await user.click(within(layers).getByRole("button", { name: "fronts" }));
  const parts = layers.closest("details")!;
  await user.click(parts.querySelector("summary")!);
  expect(parts).not.toHaveAttribute("open");
  expect((await canvasProps()).layers).toEqual({ fronts: false });
  await user.click(parts.querySelector("summary")!);
  expect(within(layers).getByRole("button", { name: "fronts" })).toHaveAttribute("aria-pressed", "false");
});
