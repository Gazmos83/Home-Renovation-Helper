import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Rooms from "./Rooms";

// No WebGL in jsdom: the 3D stage is a stub that shows the props it is given.
vi.mock("@/components/inspector/InspectorCanvas", () => ({
  default: (props: Record<string, unknown>) => <div data-testid="canvas" data-props={JSON.stringify(props)} />,
}));

const wohnen = {
  scope: "room", name: "Wohnen", slug: "wohnen", latest_version: 2, status: "succeeded",
  items: [
    { id: "wall", type: "piece", name: "listening-wall v4", version: 4, approved: false, no_longer_approved: true },
    { id: "sofa", type: "stand-in", name: "Sofa" },
  ],
  picture: "/compositions/wohnen/versions/2/files/screenshot.png",
  viewer: "/compositions/wohnen/versions/2/files/viewer.html",
};
const armchair = {
  model_id: "m1", name: "Armchair", kind: "glb", width_mm: 800, depth_mm: 700, height_mm: 900,
  state: "checking", reason: null,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Rooms /></QueryClientProvider>);
}

test("a placed piece that is no longer approved is marked plainly", async () => {
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [wohnen] };
    if (call === "GET /models") return { body: [] };
  });
  show();
  const card = within(await screen.findByRole("region", { name: "Wohnen" }));
  expect(card.getByText("listening-wall v4").closest("li")).toHaveTextContent("no longer approved");
  expect(card.getByText("Sofa").closest("li")).not.toHaveTextContent("no longer approved");
  expect(card.getByRole("img")).toHaveAttribute("src", wohnen.picture);
  expect(card.getByRole("link", { name: "Open the turntable viewer of Wohnen" })).toHaveAttribute("href", wohnen.viewer);
});

test("a refused upload shows its reason and leaves the library unchanged", async () => {
  // A file picker's filter can be overridden by the owner, so the service decides.
  const user = userEvent.setup({ applyAccept: false });
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [] };
    if (call === "GET /models") return { body: [] };
    if (call === "POST /models") {
      return { status: 415, body: { detail: { failure_class: "unsupported_type", reason: "a .blend file is not accepted; export the model as GLB, glTF or OBJ" } } };
    }
  });
  show();
  await user.upload(await screen.findByLabelText("File"), new File(["BLENDER"], "chair.blend"));
  await user.type(screen.getByLabelText("Name"), "Chair");
  await user.type(screen.getByLabelText("Width (mm)"), "800");
  await user.type(screen.getByLabelText("Depth (mm)"), "700");
  await user.type(screen.getByLabelText("Height (mm)"), "900");
  await user.click(screen.getByRole("button", { name: "Upload model" }));
  expect(await screen.findByText("a .blend file is not accepted; export the model as GLB, glTF or OBJ")).toBeInTheDocument();
  expect(screen.getByText("No models yet.")).toBeInTheDocument();
});

test("a model being checked turns ready without a reload", async () => {
  let checked = false;
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [] };
    if (call === "GET /models") {
      const body = [{ ...armchair, state: checked ? "ready" : "checking" }];
      checked = true;
      return { body };
    }
  });
  show();
  const library = within(await screen.findByRole("region", { name: "Model library" }));
  expect(await library.findByText("checking")).toBeInTheDocument();
  await waitFor(() => expect(library.getByText("ready")).toBeInTheDocument(), { timeout: 4000 });
});

test("no model name, prompt, token or cost text appears on the page", async () => {
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [wohnen] };
    if (call === "GET /models") return { body: [{ ...armchair, state: "ready" }] };
  });
  show();
  await screen.findByRole("region", { name: "Wohnen" });
  const text = document.body.textContent ?? "";
  for (const word of [/deepseek/i, /prompt/i, /token/i, /€|eur\b/i, /\bcost/i]) {
    expect(text).not.toMatch(word);
  }
});

const hall = {
  name: "Hall", width_mm: 3000, depth_mm: 2000, corners: 4, height_mm: 2500, openings: 1, apartment: null,
  pieces: [{ package_id: "hall-bench", name: "Hall bench" }], conversations: 1,
  composition: { slug: "hall", versions: [1, 2] },
};
const kueche = { ...hall, name: "Küche", apartment: "Wohnung", pieces: [], conversations: 0, composition: null };

function serveRooms(rooms: unknown[], extra: (call: string) => { status?: number; body?: unknown } | undefined = () => undefined) {
  return stubFetch((call) => {
    const mine = extra(call);
    if (mine) return mine;
    if (call === "GET /rooms") return { body: rooms };
    if (call === "GET /compositions") return { body: [] };
    if (call === "GET /models") return { body: [] };
  });
}

test("a measured room is listed with its size, ceiling, openings and pieces", async () => {
  serveRooms([hall]);
  show();
  const card = within(await screen.findByRole("region", { name: "Measured room Hall" }));
  expect(card.getByText("3000 × 2000 mm, ceiling 2500 mm, 1 opening")).toBeInTheDocument();
  expect(card.getByText("Pieces: Hall bench")).toBeInTheDocument();
  expect(card.getByText("composed")).toBeInTheDocument();
});

test("delete warns first, and cancel sends nothing", async () => {
  const user = userEvent.setup();
  const calls = serveRooms([hall]);
  show();
  await user.click(await screen.findByRole("button", { name: "Delete Hall" }));
  const warning = within(screen.getByRole("group", { name: "Delete Hall?" }));
  expect(warning.getByText(/Hall bench will have no room/)).toBeInTheDocument();
  expect(warning.getByText(/1 conversation will need to confirm a room again/)).toBeInTheDocument();
  expect(warning.getByText(/its composition and 2 versions will be removed/)).toBeInTheDocument();
  await user.click(warning.getByRole("button", { name: "Cancel" }));
  expect(calls.some(([method]) => method === "DELETE")).toBe(false);
  expect(screen.getByRole("region", { name: "Measured room Hall" })).toBeInTheDocument();
});

test("a confirmed delete removes the room and refreshes the lists", async () => {
  const user = userEvent.setup();
  let rooms: unknown[] = [hall];
  const calls = serveRooms([], (call) => {
    if (call === "GET /rooms") return { body: rooms };
    if (call === "DELETE /rooms/Hall") {
      rooms = [];
      return { status: 204 };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Delete Hall" }));
  await user.click(screen.getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(screen.queryByRole("region", { name: "Measured room Hall" })).toBeNull());
  expect(calls.filter(([method]) => method === "DELETE").map(([, url]) => url)).toEqual(["/rooms/Hall"]);
  expect(calls.filter(([, url]) => url === "/compositions").length).toBeGreaterThan(1);
});

test("a room in an apartment shows why it cannot be deleted instead of the action", async () => {
  serveRooms([kueche]);
  show();
  const card = within(await screen.findByRole("region", { name: "Measured room Küche" }));
  expect(card.getByText("Küche belongs to the apartment Wohnung; it cannot be deleted on its own yet.")).toBeInTheDocument();
  expect(card.queryByRole("button", { name: /Delete/ })).toBeNull();
});

test("a refused delete is shown next to the room, which stays", async () => {
  const user = userEvent.setup();
  serveRooms([hall], (call) => {
    if (call === "DELETE /rooms/Hall") {
      return { status: 409, body: { detail: { failure_class: "room_in_use", reason: "the composition of Hall is building or rendering; delete it once that has finished" } } };
    }
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Delete Hall" }));
  await user.click(screen.getByRole("button", { name: "Delete" }));
  const refusal = await screen.findByText("the composition of Hall is building or rendering; delete it once that has finished");
  expect(refusal.closest("section")).toHaveAccessibleName("Measured room Hall");
});

test("an empty composition says it is the room only", async () => {
  serveRooms([], (call) => {
    if (call === "GET /compositions") return { body: [{ ...wohnen, items: [] }] };
  });
  show();
  const card = within(await screen.findByRole("region", { name: "Wohnen" }));
  expect(card.getByText("The room only, no furniture.")).toBeInTheDocument();
  expect(card.getByRole("link", { name: "Open the turntable viewer of Wohnen" })).toBeInTheDocument();
});


// --- rooms in 3D (app-check-2026-10-09) ----------------------------------------------------

const SURFACES = {
  "wall 1": ["Wall_0_0"], "wall 2": ["Wall_1_0", "Wall_1_lintel_0"], "wall 3": ["Wall_2_0"], "wall 4": ["Wall_3_0"],
  floor: ["Floor"], ceiling: ["Ceiling"], items: ["STAND_sofa"],
};
const modelled = {
  ...wohnen,
  model: "/compositions/wohnen/versions/2/files/model.glb",
  surfaces: "/compositions/wohnen/versions/2/files/report.json",
};

function serve3d() {
  return stubFetch((call) => {
    if (call === "GET /compositions") return { body: [modelled] };
    if (call === "GET /models") return { body: [] };
    if (call === "GET /compositions/wohnen/versions/2/files/report.json")
      return { body: { surfaces: SURFACES, extent_mm: { min: [0, 0, 0], max: [5000, 4000, 2600] } } };
  });
}

async function canvasProps() {
  const canvas = await screen.findByTestId("canvas");
  return JSON.parse(canvas.dataset.props ?? "{}") as Record<string, unknown>;
}

test("a composition with a model opens in 3D from Iso with the ceiling off", async () => {
  const user = userEvent.setup();
  const calls = serve3d();
  show();
  const card = within(await screen.findByRole("region", { name: "Wohnen" }));
  expect(calls.some(([, url]) => url.endsWith("report.json"))).toBe(false);
  await user.click(card.getByRole("button", { name: "Open the 3D view of Wohnen" }));
  const switches = within(await card.findByRole("group", { name: "Surfaces" }));
  expect(switches.getAllByRole("button").map((b) => b.textContent)).toEqual([
    "All walls", "wall 1", "wall 2", "wall 3", "wall 4", "floor", "ceiling", "items",
  ]);
  expect(switches.getByRole("button", { name: "ceiling" })).toHaveAttribute("aria-pressed", "false");
  expect(switches.getByRole("button", { name: "All walls" })).toHaveAttribute("aria-pressed", "true");
  const props = await canvasProps();
  expect(props).toMatchObject({ url: modelled.model, camera: "iso", mode: "workshop", layers: { ceiling: false, dimensions: false } });
  expect(props.spec).toEqual({ overall: { w: 5000, h: 2600, d: 4000 }, layers: SURFACES });
  expect(props.offset).toEqual([-2.5, 0, 2]);
  expect(props.isoDirection).toEqual([2.7, 3.6, 3.25]);
});

test("switching wall 2 off hides only wall 2, and All walls switches every wall", async () => {
  const user = userEvent.setup();
  serve3d();
  show();
  const card = within(await screen.findByRole("region", { name: "Wohnen" }));
  await user.click(card.getByRole("button", { name: "Open the 3D view of Wohnen" }));
  const switches = within(await card.findByRole("group", { name: "Surfaces" }));
  await user.click(switches.getByRole("button", { name: "wall 2" }));
  expect((await canvasProps()).layers).toEqual({ ceiling: false, "wall 2": false, dimensions: false });
  expect(switches.getByRole("button", { name: "All walls" })).toHaveAttribute("aria-pressed", "false");

  await user.click(switches.getByRole("button", { name: "All walls" }));
  expect((await canvasProps()).layers).toMatchObject({ "wall 1": true, "wall 2": true, "wall 3": true, "wall 4": true });
  await user.click(switches.getByRole("button", { name: "All walls" }));
  expect((await canvasProps()).layers).toMatchObject({
    "wall 1": false, "wall 2": false, "wall 3": false, "wall 4": false, ceiling: false,
  });
});

test("an older composition without a model shows its picture and says how to get the 3D view", async () => {
  stubFetch((call) => {
    if (call === "GET /compositions")
      return { body: [{ ...wohnen, name: "Hall", slug: "hall", latest_version: 1, model: null, surfaces: null }] };
    if (call === "GET /models") return { body: [] };
  });
  show();
  const card = within(await screen.findByRole("region", { name: "Hall" }));
  expect(card.getByRole("img")).toHaveAttribute("src", wohnen.picture);
  expect(card.getByText("Composing Hall again adds the 3D view.")).toBeInTheDocument();
  expect(card.queryByRole("button", { name: /3D view/ })).not.toBeInTheDocument();
});
