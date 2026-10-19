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

// A build notice opens its version beside the chat; a piece render notice has no button any more.
const DRAFT_NOTICE = { role: "notice", text: "hall-bench version 2 is built.", kind: "build", outcome: "succeeded", package_id: "hall-bench", version: 2 };

function stubAll(threads = [thread("t2", "Shoe rack"), thread("t1", "Hall bench")], messages: object[] = [DRAFT_NOTICE]) {
  return stubFetch((call) => {
    if (call === "GET /chat/threads") return { body: threads };
    if (call === "POST /chat/threads") return { status: 201, body: thread("t9", "") };
    if (/^GET \/chat\/threads\/t[129]$/.test(call)) {
      const id = call.split("/").at(-1);
      return { body: { ...thread(id as string, "Hall bench"), messages, pending: null } };
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
  const names = ["Chat and piece", "Chat and room", "Piece, room and chat above"];
  expect(items).toHaveLength(3);
  items.forEach((item, index) => expect(item.textContent?.endsWith(names[index])).toBe(true));
  expect(screen.getByRole("menuitemradio", { name: /Chat and piece/ })).toHaveAttribute("aria-checked", "true");
  await user.click(screen.getByRole("menuitemradio", { name: /Piece, room and chat above/ }));

  expect(await screen.findByRole("complementary", { name: "Room view" })).toBeInTheDocument();
  expect(inspector()).toBeInTheDocument();
  expect(handle("Resize the piece and the room")).toHaveAttribute("aria-valuenow", "50");
  expect(handle("Resize the chat above the piece and room")).toHaveAttribute("aria-valuenow", "40");
  // The chat comes before the piece and the room.
  expect(screen.getByRole("region", { name: "Messages" }).compareDocumentPosition(inspector()!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(inspector()!.compareDocumentPosition(roomView()!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(calls.some(([method, url]) => method === "POST" && url.includes("/turns"))).toBe(false);
});

test("the arrow keys move a focused handle, never below a fifth, and a double-click restores the default (Keyboard, Double-click resets)", async () => {
  const user = userEvent.setup();
  stubAll();
  setWorkspaceLayout("chat-above");
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

test("the chat grows when the handle below it moves down, and shrinks when it moves up (Chat expanded downwards, Chat expanded upwards)", async () => {
  const user = userEvent.setup();
  stubAll();
  setWorkspaceLayout("chat-above");
  show();
  await screen.findByRole("complementary", { name: "Room view" });
  const below = handle("Resize the chat above the piece and room");
  act(() => below.focus());
  // The handle's value is the chat's share of the height.
  await user.keyboard("{ArrowDown}");
  expect(Number(below.getAttribute("aria-valuenow"))).toBeGreaterThan(40);
  await user.keyboard("{Home}{ArrowUp}");
  expect(Number(below.getAttribute("aria-valuenow"))).toBe(20);
});

test("a browser that remembered the replaced layout opens chat above at its default sizes (Old layout remembered)", async () => {
  window.localStorage.setItem("studio.workspace.layout", "piece-room");
  resetWorkspaceLayout();
  stubAll();
  show();
  await screen.findByRole("complementary", { name: "Room view" });
  expect(inspector()).toBeInTheDocument();
  expect(handle("Resize the chat above the piece and room")).toHaveAttribute("aria-valuenow", "40");
  expect(handle("Resize the piece and the room")).toHaveAttribute("aria-valuenow", "50");
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
  await user.click(await screen.findByRole("button", { name: "Inspect version 2" }));
  expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
  expect(roomView()).not.toBeInTheDocument();
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/workspace/t1?inspect=hall-bench%2F2");
});

test("in the piece and room layout the piece and the room are both shown and neither closes the other (Piece and room together)", async () => {
  const user = userEvent.setup();
  stubAll();
  setWorkspaceLayout("chat-above");
  show();
  await screen.findByRole("complementary", { name: "Room view" });
  await user.click(await screen.findByRole("button", { name: "Inspect version 2" }));
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
  await user.click(await screen.findByRole("button", { name: "Inspect version 2" }));
  const tabs = within(screen.getByRole("tablist", { name: "Panes" }));
  expect(tabs.getByRole("tab", { name: "Piece" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByRole("complementary", { name: "Inspector" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Messages" })).not.toBeInTheDocument();
});

const CHAT = [
  { role: "owner", text: "Make it 10 cm narrower", message_id: "m1" },
  { role: "assistant", text: "Done. Version 3 is ready.", speaker: "designer" },
];

test("chat above shows a compact transcript on the left with the speakers inline (Compact transcript)", async () => {
  stubAll(undefined, CHAT);
  setWorkspaceLayout("chat-above");
  show();
  const list = await screen.findByRole("region", { name: "Messages" });
  const owner = await within(list).findByText("Make it 10 cm narrower");
  const reply = within(list).getByText("Done. Version 3 is ready.");
  for (const text of [owner, reply]) expect(text.closest("[data-side]")).toHaveAttribute("data-side", "left");
  // The speaker sits on the same row as the text, in a light bubble.
  const ownerRow = owner.closest("[data-side]")!.firstElementChild!;
  expect(ownerRow.textContent?.startsWith("You:Make it 10 cm narrower")).toBe(true);
  expect(ownerRow).toHaveClass("flex", "border");
  expect(ownerRow).not.toHaveClass("bg-primary");
  expect(reply.closest("[data-side]")!.firstElementChild!.textContent?.startsWith("Lil' Glitty:")).toBe(true);
  // An 8 px gap between messages.
  expect(list).toHaveClass("space-y-2");
});

test("chat above puts You:, the message box and Send on one row (Compact composer)", async () => {
  stubAll(undefined, CHAT);
  setWorkspaceLayout("chat-above");
  show();
  const box = await screen.findByRole("textbox", { name: "Message" });
  expect(box).toHaveAttribute("placeholder", "Describe what you want…");
  const row = box.parentElement!;
  expect(within(row).getByText("You:")).toBeInTheDocument();
  expect(within(row).getByRole("button", { name: "Send" })).toBeInTheDocument();
  expect(within(row).queryByLabelText("Add a plan, photo, design or note")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Add a plan, photo, design or note")).toBeInTheDocument();
});

test("switching to chat and piece brings back the left and right bubbles and keeps the half-typed message (Other layouts unchanged)", async () => {
  const user = userEvent.setup();
  stubAll(undefined, CHAT);
  setWorkspaceLayout("chat-above");
  show();
  await user.type(await screen.findByRole("textbox", { name: "Message" }), "Also lower");
  await chooseLayout(user, "Chat and piece");
  await screen.findByRole("complementary", { name: "Inspector" });
  const owner = screen.getByText("Make it 10 cm narrower");
  expect(owner.closest("[data-side]")).toHaveAttribute("data-side", "right");
  expect(screen.getByText("Done. Version 3 is ready.").closest("[data-side]")).toHaveAttribute("data-side", "left");
  expect(screen.getByRole("region", { name: "Messages" })).toHaveClass("space-y-4");
  expect(screen.getByRole("textbox", { name: "Message" })).toHaveValue("Also lower");
  expect(screen.queryByText("You:")).not.toBeInTheDocument();
});

test("the title row is gone: Layout sits at the end of the chat header, after the Room icon (Layout button in the chat header)", async () => {
  stubAll();
  show();
  const title = await screen.findByRole("heading", { level: 1, name: "Design Studio" });
  expect(title).toHaveClass("sr-only");
  const layout = screen.getByRole("button", { name: "Layout" });
  const roomIcon = screen.getByRole("button", { name: "Room" });
  expect(roomIcon.compareDocumentPosition(layout) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(layout.compareDocumentPosition(screen.getByRole("region", { name: "Messages" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("Delete sits on the header row right of the conversation's title (Delete beside the title)", async () => {
  const user = userEvent.setup();
  stubAll();
  show();
  const title = await screen.findByRole("heading", { level: 2, name: "Hall bench" });
  const remove = screen.getByRole("button", { name: "Delete Hall bench" });
  const row = screen.getByRole("button", { name: "Layout" }).closest(".flex-wrap")!;
  expect(row).toContainElement(title);
  expect(row).toContainElement(remove);
  expect(title.compareDocumentPosition(remove) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  await user.click(remove);
  // The confirmation takes its own line below the row.
  expect(screen.getByRole("group", { name: "Delete Hall bench?" })).toHaveClass("basis-full", "order-last");
});

test("switching the layout shows the chat at its last message (Last message after a switch)", async () => {
  const user = userEvent.setup();
  const tops = new WeakMap<Element, number>();
  const isBox = (el: Element) => el.getAttribute("aria-label") === "Messages";
  const spies = [
    vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(function (this: HTMLElement) {
      return isBox(this) ? 900 : 0;
    }),
    vi.spyOn(Element.prototype, "scrollTop", "get").mockImplementation(function (this: Element) {
      return tops.get(this) ?? 0;
    }),
    vi.spyOn(Element.prototype, "scrollTop", "set").mockImplementation(function (this: Element, value: number) {
      tops.set(this, value);
    }),
  ];
  try {
    stubAll(undefined, CHAT);
    show();
    const box = await screen.findByRole("region", { name: "Messages" });
    await screen.findByText("Done. Version 3 is ready.");
    // Moving the pane resets its scroll, as a browser does.
    tops.set(box, 0);
    await chooseLayout(user, "Piece, room and chat above");
    await waitFor(() => expect(box.scrollTop).toBe(900));
  } finally {
    spies.forEach((spy) => spy.mockRestore());
  }
});

/**
 * A stub that keeps approvals (workspace-pane-approval): `hall-bench` versions 1–3 (version 4 building)
 * and the room `Hall` versions 1–2, approving one clearing the other as the API does.
 */
function stubApprovals({ piece = null as number | null, room = null as number | null, refuseRoom = false } = {}) {
  const state = { piece, room };
  const status = (n: number) => (n === 4 ? "running" : "succeeded");
  const info = (n: number) => ({
    package_id: "hall-bench", version: n, status: status(n),
    approved_at: state.piece === n ? "2026-10-17T00:00:00Z" : null, files: ["model.glb", "spec.json"],
  });
  const roomVersion = (n: number) => ({
    version: n, status: "succeeded", picture: null, viewer: null, items: [],
    model: `/compositions/room-hall/versions/${n}/files/model.glb`,
    surfaces: `/compositions/room-hall/versions/${n}/files/report.json`, dimensions: null,
    approved_at: state.room === n ? "2026-10-17T00:00:00Z" : null,
  });
  return stubFetch((call) => {
    if (call === "GET /chat/threads") return { body: [thread("t1", "Hall bench")] };
    if (call === "GET /chat/threads/t1") return { body: { ...thread("t1", "Hall bench"), messages: [], pending: null } };
    if (call === "GET /chat/threads/t1/progress") {
      return {
        body: {
          ...progress, latest_version: 4, approved_version: state.piece, build_status: "running", version_count: 4,
          room: { ...HALL, versions: [roomVersion(2), roomVersion(1)], approved_version: state.room, approved_picture: null },
        },
      };
    }
    if (call === "GET /packages/hall-bench") return { body: { package_id: "hall-bench", versions: [4, 3, 2, 1].map(info) } };
    const version = /^GET \/packages\/hall-bench\/versions\/(\d)$/.exec(call);
    if (version) return { body: info(Number(version[1])) };
    if (/^GET \/packages\/hall-bench\/versions\/\d\/files\/spec.json$/.test(call)) return { body: SPEC };
    const pieceApproval = /^(PUT|DELETE) \/packages\/hall-bench\/versions\/(\d)\/approval$/.exec(call);
    if (pieceApproval) {
      state.piece = pieceApproval[1] === "PUT" ? Number(pieceApproval[2]) : null;
      return { body: info(Number(pieceApproval[2])) };
    }
    const roomApproval = /^(PUT|DELETE) \/compositions\/room-hall\/versions\/(\d)\/approval$/.exec(call);
    if (roomApproval) {
      if (refuseRoom) {
        return {
          status: 409,
          body: { detail: { failure_class: "unapproved_pieces", reason: "Hall version 2 places hall-bench v3, which is not approved; approve those piece versions first" } },
        };
      }
      const n = Number(roomApproval[2]);
      state.room = roomApproval[1] === "PUT" ? n : null;
      return { body: { slug: "room-hall", version: n, status: "succeeded", approved_at: state.room === n ? "2026-10-17T00:00:00Z" : null } };
    }
    if (/^GET \/compositions\/room-hall\/versions\/\d\/files\/report.json$/.test(call)) {
      return { body: { surfaces: { "wall 1": ["Wall_0_0"] }, extent_mm: { min: [0, 0, 0], max: [3000, 2000, 2500] } } };
    }
  });
}

const sentTurn = (calls: [string, string, unknown][]) =>
  calls.some(([method, url]) => method === "POST" && url.startsWith("/chat/threads/t1/"));

test("the piece pane approves the version it shows, and the dropdown follows without a turn (Approve the shown piece version)", async () => {
  const user = userEvent.setup();
  const calls = stubApprovals();
  show("/studio/workspace/t1?inspect=hall-bench/2");
  const pane = await screen.findByRole("complementary", { name: "Inspector" });
  await user.click(await within(pane).findByRole("button", { name: "Approve version 2" }));
  expect(await within(pane).findByRole("button", { name: "Unapprove version 2" })).toBeInTheDocument();
  expect(await within(pane).findByRole("option", { name: "Version 2, built, approved" })).toBeInTheDocument();
  expect(calls.some(([method, url]) => method === "PUT" && url === "/packages/hall-bench/versions/2/approval")).toBe(true);
  expect(sentTurn(calls)).toBe(false);
});

test("approving an older version from the piece pane's dropdown replaces the approval (Approve an older piece version)", async () => {
  const user = userEvent.setup();
  stubApprovals({ piece: 3 });
  show("/studio/workspace/t1?inspect=hall-bench/3");
  const pane = await screen.findByRole("complementary", { name: "Inspector" });
  expect(await within(pane).findByRole("button", { name: "Unapprove version 3" })).toBeInTheDocument();
  await user.selectOptions(within(pane).getByRole("combobox", { name: "Version" }), "2");
  await user.click(await within(pane).findByRole("button", { name: "Approve version 2" }));
  expect(await within(pane).findByRole("option", { name: "Version 2, built, approved" })).toBeInTheDocument();
  expect(within(pane).getByRole("option", { name: "Version 3, built" })).toBeInTheDocument();
});

test("the piece pane unapproves the approved version it shows (Unapprove the shown piece version)", async () => {
  const user = userEvent.setup();
  stubApprovals({ piece: 2 });
  show("/studio/workspace/t1?inspect=hall-bench/2");
  const pane = await screen.findByRole("complementary", { name: "Inspector" });
  await user.click(await within(pane).findByRole("button", { name: "Unapprove version 2" }));
  expect(await within(pane).findByRole("button", { name: "Approve version 2" })).toBeInTheDocument();
});

test("a version still building offers no approval control in the piece pane (Unbuilt version offers no control)", async () => {
  stubApprovals();
  show("/studio/workspace/t1?inspect=hall-bench/4");
  const pane = await screen.findByRole("complementary", { name: "Inspector" });
  expect(await within(pane).findByText("Version 4 is not approved.")).toBeInTheDocument();
  expect(within(pane).queryByRole("button", { name: /approve version 4/i })).not.toBeInTheDocument();
  expect(within(pane).queryByRole("button", { name: "Delete version 4" })).not.toBeInTheDocument();
});

test("the room pane approves and unapproves the version it shows (Approve the shown room version)", async () => {
  const user = userEvent.setup();
  const calls = stubApprovals();
  setWorkspaceLayout("chat-room");
  show();
  const pane = await screen.findByRole("complementary", { name: "Room view" });
  await user.click(await within(pane).findByRole("button", { name: "Approve version 2" }));
  expect(await within(pane).findByRole("option", { name: "Version 2 (approved)" })).toBeInTheDocument();
  await user.click(within(pane).getByRole("button", { name: "Unapprove version 2" }));
  expect(await within(pane).findByRole("button", { name: "Approve version 2" })).toBeInTheDocument();
  expect(sentTurn(calls)).toBe(false);
});

test("a refused room approval is shown next to the control and nothing changes (Room approval refused)", async () => {
  const user = userEvent.setup();
  stubApprovals({ refuseRoom: true });
  setWorkspaceLayout("chat-room");
  show();
  const pane = await screen.findByRole("complementary", { name: "Room view" });
  await user.click(await within(pane).findByRole("button", { name: "Approve version 2" }));
  expect(await within(pane).findByText(/places hall-bench v3, which is not approved/)).toBeInTheDocument();
  expect(within(pane).getByRole("button", { name: "Approve version 2" })).toBeInTheDocument();
  // The service's words only: no status code and no internal code (workspace-opens-inspector).
  expect(pane.textContent).not.toMatch(/409|unapproved_pieces/);
});
