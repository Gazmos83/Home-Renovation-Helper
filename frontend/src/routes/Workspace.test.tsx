import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { resetWorkspaceLayout, setWorkspaceLayout } from "../lib/workspaceLayout";
import { stubFetch } from "../test/fetchStub";
import { setScreenWidth } from "../test/media";
import Studio from "./Studio";

// No WebGL in jsdom: the 3D stage is a stub.
vi.mock("@/components/inspector/InspectorCanvas", () => ({ default: () => <div data-testid="canvas" /> }));

const SPEC = {
  name: "Hall bench", units: "mm", overall: { w: 1200, h: 450, d: 400 }, modules: {},
  layers: { carcass: ["side"] }, parts: [], hardware: [],
};
const HALL = {
  name: "Hall", scope: "room", slug: "room-hall",
  model: "/compositions/room-hall/versions/1/files/model.glb",
  surfaces: "/compositions/room-hall/versions/1/files/report.json",
};
const progress = {
  package_id: "hall-bench", name: "Hall bench", latest_version: 1, approved_version: null, build_status: "succeeded",
  version_count: 1, max_versions: 15, steps: [], next_step: "Ask for a draft render", open_review_items: 0,
  open_requests: [], screenshot: null, still: null, viewer: null, rendering: false, room: HALL,
};
const thread = (id: string, title: string) => ({ thread_id: id, title, package_id: null, created_at: "", last_turn_at: "" });

function stubAll(threads = [thread("t2", "Shoe rack"), thread("t1", "Hall bench")]) {
  return stubFetch((call) => {
    if (call === "GET /chat/threads") return { body: threads };
    if (call === "POST /chat/threads") return { status: 201, body: thread("t9", "") };
    if (/^GET \/chat\/threads\/t[129]$/.test(call)) {
      const id = call.split("/").at(-1);
      return { body: { ...thread(id as string, "Hall bench"), messages: [{ role: "notice", text: "Draft v2 is ready.", kind: "render", outcome: "succeeded", tier: "draft", package_id: "hall-bench", version: 2 }], pending: null } };
    }
    if (/^GET \/chat\/threads\/t[129]\/progress$/.test(call)) return { body: progress };
    if (/^GET \/packages\/hall-bench\/versions\/\d$/.test(call)) {
      const version = Number(call.at(-1));
      return { body: { package_id: "hall-bench", version, status: "succeeded", approved_at: null, files: ["model.glb", "spec.json"] } };
    }
    if (/^GET \/packages\/hall-bench\/versions\/\d\/files\/spec.json$/.test(call)) return { body: SPEC };
    if (call === "GET /compositions/room-hall/versions/1/files/report.json") {
      return { body: { surfaces: { "wall 1": ["Wall_0_0"] }, extent_mm: { min: [0, 0, 0], max: [3000, 2000, 2500] } } };
    }
  });
}

function Address() {
  const location = useLocation();
  return <output aria-label="address">{location.pathname + location.search}</output>;
}

function show(path = "/studio/workspace/t1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/studio/:tab/*" element={<Studio />} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const inspector = () => screen.queryByRole("complementary", { name: "Inspector" });
const roomView = () => screen.queryByRole("complementary", { name: "Room view" });
const handle = (name: string) => screen.getByRole("separator", { name });

async function chooseLayout(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByRole("button", { name: "Layout" }));
  await user.click(await screen.findByRole("menuitemradio", { name }));
}

test("a conversation opens with the chat on the left and the piece on the right, each half the width (Default layout)", async () => {
  stubAll();
  show();
  expect(await screen.findByRole("region", { name: "Messages" })).toBeInTheDocument();
  expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
  expect(roomView()).not.toBeInTheDocument();
  const between = handle("Resize the chat and the piece");
  expect(between).toHaveAttribute("aria-valuenow", "50");
  // The chat comes first, the piece after the handle.
  const chat = screen.getByRole("region", { name: "Messages" });
  expect(chat.compareDocumentPosition(between) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(between.compareDocumentPosition(inspector()!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("the Layout menu lists the three layouts with the current one marked, and choosing one switches without a turn (Choose a layout)", async () => {
  const user = userEvent.setup();
  const calls = stubAll();
  show();
  await screen.findByRole("complementary", { name: "Inspector" });
  await user.click(screen.getByRole("button", { name: "Layout" }));
  const items = await screen.findAllByRole("menuitemradio");
  // Each item is its pictogram (the letters C, P and R) and its name.
  const names = ["Chat and piece", "Chat and room", "Piece and room, chat below"];
  expect(items).toHaveLength(3);
  items.forEach((item, index) => expect(item.textContent?.endsWith(names[index])).toBe(true));
  expect(screen.getByRole("menuitemradio", { name: /Chat and piece/ })).toHaveAttribute("aria-checked", "true");
  await user.click(screen.getByRole("menuitemradio", { name: /Piece and room, chat below/ }));

  expect(await screen.findByRole("complementary", { name: "Room view" })).toBeInTheDocument();
  expect(inspector()).toBeInTheDocument();
  expect(handle("Resize the piece and the room")).toHaveAttribute("aria-valuenow", "50");
  expect(handle("Resize the piece and room above the chat")).toHaveAttribute("aria-valuenow", "60");
  // The piece and the room come before the chat.
  expect(roomView()!.compareDocumentPosition(screen.getByRole("region", { name: "Messages" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(calls.some(([method, url]) => method === "POST" && url.includes("/turns"))).toBe(false);
});

test("the arrow keys move a focused handle, never below a fifth, and a double-click restores the default (Keyboard, Double-click resets)", async () => {
  const user = userEvent.setup();
  stubAll();
  setWorkspaceLayout("piece-room");
  show();
  await screen.findByRole("complementary", { name: "Room view" });
  const between = handle("Resize the piece and the room");
  act(() => between.focus());
  await user.keyboard("{ArrowLeft}");
  const moved = Number(between.getAttribute("aria-valuenow"));
  expect(moved).toBeLessThan(50);
  await user.keyboard("{Home}");
  expect(Number(between.getAttribute("aria-valuenow"))).toBe(20);

  // The library finds the handle under the pointer; the test setup measures the panels off-screen.
  fireEvent.dblClick(between, { clientX: -9500, clientY: -9600 });
  await waitFor(() => expect(between).toHaveAttribute("aria-valuenow", "50"));
});

test("the chat grows upwards when the handle above it moves up (Chat expanded upwards)", async () => {
  const user = userEvent.setup();
  stubAll();
  setWorkspaceLayout("piece-room");
  show();
  await screen.findByRole("complementary", { name: "Room view" });
  const above = handle("Resize the piece and room above the chat");
  act(() => above.focus());
  await user.keyboard("{ArrowUp}");
  // The top panes shrink, so the chat below them grows.
  expect(Number(above.getAttribute("aria-valuenow"))).toBeLessThan(60);
});


test("the layout and its sizes are remembered in the browser (Remembered)", async () => {
  const user = userEvent.setup();
  stubAll();
  show();
  await screen.findByRole("complementary", { name: "Inspector" });
  await chooseLayout(user, "Chat and room");
  const between = handle("Resize the chat and the room");
  act(() => between.focus());
  await user.keyboard("{ArrowRight}");
  const moved = between.getAttribute("aria-valuenow");
  expect(moved).not.toBe("50");
  expect(window.localStorage.getItem("studio.workspace.layout")).toBe("chat-room");
  await waitFor(() => expect(Object.keys(window.localStorage).some((key) => key.includes("workspace.chat-room"))).toBe(true));

  // A reload: the page and the in-memory choice are gone, the browser's memory is not.
  cleanup();
  resetWorkspaceLayout();
  show();
  expect(await screen.findByRole("complementary", { name: "Room view" })).toBeInTheDocument();
  await waitFor(() => expect(handle("Resize the chat and the room")).toHaveAttribute("aria-valuenow", moved));
});

test("without browser storage the Workspace opens on the default and still switches (Storage unavailable)", async () => {
  const user = userEvent.setup();
  stubAll();
  const blocked = () => {
    throw new Error("blocked");
  };
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(blocked);
  try {
    show();
    expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
    await chooseLayout(user, "Chat and room");
    expect(await screen.findByRole("complementary", { name: "Room view" })).toBeInTheDocument();
    expect(inspector()).not.toBeInTheDocument();
  } finally {
    vi.restoreAllMocks();
  }
});

test("reviewing a version from the chat in the room layout switches to the piece layout (Opened from the room layout)", async () => {
  const user = userEvent.setup();
  stubAll();
  setWorkspaceLayout("chat-room");
  show();
  await screen.findByRole("complementary", { name: "Room view" });
  await user.click(await screen.findByRole("button", { name: /Review draft revision 2/ }));
  expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
  expect(roomView()).not.toBeInTheDocument();
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/workspace/t1?inspect=hall-bench%2F2");
});

test("in the piece and room layout the piece and the room are both shown and neither closes the other (Piece and room together)", async () => {
  const user = userEvent.setup();
  stubAll();
  setWorkspaceLayout("piece-room");
  show();
  await screen.findByRole("complementary", { name: "Room view" });
  await user.click(await screen.findByRole("button", { name: /Review draft revision 2/ }));
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("inspect=hall-bench%2F2"));
  expect(inspector()).toBeInTheDocument();
  expect(roomView()).toBeInTheDocument();
});

test("/studio/workspace opens the most recent conversation, highlighted in the sub-menu (Newest conversation)", async () => {
  stubAll();
  show("/studio/workspace");
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/studio/workspace/t2"));
  const [column] = screen.getAllByRole("navigation", { name: "Conversations" });
  expect(within(column).getAllByRole("link").map((link) => link.textContent)).toEqual(["Shoe rack", "Hall bench"]);
  expect(await within(column).findByRole("link", { name: "Shoe rack" })).toHaveAttribute("aria-current", "page");
});

test("New conversation starts one and opens it (New conversation)", async () => {
  const user = userEvent.setup();
  const calls = stubAll();
  show();
  const [column] = screen.getAllByRole("navigation", { name: "Conversations" });
  await user.click(within(column).getByRole("button", { name: "New conversation" }));
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/studio/workspace/t9"));
  expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("POST /chat/threads");
});

test("with no conversations the Workspace says so and offers to start one", async () => {
  stubAll([]);
  show("/studio/workspace");
  expect(await screen.findByText("No conversations yet.")).toBeInTheDocument();
  const [column] = screen.getAllByRole("navigation", { name: "Conversations" });
  expect(within(column).getByText("No conversations yet")).toBeInTheDocument();
});

test("an unknown conversation says it was not found and keeps the sub-menu", async () => {
  stubAll();
  show("/studio/workspace/t7");
  expect(await screen.findByText(/This conversation was not found/)).toBeInTheDocument();
  expect(screen.getAllByRole("navigation", { name: "Conversations" }).length).toBeGreaterThan(0);
});

test("on a phone one pane is shown at a time from Chat, Piece and Room tabs, with no Layout button (Phone tabs)", async () => {
  setScreenWidth(360);
  stubAll();
  show();
  const tabs = within(await screen.findByRole("tablist", { name: "Panes" }));
  expect(tabs.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Chat", "Piece", "Room"]);
  expect(tabs.getByRole("tab", { name: "Chat" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByRole("region", { name: "Messages" })).toBeInTheDocument();
  expect(inspector()).not.toBeInTheDocument();
  expect(roomView()).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Layout" })).not.toBeInTheDocument();
  expect(screen.queryByRole("separator")).not.toBeInTheDocument();
});

test("on a phone reviewing a version from the chat chooses the Piece tab (Phone review)", async () => {
  const user = userEvent.setup();
  setScreenWidth(360);
  stubAll();
  show();
  await user.click(await screen.findByRole("button", { name: /Review draft revision 2/ }));
  const tabs = within(screen.getByRole("tablist", { name: "Panes" }));
  expect(tabs.getByRole("tab", { name: "Piece" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Messages" })).not.toBeInTheDocument();
});
