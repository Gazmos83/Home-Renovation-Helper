import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Rooms from "./Rooms";

// No WebGL in jsdom: the 3D stage is a stub that shows the props it is given.
// The dimensions overlay is a React element: its own props are shown apart (project-room-inspection).
vi.mock("@/components/inspector/InspectorCanvas", () => ({
  default: ({ overlay, ...props }: Record<string, unknown>) => (
    <div
      data-testid="canvas"
      data-props={JSON.stringify(props)}
      data-overlay={overlay ? JSON.stringify((overlay as { props: unknown }).props) : ""}
    />
  ),
}));

const wohnen = {
  scope: "room", name: "Wohnen", slug: "wohnen", latest_version: 2, status: "succeeded",
  items: [
    { id: "wall", type: "piece", name: "listening-wall v4", version: 4, approved: false, no_longer_approved: true },
    { id: "sofa", type: "stand-in", name: "Sofa" },
  ],
  picture: "/compositions/wohnen/versions/2/files/screenshot.png" as string | null,
  viewer: "/compositions/wohnen/versions/2/files/viewer.html" as string | null,
};

function Address() {
  const location = useLocation();
  return <output aria-label="address">{location.pathname + location.search}</output>;
}

/** The Measured Rooms tab at `path`: the grid, or a room's or composition's dialog (studio-tile-grid). */
function show(path = "/studio/rooms") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/studio/:tab/*" element={<Rooms />} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const address = () => screen.getByRole("status", { name: "address", hidden: true }).textContent;

test("a placed piece that is no longer approved is marked plainly", async () => {
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [wohnen] };
  });
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  expect(card.getByText("listening-wall v4").closest("li")).toHaveTextContent("no longer approved");
  expect(card.getByText("Sofa").closest("li")).not.toHaveTextContent("no longer approved");
  expect(card.getByRole("img")).toHaveAttribute("src", wohnen.picture);
});

test("no model library, model name, prompt, token or cost text appears on the page", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /compositions") return { body: [wohnen] };
  });
  show("/studio/rooms/compositions/wohnen");
  await screen.findByRole("dialog", { name: "Wohnen" });
  expect(calls.map(([, url]) => url)).not.toContain("/models");
  expect(screen.queryByText(/model library/i)).toBeNull();
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
  });
}

test("a measured room's size, ceiling, openings and pieces open from its Room brief button", async () => {
  const user = userEvent.setup();
  serveRooms([hall]);
  show("/studio/rooms/Hall");
  const card = within(await screen.findByRole("dialog", { name: "Hall" }));
  expect(card.getByRole("heading", { level: 2, name: "Hall" })).toBeInTheDocument();
  expect(card.queryByText("3000 × 2000 mm, ceiling 2500 mm, 1 opening")).toBeNull();
  await user.click(card.getByRole("button", { name: "Room brief" }));
  const brief = within(await screen.findByRole("dialog", { name: "Hall brief" }));
  expect(brief.getByText("3000 × 2000 mm, ceiling 2500 mm, 1 opening")).toBeInTheDocument();
  const rows = within(brief.getByRole("table", { name: "Pieces in Hall" })).getAllByRole("row");
  expect(rows.map((r) => r.textContent)).toEqual(["PieceID", "Hall benchhall-bench"]);
});

test("a room brief without pieces says so", async () => {
  const user = userEvent.setup();
  serveRooms([{ ...hall, pieces: [] }]);
  show("/studio/rooms/Hall");
  const card = within(await screen.findByRole("dialog", { name: "Hall" }));
  await user.click(card.getByRole("button", { name: "Room brief" }));
  const brief = within(await screen.findByRole("dialog", { name: "Hall brief" }));
  expect(brief.getByText("No pieces in this room.")).toBeInTheDocument();
  expect(brief.queryByRole("table")).toBeNull();
});

test("a room without a composition says so and how to get one", async () => {
  serveRooms([{ ...hall, composition: null }]);
  show("/studio/rooms/Hall");
  const card = within(await screen.findByRole("dialog", { name: "Hall" }));
  expect(await card.findByText("No composition yet. Ask the Designer in a conversation to compose Hall.")).toBeInTheDocument();
});

test("a room's composition is shown inside its dialog, not on a tile of its own", async () => {
  const wohnenRoom = { ...hall, name: "Wohnen", pieces: [], composition: { slug: "wohnen", versions: [2] } };
  serveRooms([wohnenRoom], (call) => (call === "GET /compositions" ? { body: [wohnen] } : undefined));
  show("/studio/rooms/Wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  const composition = within(await card.findByRole("group", { name: "Wohnen" }));
  expect(composition.getByRole("heading", { level: 3, name: "Composition" })).toBeInTheDocument();
  expect(composition.getByText("listening-wall v4")).toBeInTheDocument();
  expect(composition.getByRole("img")).toHaveAttribute("src", wohnen.picture);
  expect(screen.getAllByRole("button", { name: "Wohnen", hidden: true })).toHaveLength(1);
  expect(card.queryByText(/No composition yet/)).toBeNull();
});

test("an apartment composition has a tile of its own after the rooms (Apartment composition on its own card)", async () => {
  const user = userEvent.setup();
  const wohnung = { ...wohnen, scope: "apartment", name: "Wohnung", slug: "wohnung" };
  serveRooms([kueche], (call) => (call === "GET /compositions" ? { body: [wohnung] } : undefined));
  show();
  const tile = await screen.findByRole("button", { name: "Wohnung" });
  expect(within(tile).getByText("Apartment")).toBeInTheDocument();
  const room = screen.getByRole("button", { name: "Küche" });
  expect(within(room).getByText("Wohnung")).toBeInTheDocument();
  expect(room.compareDocumentPosition(tile) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  await user.click(tile);
  expect(address()).toBe("/studio/rooms/compositions/wohnung");
  expect(within(await screen.findByRole("dialog", { name: "Wohnung" })).getByText("Apartment")).toBeInTheDocument();
});

test("each room is a tile with its composition's picture and its size", async () => {
  const wohnenRoom = { ...hall, name: "Wohnen", pieces: [], composition: { slug: "wohnen", versions: [2] } };
  serveRooms([wohnenRoom, { ...hall, composition: null }], (call) => (call === "GET /compositions" ? { body: [wohnen] } : undefined));
  show();
  const tile = await screen.findByRole("button", { name: "Wohnen" });
  expect(tile).toHaveTextContent("3000 × 2000 mm, ceiling 2500 mm");
  await waitFor(() => expect(tile.querySelector("img")).toHaveAttribute("src", wohnen.picture));
  expect(within(screen.getByRole("button", { name: "Hall" })).getByTestId("tile-placeholder")).toBeInTheDocument();
});

test("an address naming no room shows the grid and no dialog", async () => {
  serveRooms([hall]);
  show("/studio/rooms/Bad");
  expect(await screen.findByRole("button", { name: "Hall" })).toBeInTheDocument();
  await waitFor(() => expect(address()).toBe("/studio/rooms"));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("with no rooms the page says none are measured yet", async () => {
  serveRooms([]);
  show();
  expect(await screen.findByText("No rooms measured yet. Describe one in a conversation.")).toBeInTheDocument();
});

test("delete warns first, and cancel sends nothing", async () => {
  const user = userEvent.setup();
  const calls = serveRooms([hall]);
  show("/studio/rooms/Hall");
  await user.click(await screen.findByRole("button", { name: "Delete Hall" }));
  const warning = within(screen.getByRole("group", { name: "Delete Hall?" }));
  expect(warning.getByText(/Hall bench will have no room/)).toBeInTheDocument();
  expect(warning.getByText(/1 conversation will need to confirm a room again/)).toBeInTheDocument();
  expect(warning.getByText(/its composition and 2 versions will be removed/)).toBeInTheDocument();
  await user.click(warning.getByRole("button", { name: "Cancel" }));
  expect(calls.some(([method]) => method === "DELETE")).toBe(false);
  expect(screen.getByRole("dialog", { name: "Hall" })).toBeInTheDocument();
});

test("a confirmed delete closes the dialog, removes the tile and refreshes the lists (Delete confirmed)", async () => {
  const user = userEvent.setup();
  let rooms: unknown[] = [hall];
  const calls = serveRooms([], (call) => {
    if (call === "GET /rooms") return { body: rooms };
    if (call === "DELETE /rooms/Hall") {
      rooms = [];
      return { status: 204 };
    }
  });
  show("/studio/rooms/Hall");
  await user.click(await screen.findByRole("button", { name: "Delete Hall" }));
  await user.click(screen.getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.queryByRole("button", { name: "Hall" })).toBeNull();
  expect(address()).toBe("/studio/rooms");
  expect(calls.filter(([method]) => method === "DELETE").map(([, url]) => url)).toEqual(["/rooms/Hall"]);
  expect(calls.filter(([, url]) => url === "/compositions").length).toBeGreaterThan(1);
});

test("a room in an apartment shows why it cannot be deleted instead of the action", async () => {
  serveRooms([kueche]);
  show("/studio/rooms/Küche");
  const card = within(await screen.findByRole("dialog", { name: "Küche" }));
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
  show("/studio/rooms/Hall");
  await user.click(await screen.findByRole("button", { name: "Delete Hall" }));
  await user.click(screen.getByRole("button", { name: "Delete" }));
  const refusal = await screen.findByText("the composition of Hall is building or rendering; delete it once that has finished");
  expect(refusal.closest('[role="dialog"]')).toHaveAccessibleName("Hall");
});

test("an empty composition says it is the room only", async () => {
  serveRooms([], (call) => {
    if (call === "GET /compositions") return { body: [{ ...wohnen, items: [] }] };
  });
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  expect(card.getByText("The room only, no furniture.")).toBeInTheDocument();
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
    if (call === "GET /compositions/wohnen/versions/2/files/report.json")
      return { body: { surfaces: SURFACES, extent_mm: { min: [0, 0, 0], max: [5000, 4000, 2600] } } };
  });
}

test("the turntable viewer is offered only in the open 3D view (Turntable viewer only in the 3D view)", async () => {
  const user = userEvent.setup();
  serve3d();
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  expect(card.queryByRole("link", { name: "Open the turntable viewer of Wohnen" })).not.toBeInTheDocument();
  await user.click(card.getByRole("button", { name: "Open the 3D view of Wohnen" }));
  expect(await card.findByRole("link", { name: "Open the turntable viewer of Wohnen" })).toHaveAttribute("href", wohnen.viewer);
});

async function canvasProps() {
  const canvas = await screen.findByTestId("canvas");
  return JSON.parse(canvas.dataset.props ?? "{}") as Record<string, unknown>;
}

test("a composition with a model opens in 3D from Iso with the ceiling off", async () => {
  const user = userEvent.setup();
  const calls = serve3d();
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  expect(calls.some(([, url]) => url.endsWith("report.json"))).toBe(false);
  await user.click(card.getByRole("button", { name: "Open the 3D view of Wohnen" }));
  const switches = within(await card.findByRole("group", { name: "Surfaces" }));
  expect(switches.getAllByRole("button").map((b) => b.textContent)).toEqual([
    "All walls", "wall 1", "wall 2", "wall 3", "wall 4", "floor", "ceiling",
  ]);
  const furniture = within(card.getByRole("group", { name: "Furniture" }));
  expect(furniture.getAllByRole("button").map((b) => b.textContent)).toEqual(["items"]);
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
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
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

test("the 3D controls sit in open Views, Room and Furniture sections (Room controls grouped)", async () => {
  serve3d();
  const { card } = await openItems();
  const sections = [...card.getByRole("group", { name: "Camera" }).closest("[data-role=stage-column]")!.querySelectorAll("details")];
  expect(sections.map((d) => d.querySelector("summary")?.textContent)).toEqual(["Views", "Room", "Furniture"]);
  sections.forEach((d) => expect(d).toHaveAttribute("open"));
  const views = within(sections[0]);
  expect(views.getAllByRole("button").map((b) => b.textContent)).toEqual(["Iso", "Front", "Side", "Plan", "Workshop", "Blueprint"]);
});

test("a wall switched off stays off while Room is folded (Folding keeps switches)", async () => {
  serve3d();
  const { user, card } = await openItems();
  const surfaces = card.getByRole("group", { name: "Surfaces" });
  await user.click(within(surfaces).getByRole("button", { name: "wall 2" }));
  const room = surfaces.closest("details")!;
  await user.click(room.querySelector("summary")!);
  expect(room).not.toHaveAttribute("open");
  expect((await canvasProps()).layers).toEqual({ ceiling: false, "wall 2": false, dimensions: false });
  await user.click(room.querySelector("summary")!);
  expect(within(surfaces).getByRole("button", { name: "wall 2" })).toHaveAttribute("aria-pressed", "false");
});

test("a room without items shows no Furniture section (Room without items)", async () => {
  const { items: _items, ...bare } = SURFACES;
  serveItems({ surfaces: bare, extent_mm: { min: [0, 0, 0], max: [5000, 4000, 2600] }, items: [] });
  const user = userEvent.setup();
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  await user.click(card.getByRole("button", { name: "Open the 3D view of Wohnen" }));
  await card.findByRole("group", { name: "Surfaces" });
  expect(card.queryByRole("group", { name: "Furniture" })).not.toBeInTheDocument();
  expect(card.queryByText("Furniture")).not.toBeInTheDocument();
});

function serveItems(report: unknown) {
  return stubFetch((call) => {
    if (call === "GET /compositions") return { body: [modelled] };
    if (call === "GET /compositions/wohnen/versions/2/files/report.json") return { body: report };
  });
}

async function openItems() {
  const user = userEvent.setup();
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  await user.click(card.getByRole("button", { name: "Open the 3D view of Wohnen" }));
  await card.findByRole("group", { name: "Surfaces" });
  return { user, card, switches: within(card.getByRole("group", { name: "Furniture" })) };
}

test("an older composition without a model shows its picture and says how to get the 3D view", async () => {
  stubFetch((call) => {
    if (call === "GET /compositions")
      return { body: [{ ...wohnen, name: "Hall", slug: "hall", latest_version: 1, model: null, surfaces: null }] };
  });
  show("/studio/rooms/compositions/hall");
  const card = within(await screen.findByRole("dialog", { name: "Hall" }));
  expect(card.getByRole("img")).toHaveAttribute("src", wohnen.picture);
  expect(card.getByText("Composing Hall again adds the 3D view.")).toBeInTheDocument();
  expect(card.queryByRole("button", { name: /3D view/ })).not.toBeInTheDocument();
});

// --- versions and dimensions (project-room-inspection) --------------------------------------

const view = (version: number, extra: Record<string, unknown> = {}) => ({
  version, status: "succeeded", viewer: null as string | null, items: [] as unknown[],
  picture: `/compositions/wohnen/versions/${version}/files/screenshot.png` as string | null,
  model: `/compositions/wohnen/versions/${version}/files/model.glb` as string | null,
  surfaces: `/compositions/wohnen/versions/${version}/files/report.json` as string | null,
  dimensions: `/compositions/wohnen/versions/${version}/dimensions` as string | null,
  approved_at: null as string | null,
  ...extra,
});
const DIMENSIONS = {
  walls: [
    { label: "wall 1", from: [0, 0], to: [6200, 0], length_mm: 6200 },
    { label: "wall 2", from: [6200, 0], to: [6200, 5700], length_mm: 5700 },
  ],
  ceilings: [{ room: "Wohnen", height_mm: 2500, at: [3100, 2850] }],
};
const versioned = {
  ...modelled,
  latest_version: 7,
  version_views: [7, 6, 5, 4, 3].map((n) =>
    view(n, n === 5 ? { items: [{ id: "sofa", type: "stand-in", name: "Sofa" }], status: "failed", model: null, surfaces: null, dimensions: null } : {}),
  ),
};

function serveVersions() {
  return stubFetch((call) => {
    if (call === "GET /compositions") return { body: [versioned] };
    if (/^GET \/compositions\/wohnen\/versions\/\d\/files\/report\.json$/.test(call))
      return { body: { surfaces: SURFACES, extent_mm: { min: [0, 0, 0], max: [6200, 6064, 2500] } } };
    if (/^GET \/compositions\/wohnen\/versions\/\d\/dimensions$/.test(call)) return { body: DIMENSIONS };
  });
}

test("the version dropdown lists the newest five and the card follows the chosen one", async () => {
  const user = userEvent.setup();
  serveVersions();
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  const select = card.getByRole("combobox", { name: "Version of Wohnen" });
  expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([
    "Version 7", "Version 6", "Version 5", "Version 4", "Version 3",
  ]);
  expect(select).toHaveValue("7");
  expect(card.getByRole("img")).toHaveAttribute("src", "/compositions/wohnen/versions/7/files/screenshot.png");
  expect(card.getByText("The room only, no furniture.")).toBeInTheDocument();

  await user.click(card.getByRole("button", { name: "Open the 3D view of Wohnen" }));
  expect((await canvasProps()).url).toBe("/compositions/wohnen/versions/7/files/model.glb");
  await user.selectOptions(select, "6");
  await waitFor(async () => expect((await canvasProps()).url).toBe("/compositions/wohnen/versions/6/files/model.glb"));

  await user.selectOptions(select, "5");
  expect(card.getByText("failed")).toBeInTheDocument();
  expect(card.getByText("Sofa")).toBeInTheDocument();
  expect(card.getByRole("img")).toHaveAttribute("src", "/compositions/wohnen/versions/5/files/screenshot.png");
  expect(card.queryByTestId("canvas")).not.toBeInTheDocument();
});

test("a built room version offers its Blender file, model and picture for download", async () => {
  const user = userEvent.setup();
  const withBlend = {
    ...versioned,
    version_views: versioned.version_views.map((v) =>
      v.version === 7 ? { ...v, blend: "/compositions/wohnen/versions/7/files/model.blend" } : v,
    ),
  };
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: [withBlend] };
  });
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  const panel = within(card.getByRole("region", { name: "Download the room (version 7)" }));
  const blend = panel.getByRole("link", { name: "Download Blender file (version 7)" });
  expect(blend).toHaveAttribute("href", "/compositions/wohnen/versions/7/files/model.blend");
  expect(blend).toHaveAttribute("download", "wohnen-v7.blend");
  expect(panel.getByRole("link", { name: "Download glTF model (version 7)" })).toHaveAttribute("download", "wohnen-v7.glb");
  expect(panel.getByRole("link", { name: "Download Screenshot (version 7)" })).toHaveAttribute(
    "href", "/compositions/wohnen/versions/7/files/screenshot.png",
  );

  await user.selectOptions(card.getByRole("combobox", { name: "Version of Wohnen" }), "6");
  expect(card.queryByRole("link", { name: /Download Blender file/ })).toBeNull();
  expect(card.getByRole("link", { name: "Download glTF model (version 6)" })).toBeInTheDocument();

  await user.selectOptions(card.getByRole("combobox", { name: "Version of Wohnen" }), "5");
  expect(card.queryByRole("region", { name: /Download the room/ })).toBeNull();
});

test("dimensions are read only when switched on and label the chosen version", async () => {
  const user = userEvent.setup();
  const calls = serveVersions();
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  await user.click(card.getByRole("button", { name: "Open the 3D view of Wohnen" }));
  const toggle = await card.findByRole("button", { name: "dimensions" });
  expect(toggle).toHaveAttribute("aria-pressed", "false");
  expect((await screen.findByTestId("canvas")).dataset.overlay).toBe("");
  expect(calls.some(([, url]) => url.endsWith("/dimensions"))).toBe(false);

  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-pressed", "true");
  await waitFor(() => expect(screen.getByTestId("canvas").dataset.overlay).not.toBe(""));
  const overlay = JSON.parse(screen.getByTestId("canvas").dataset.overlay ?? "{}");
  expect(overlay).toEqual({ dimensions: DIMENSIONS, apartment: false });
  expect(calls.some(([, url]) => url === "/compositions/wohnen/versions/7/dimensions")).toBe(true);
});


// --- room-version-approval ------------------------------------------------------------------

function composed(extra: Record<string, unknown> = {}) {
  return {
    ...wohnen,
    versions: [2, 1],
    approved_version: null as number | null,
    version_views: [
      view(2, { items: wohnen.items, picture: wohnen.picture, viewer: wohnen.viewer, approved_at: null }),
      view(1, {
        items: [],
        picture: null,
        viewer: null,
        model: null,
        surfaces: null,
        dimensions: null,
        approved_at: null,
      }),
    ],
    ...extra,
  };
}

function serveComposed(
  initial: ReturnType<typeof composed>,
  extra: (call: string) => { status?: number; body?: unknown } | undefined = () => undefined,
) {
  let listed = initial;
  const calls = stubFetch((call) => {
    const mine = extra(call);
    if (mine) return mine;
    if (call === "GET /compositions") return { body: [listed] };
    if (call === "GET /rooms") return { body: [] };
    const change = /^(PUT|DELETE) \/compositions\/wohnen\/versions\/(\d+)\/approval$/.exec(call);
    if (change) {
      const version = Number(change[2]);
      const approved_at = change[1] === "PUT" ? "2026-10-10T00:00:00Z" : null;
      listed = {
        ...listed,
        approved_version: change[1] === "PUT" ? version : null,
        version_views: listed.version_views.map((v) => ({
          ...v,
          approved_at: v.version === version ? approved_at : change[1] === "PUT" ? null : v.approved_at,
        })),
      };
      return { body: { slug: "wohnen", version, status: "succeeded", approved_at } };
    }
  });
  return { calls, setListed: (next: typeof listed) => { listed = next; } };
}

test("a built room version is approved from the page and the badge shows without a reload", async () => {
  const user = userEvent.setup();
  const { calls } = serveComposed(composed());
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  await user.click(await card.findByRole("button", { name: "Approve version 2" }));
  expect(await card.findByRole("button", { name: "Unapprove version 2" })).toBeInTheDocument();
  expect(card.getByText("Approved")).toBeInTheDocument();
  expect(card.queryByRole("button", { name: "Delete version 2" })).toBeNull();
  expect(calls.some(([m, u]) => m === "PUT" && u === "/compositions/wohnen/versions/2/approval")).toBe(true);
});

test("an approved room version is unapproved and the page shows no approved version", async () => {
  const user = userEvent.setup();
  const { calls } = serveComposed(
    composed({
      approved_version: 2,
      version_views: [
        view(2, { items: wohnen.items, picture: wohnen.picture, viewer: wohnen.viewer, approved_at: "2026-10-10T00:00:00Z" }),
        view(1, { items: [], picture: null, viewer: null, model: null, surfaces: null, dimensions: null, approved_at: null }),
      ],
    }),
  );
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  expect(card.getByText("Approved")).toBeInTheDocument();
  expect(card.queryByRole("button", { name: "Delete version 2" })).toBeNull();
  await user.click(card.getByRole("button", { name: "Unapprove version 2" }));
  expect(await card.findByRole("button", { name: "Approve version 2" })).toBeInTheDocument();
  expect(card.queryByText("Approved")).toBeNull();
  expect(calls.some(([m]) => m === "DELETE")).toBe(true);
});

test("delete asks first, and cancel sends nothing", async () => {
  const user = userEvent.setup();
  const { calls } = serveComposed(composed());
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  await user.click(await card.findByRole("button", { name: "Delete version 2" }));
  expect(card.getByText("Are you sure? Version 2 and its model and renders will be deleted. This cannot be undone.")).toBeInTheDocument();
  await user.click(card.getByRole("button", { name: "Cancel" }));
  expect(card.getByRole("button", { name: "Delete version 2" })).toBeInTheDocument();
  expect(card.queryByText(/Are you sure/)).not.toBeInTheDocument();
  expect(calls.filter(([m]) => m === "DELETE")).toEqual([]);
});

test("a confirmed delete removes the version and the page shows another", async () => {
  const user = userEvent.setup();
  let listed = composed();
  stubFetch((call) => {
    if (call === "GET /compositions") return { body: listed.versions.length ? [listed] : [] };
    if (call === "GET /rooms") return { body: [] };
    if (call === "DELETE /compositions/wohnen/versions/2") {
      listed = {
        ...listed,
        latest_version: 1,
        versions: [1],
        version_views: [listed.version_views[1]],
        picture: null,
        viewer: null,
      };
      return { status: 204 };
    }
  });
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  await user.click(await card.findByRole("button", { name: "Delete version 2" }));
  await user.click(card.getByRole("button", { name: "Yes, delete version 2" }));
  await waitFor(() => expect(card.getByRole("combobox", { name: "Version of Wohnen" })).toHaveValue("1"));
  expect(card.queryByRole("option", { name: "Version 2" })).toBeNull();
});

test("an approved version has no delete control", async () => {
  serveComposed(
    composed({
      approved_version: 2,
      version_views: [
        view(2, { items: wohnen.items, picture: wohnen.picture, viewer: wohnen.viewer, approved_at: "2026-10-10T00:00:00Z" }),
        view(1, { items: [], picture: null, viewer: null, model: null, surfaces: null, dimensions: null, approved_at: null }),
      ],
    }),
  );
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  expect(await card.findByRole("button", { name: "Unapprove version 2" })).toBeInTheDocument();
  expect(card.queryByRole("button", { name: "Delete version 2" })).toBeNull();
});

test("an approval refusal is shown next to the version it names", async () => {
  const user = userEvent.setup();
  serveComposed(composed(), (call) => {
    if (call === "PUT /compositions/wohnen/versions/2/approval") {
      return {
        status: 409,
        body: {
          detail: {
            failure_class: "unapproved_pieces",
            reason: "Wohnen version 2 places listening-wall v4, which is not approved; approve those piece versions first",
          },
        },
      };
    }
  });
  show("/studio/rooms/compositions/wohnen");
  const card = within(await screen.findByRole("dialog", { name: "Wohnen" }));
  await user.click(await card.findByRole("button", { name: "Approve version 2" }));
  const refusal = await card.findByRole("alert");
  expect(refusal).toHaveTextContent("listening-wall v4");
  expect(refusal.closest("[role=group]")).toHaveAccessibleName("Approval of Wohnen version 2");
  expect(card.getByRole("button", { name: "Approve version 2" })).toBeEnabled();
});
