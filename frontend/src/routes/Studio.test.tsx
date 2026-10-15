import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { setScreenWidth } from "../test/media";
import Studio from "./Studio";

afterEach(() => window.localStorage.clear());

function Address() {
  const location = useLocation();
  return <output aria-label="address">{location.pathname + location.search}</output>;
}

function show(path: string, dev = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/studio" element={<Studio dev={dev} />} />
          <Route path="/studio/:tab/*" element={<Studio dev={dev} />} />
          <Route path="/admin/agents" element={<Studio dev fixedTab="agents" />} />
          <Route path="/admin/agents/:tab" element={<Studio dev fixedTab="agents" />} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function stubAll() {
  return stubFetch((call) => {
    if (call === "GET /packages") return { body: [] };
    if (call === "GET /rooms") return { body: [] };
    if (call === "GET /compositions") return { body: [] };
    if (call === "GET /models") return { body: [] };
    if (call.startsWith("GET /price-list")) return { body: [] };
    if (call === "GET /snapshots") return { body: [] };
    if (call === "GET /remnants") return { body: [] };
    if (call === "GET /admin/memory") return { body: memory };
  });
}

const memoryDefaults = {
  trigger_percent: 100, keep_turns: 0, note_tokens: 400, note_instructions: "You keep the notes.", tool_result_chars: 300,
  reviews: "auto", save_preferences: true, other_builds: "line", include_preferences: true,
  include_review_items: true, render_ratings: 5, include_extension_requests: true,
};
const memory = { settings: memoryDefaults, defaults: memoryDefaults, fixed_rules: ["Generator-extension requests are always saved."] };

const AGENT_LABELS = [
  "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins", "Models and Routing",
];

test("the page opens on the Pieces tab", async () => {
  stubAll();
  show("/studio");
  expect(screen.getByRole("heading", { level: 1, name: "Design Studio" })).toBeInTheDocument();
  const tabs = screen.getAllByRole("tab").map((tab) => tab.getAttribute("aria-label"));
  expect(tabs).toEqual(["Workspace", "Pieces", "Measured Rooms", "Model Library", "Pricing"]);
  expect(screen.getByRole("tab", { name: "Pieces" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByRole("button", { name: "Create A New Piece" })).toBeInTheDocument();
  const [column] = screen.getAllByRole("navigation", { name: "Pieces" });
  expect(await within(column).findByText("No pieces yet")).toBeInTheDocument();
});

test("choosing a tab changes the address and shows only that tab", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/studio/pieces");
  await user.click(screen.getByRole("tab", { name: "Model Library" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/models");
  expect(screen.getByRole("tab", { name: "Model Library" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Pieces" })).toHaveAttribute("aria-selected", "false");
  expect(await screen.findByText(/No models yet/)).toBeInTheDocument();
  const [column] = screen.getAllByRole("navigation", { name: "Model Library views" });
  expect(within(column).getByRole("link", { name: "Uploaded models" })).toHaveAttribute("aria-current", "page");
  expect(within(column).getByRole("link", { name: "Upload model" })).toHaveAttribute("href", "/studio/models/upload");
  expect(screen.queryByRole("form", { name: "Upload a model" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Create A New Piece" })).not.toBeInTheDocument();
  expect(screen.queryByText(/No rooms measured yet/)).not.toBeInTheDocument();
});

test("a tab address opens that tab", async () => {
  stubAll();
  show("/studio/rooms");
  expect(screen.getByRole("tab", { name: "Measured Rooms" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByText(/No rooms measured yet/)).toBeInTheDocument();
});

test("an unknown tab opens Pieces", async () => {
  stubAll();
  show("/studio/quotes");
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/studio/pieces"));
  expect(screen.getByRole("tab", { name: "Pieces" })).toHaveAttribute("aria-selected", "true");
});

test("the tabs sit in a rail of icons that shows and hides its labels like the conversation's", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/studio/pieces");
  const list = screen.getByRole("tablist", { name: "Design Studio" });
  expect(list).toHaveAttribute("aria-orientation", "vertical");
  expect(within(list).queryByText("Model Library")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Show labels" }));
  expect(within(list).getByText("Model Library")).toBeInTheDocument();
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("true");
  await user.click(screen.getByRole("button", { name: "Hide labels" }));
  expect(within(list).queryByText("Model Library")).not.toBeInTheDocument();
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("false");
});

test("the labels follow the choice made on another rail", () => {
  window.localStorage.setItem("studio.rail.expanded", "true");
  stubAll();
  show("/studio/models");
  const list = screen.getByRole("tablist", { name: "Design Studio" });
  expect(within(list).getByText("Measured Rooms")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Hide labels" })).toBeInTheDocument();
});

test("on a phone the rail stays and the sub-menu is a row above the tiles (Sub-menu on a phone)", async () => {
  setScreenWidth(360);
  stubAll();
  show("/studio/models");
  expect(screen.getByRole("tablist", { name: "Design Studio" })).toBeInTheDocument();
  const [, row] = screen.getAllByRole("navigation", { name: "Model Library views" });
  expect(within(row).getAllByRole("link").map((l) => l.textContent)).toEqual(["Uploaded models", "Upload model"]);
});

test("Upload model opens the upload dialog over the grid and is highlighted while open", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/studio/models?page=2");
  const [column] = screen.getAllByRole("navigation", { name: "Model Library views" });
  await user.click(within(column).getByRole("link", { name: "Upload model" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/models/upload?page=2");
  expect(await screen.findByRole("dialog", { name: "Upload a model" })).toBeInTheDocument();
  const [after] = screen.getAllByRole("navigation", { name: "Model Library views", hidden: true });
  expect(within(after).getByRole("link", { name: "Upload model", hidden: true })).toHaveAttribute("aria-current", "page");
  await user.keyboard("{Escape}");
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/models?page=2");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

// --- the sub-menu lists pieces and rooms by name (studio-submenu-names) ----------------------

const piece = (id: string) => ({ package_id: id, versions: [1], room: null, thread_id: null });
const room = (name: string, apartment: string | null = null) => ({
  name, width_mm: 3000, depth_mm: 2000, corners: 4, height_mm: 2500, openings: 1,
  apartment, pieces: [], conversations: 0, composition: null,
});
const wohnung = {
  scope: "apartment", name: "Wohnung", slug: "wohnung", latest_version: 1, status: "succeeded", items: [],
  picture: null, viewer: null,
};

function stubLists() {
  return stubFetch((call) => {
    if (call === "GET /packages") return { body: [piece("bench"), piece("hall-bench"), piece("shelf")] };
    if (/^GET \/packages\/[^/]+\/versions\/1$/.test(call)) return { body: { version: 1, status: "running", approved_at: null } };
    if (call === "GET /rooms") return { body: [room("Hall"), room("Küche", "Wohnung")] };
    if (call === "GET /compositions") return { body: [wohnung] };
    if (call === "GET /models") return { body: [] };
  });
}

const names = (nav: HTMLElement) => within(nav).getAllByRole("link", { hidden: true }).map((link) => link.textContent);

test("the Pieces sub-menu lists every piece by name and no All pieces entry (Pieces first, Pieces listed by name)", async () => {
  stubLists();
  show("/studio/pieces");
  const [column, row] = screen.getAllByRole("navigation", { name: "Pieces" });
  await waitFor(() => expect(names(column)).toEqual(["bench", "hall-bench", "shelf"]));
  expect(column).toHaveClass("md:flex", "hidden", "overflow-y-auto");
  expect(row).toHaveClass("md:hidden", "overflow-x-auto");
  expect(within(column).queryByRole("link", { name: "All pieces" })).toBeNull();
  expect(within(column).queryByRole("link", { current: "page" })).toBeNull();
  expect(await screen.findByRole("button", { name: "bench" })).toBeInTheDocument();
});

test("the Measured Rooms sub-menu lists the rooms, then the apartment (Rooms and apartment listed)", async () => {
  stubLists();
  show("/studio/rooms");
  const [column] = screen.getAllByRole("navigation", { name: "Measured Rooms" });
  await waitFor(() => expect(names(column)).toEqual(["Hall", "Küche", "Wohnung"]));
  expect(within(column).queryByRole("link", { name: "All rooms" })).toBeNull();
});

test("a name opens its dialog over the grid, keeps the page and is highlighted until closed (Name opens the dialog, Dialog closed)", async () => {
  const user = userEvent.setup();
  stubLists();
  show("/studio/pieces?page=2");
  const [column] = screen.getAllByRole("navigation", { name: "Pieces" });
  await user.click(await within(column).findByRole("link", { name: "shelf" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/pieces/shelf?page=2");
  expect(await screen.findByRole("dialog", { name: "shelf" })).toBeInTheDocument();
  const [open] = screen.getAllByRole("navigation", { name: "Pieces", hidden: true });
  expect(within(open).getByRole("link", { name: "shelf", hidden: true })).toHaveAttribute("aria-current", "page");
  expect(within(open).getByRole("link", { name: "bench", hidden: true })).not.toHaveAttribute("aria-current");
  await user.keyboard("{Escape}");
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/pieces?page=2");
  expect(screen.queryByRole("dialog")).toBeNull();
  const [closed] = screen.getAllByRole("navigation", { name: "Pieces" });
  expect(within(closed).queryByRole("link", { current: "page" })).toBeNull();
});

test("a composition's name opens its dialog (Composition name opens its dialog)", async () => {
  const user = userEvent.setup();
  stubLists();
  show("/studio/rooms");
  const [column] = screen.getAllByRole("navigation", { name: "Measured Rooms" });
  await user.click(await within(column).findByRole("link", { name: "Wohnung" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/rooms/compositions/wohnung");
  expect(await screen.findByRole("dialog", { name: "Wohnung" })).toBeInTheDocument();
  const [open] = screen.getAllByRole("navigation", { name: "Measured Rooms", hidden: true });
  expect(within(open).getByRole("link", { name: "Wohnung", hidden: true })).toHaveAttribute("aria-current", "page");
});

test("a room name with a special character opens its dialog", async () => {
  stubLists();
  show("/studio/rooms");
  const [column] = screen.getAllByRole("navigation", { name: "Measured Rooms" });
  expect(await within(column).findByRole("link", { name: "Küche" })).toHaveAttribute("href", "/studio/rooms/K%C3%BCche");
});

test("with no rooms the sub-menu says so", async () => {
  stubAll();
  show("/studio/rooms");
  const [column] = screen.getAllByRole("navigation", { name: "Measured Rooms" });
  expect(await within(column).findByText("No rooms yet")).toBeInTheDocument();
});

test("a deleted room leaves the sub-menu without a reload (Deleted room leaves the sub-menu)", async () => {
  const user = userEvent.setup();
  let listed = [room("Hall"), room("Bad")];
  stubFetch((call) => {
    if (call === "GET /rooms") return { body: listed };
    if (call === "GET /compositions") return { body: [] };
    if (call === "DELETE /rooms/Hall") {
      listed = [room("Bad")];
      return { status: 204 };
    }
  });
  show("/studio/rooms/Hall");
  await user.click(await screen.findByRole("button", { name: "Delete Hall" }));
  await user.click(screen.getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  const [column] = screen.getAllByRole("navigation", { name: "Measured Rooms" });
  await waitFor(() => expect(names(column)).toEqual(["Bad"]));
});

test("on a phone the names are one row that scrolls sideways (Names on a phone)", async () => {
  setScreenWidth(360);
  stubLists();
  show("/studio/pieces");
  const [, row] = screen.getAllByRole("navigation", { name: "Pieces" });
  await waitFor(() => expect(names(row)).toEqual(["bench", "hall-bench", "shelf"]));
  expect(row).toHaveClass("overflow-x-auto", "md:hidden");
  expect(row).not.toHaveClass("flex-col");
  expect(screen.getByRole("tablist", { name: "Design Studio" })).toBeInTheDocument();
});

test("the owner's rail has no divider and no AI & Agent Settings tab (Owner rail)", () => {
  stubAll();
  show("/studio/pieces");
  expect(screen.getAllByRole("tab").map((tab) => tab.getAttribute("aria-label"))).toEqual([
    "Workspace", "Pieces", "Measured Rooms", "Model Library", "Pricing",
  ]);
  expect(document.querySelector("[data-rail-divider]")).toBeNull();
});

test("the developer's rail ends with a divider and AI & Agent Settings (Developer rail)", () => {
  stubAll();
  show("/studio/pieces", true);
  const list = screen.getByRole("tablist", { name: "Design Studio" });
  expect(within(list).getAllByRole("tab").map((tab) => tab.getAttribute("aria-label"))).toEqual([
    "Workspace", "Pieces", "Measured Rooms", "Model Library", "Pricing", "AI & Agent Settings",
  ]);
  const divider = list.querySelector("[data-rail-divider]");
  expect(divider?.nextElementSibling).toBe(screen.getByRole("tab", { name: "AI & Agent Settings" }));
  expect(screen.getByRole("tab", { name: "AI & Agent Settings" })).toHaveAttribute("href", "/admin/agents");
});

test("Pricing opens on Prices with its three views in the sub-menu (Prices first)", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/studio/pieces");
  await user.click(screen.getByRole("tab", { name: "Pricing" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/pricing");
  expect(screen.getByRole("heading", { level: 1, name: "Design Studio" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Pricing" })).toHaveAttribute("aria-selected", "true");
  const [column] = screen.getAllByRole("navigation", { name: "Pricing views" });
  expect(within(column).getAllByRole("link").map((l) => l.textContent)).toEqual(["Prices", "Snapshots", "Remnants"]);
  expect(within(column).getByRole("link", { name: "Prices" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("table")).toBeInTheDocument();
});

test("choosing a Pricing view shows only that view (View chosen)", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/studio/pricing/prices");
  const [column] = screen.getAllByRole("navigation", { name: "Pricing views" });
  await user.click(within(column).getByRole("link", { name: "Remnants" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/pricing/remnants");
  expect(await screen.findByText("The rack is empty.")).toBeInTheDocument();
  expect(within(column).getByRole("link", { name: "Remnants" })).toHaveAttribute("aria-current", "page");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("form", { name: "Record a snapshot" })).not.toBeInTheDocument();
});

test("a Pricing view address opens that view (View address reloaded)", () => {
  stubAll();
  show("/studio/pricing/snapshots");
  expect(screen.getByRole("tab", { name: "Pricing" })).toHaveAttribute("aria-selected", "true");
  const [column] = screen.getAllByRole("navigation", { name: "Pricing views" });
  expect(within(column).getByRole("link", { name: "Snapshots" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("form", { name: "Record a snapshot" })).toBeInTheDocument();
});

test("on a phone the Pricing views are a row above the price list (Pricing on a phone)", () => {
  setScreenWidth(360);
  stubAll();
  show("/studio/pricing/prices");
  const [, row] = screen.getAllByRole("navigation", { name: "Pricing views" });
  expect(within(row).getAllByRole("link").map((l) => l.textContent)).toEqual(["Prices", "Snapshots", "Remnants"]);
  expect(row).toHaveClass("overflow-x-auto", "md:hidden");
  expect(screen.getByRole("tablist", { name: "Design Studio" })).toBeInTheDocument();
});

test("the developer tab opens on Agent Memory inside the Design Studio (Agent Memory first)", async () => {
  stubAll();
  show("/admin/agents");
  expect(screen.getByRole("heading", { level: 1, name: "Design Studio" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "AI & Agent Settings" })).toHaveAttribute("aria-selected", "true");
  const [column] = screen.getAllByRole("navigation", { name: "AI & Agent Settings views" });
  expect(within(column).getAllByRole("link").map((l) => l.textContent)).toEqual(AGENT_LABELS);
  expect(within(column).getByRole("link", { name: "Agent Memory" })).toHaveAttribute("aria-current", "page");
  expect(await screen.findByText("Generator-extension requests are always saved.")).toBeInTheDocument();
});

test("a developer view address keeps the developer route tree (View address reloaded)", async () => {
  const calls = stubFetch((call) => (call === "GET /admin/offload" ? { status: 503, body: { detail: "down" } } : undefined));
  show("/admin/agents/offload");
  const [column] = screen.getAllByRole("navigation", { name: "AI & Agent Settings views" });
  expect(within(column).getByRole("link", { name: "Render Offload" })).toHaveAttribute("aria-current", "page");
  expect(within(column).getByRole("link", { name: "Token Usage" })).toHaveAttribute("href", "/admin/agents/usage");
  await waitFor(() => expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("GET /admin/offload"));
});

test("on a phone the eight developer views are a sideways-scrolling row (Sub-menu on a phone)", () => {
  setScreenWidth(360);
  stubAll();
  show("/admin/agents/models");
  const [, row] = screen.getAllByRole("navigation", { name: "AI & Agent Settings views" });
  expect(within(row).getAllByRole("link").map((l) => l.textContent)).toEqual(AGENT_LABELS);
  expect(within(row).getByRole("link", { name: "Models and Routing" })).toHaveAttribute("aria-current", "page");
  expect(row).toHaveClass("overflow-x-auto", "md:hidden");
});
