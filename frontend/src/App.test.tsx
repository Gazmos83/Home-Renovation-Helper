import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import App from "./App";
import { stubFetch } from "./test/fetchStub";

function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>
    </QueryClientProvider>,
  );
}

test("without a session the price list is the sign-in page", async () => {
  stubFetch((call) => (call === "GET /auth/me" ? { status: 401, body: { detail: "Not authenticated" } } : undefined));
  show("/price-list");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("a 401 from any call returns the owner to sign-in", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /remnants") return { status: 401, body: { detail: "session expired" } };
  });
  // The current address: an old one redirects, and the redirect re-checks the session, which this stub answers.
  show("/studio/pricing/remnants");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("the header stays at the top of the screen while the page scrolls", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /remnants") return { body: [] };
  });
  show("/remnants");
  const header = (await screen.findByRole("navigation", { name: "Main" })).closest("header");
  expect(header).toHaveClass("sticky", "top-0");
});

test("the homeowner nav has Design Studio and no Conversations", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /packages") return { body: [] };
  });
  show("/studio/pieces");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { name: "Design Studio" })).toHaveAttribute("href", "/studio");
  expect(within(nav).queryByRole("link", { name: "Conversations" })).not.toBeInTheDocument();
});

test("the nav has one Design Studio item, first, and no Pieces, Measured Rooms or Model Library", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /models") return { body: [] };
  });
  show("/studio/models");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  const labels = within(nav).getAllByRole("link").map((link) => link.textContent);
  expect(labels[0]).toBe("Design Studio");
  expect(within(nav).getByRole("link", { name: "Design Studio" })).toHaveAttribute("aria-current", "page");
  for (const old of ["Pieces", "Measured Rooms", "Model Library", "Rooms"]) {
    expect(within(nav).queryByRole("link", { name: old })).not.toBeInTheDocument();
  }
});

test("an old address opens its tab on the Design Studio page", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /rooms") return { body: [] };
    if (call === "GET /compositions") return { body: [] };
  });
  show("/rooms");
  expect(await screen.findByRole("heading", { level: 1, name: "Design Studio" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Measured Rooms" })).toHaveAttribute("aria-selected", "true");
});

test("a piece version's inspector keeps its address", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
  });
  show("/pieces/shoe-bench/versions/2");
  expect(await screen.findByRole("heading", { level: 1, name: "shoe-bench, version 2" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Back to pieces" })).toHaveAttribute("href", "/pieces");
  expect(screen.queryByRole("heading", { name: "Design Studio" })).not.toBeInTheDocument();
});

test("a reloaded dialog address opens the Design Studio tab with that dialog (Link reopens)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /rooms") {
      return {
        body: [{ name: "Wohnen", width_mm: 4000, depth_mm: 3500, corners: 4, height_mm: 2500, openings: 2,
          apartment: null, pieces: [], conversations: 0, composition: null }],
      };
    }
    if (call === "GET /compositions") return { body: [] };
  });
  show("/studio/rooms/Wohnen?page=1");
  const dialog = await screen.findByRole("dialog", { name: "Wohnen" });
  expect(within(dialog).getByText("4000 × 3500 mm, ceiling 2500 mm, 2 openings")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Measured Rooms", hidden: true })).toHaveAttribute("aria-selected", "true");
  const nav = screen.getByRole("navigation", { name: "Main", hidden: true });
  expect(within(nav).getByRole("link", { name: "Design Studio", hidden: true })).toHaveAttribute("aria-current", "page");
});

test("without a session a dialog address is the sign-in page", async () => {
  stubFetch((call) => (call === "GET /auth/me" ? { status: 401, body: { detail: "Not authenticated" } } : undefined));
  show("/studio/models/upload");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("without a session the model library is the sign-in page", async () => {
  stubFetch((call) => (call === "GET /auth/me" ? { status: 401, body: { detail: "Not authenticated" } } : undefined));
  show("/studio/models");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("a conversation deep link opens it in the Workspace, keeping its piece version (Deep link still works)", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /chat/threads/t1") {
      return {
        body: {
          thread_id: "t1",
          title: "Hall bench",
          package_id: "hall-bench",
          created_at: "",
          last_turn_at: "",
          messages: [],
          pending: null,
        },
      };
    }
    if (call === "GET /chat/threads/t1/progress") {
      return {
        body: {
          package_id: null,
          name: null,
          latest_version: null,
          approved_version: null,
          build_status: null,
          version_count: 0,
          max_versions: 15,
          steps: [],
          next_step: null,
          open_review_items: 0,
          open_requests: [],
          screenshot: null,
          still: null,
          viewer: null,
          rendering: false,
        },
      };
    }
    if (call === "GET /chat/threads/t1/tools") return { body: [] };
    if (call === "GET /chat/threads/t1/uploads") return { body: [] };
    if (call === "GET /chat/threads") return { body: [{ thread_id: "t1", title: "Hall bench", package_id: "hall-bench", created_at: "", last_turn_at: "" }] };
  });
  show("/conversations/t1?inspect=hall-bench/2");
  expect(await screen.findByRole("heading", { level: 2, name: "Hall bench" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Workspace" })).toHaveAttribute("aria-selected", "true");
  const [column] = screen.getAllByRole("navigation", { name: "Conversations" });
  expect(await within(column).findByRole("link", { name: "Hall bench" })).toHaveAttribute("aria-current", "page");
  // The piece pane shows the version the old address named.
  await waitFor(() => expect(calls.map(([, url]) => url)).toContain("/packages/hall-bench/versions/2"));
});

test("the old conversations list opens the Workspace", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /chat/threads") return { body: [] };
  });
  show("/conversations");
  expect(await screen.findByText("No conversations yet.")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Workspace" })).toHaveAttribute("aria-selected", "true");
});

test("pricing is a Design Studio tab and the nav has no Pricing Overview, Price list, Snapshots or Remnants (Navigation)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /remnants") return { body: [] };
  });
  show("/studio/pricing/remnants");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { name: "Design Studio" })).toHaveAttribute("aria-current", "page");
  for (const old of ["Pricing Overview", "Price list", "Snapshots", "Remnants", "AI & Agent Settings"]) {
    expect(within(nav).queryByRole("link", { name: old })).not.toBeInTheDocument();
  }
  expect(screen.getByRole("tab", { name: "Pricing" })).toHaveAttribute("aria-selected", "true");
});

for (const [old, view] of [
  ["/snapshots", "snapshots"],
  ["/pricing/snapshots", "snapshots"],
  ["/pricing", "prices"],
  ["/price-list", "prices"],
  ["/remnants", "remnants"],
  ["/pricing/quotes", "prices"],
] as const) {
  test(`the old address ${old} opens the ${view} view of the Pricing tab (Old address)`, async () => {
    stubFetch((call) => {
      if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
      if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
      if (call.startsWith("GET /price-list")) return { body: [] };
      if (call === "GET /snapshots") return { body: [] };
      if (call === "GET /remnants") return { body: [] };
    });
    show(old);
    expect(await screen.findByRole("heading", { level: 1, name: "Design Studio" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Pricing" })).toHaveAttribute("aria-selected", "true");
    const [column] = await screen.findAllByRole("navigation", { name: "Pricing views" });
    const label = { prices: "Prices", snapshots: "Snapshots", remnants: "Remnants" }[view];
    await waitFor(() => expect(within(column).getByRole("link", { name: label })).toHaveAttribute("aria-current", "page"));
  });
}

test("a signed-out visit to a Pricing view goes to sign-in (Signed out)", async () => {
  stubFetch((call) => (call === "GET /auth/me" ? { status: 401, body: { detail: "Not authenticated" } } : undefined));
  show("/studio/pricing/remnants");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

function stubDeveloper() {
  return stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { body: { slots: [], registry: [], profiles: [] } };
    if (call === "GET /chat/threads") return { body: [] };
    if (call.startsWith("GET /admin/usage/summary")) return { body: { days: 30, totals: [], per_day: [] } };
    if (call === "GET /packages") return { body: [] };
    if (call.startsWith("GET /admin/usage?")) return { body: [] };
  });
}

test("the developer header keeps Guidelines, Knowledge and Rules and has no AI & Agent Settings entry (Navigation)", async () => {
  stubDeveloper();
  show("/pieces");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  const rules = await within(nav).findByRole("link", { name: "Rules" });
  expect(rules).toBeInTheDocument();
  const labels = within(nav).getAllByRole("link").map((link) => link.textContent);
  expect(labels.slice(labels.lastIndexOf("Guidelines"))).toEqual(["Guidelines", "Knowledge", "Rules"]);
  for (const old of ["AI & Agent Settings", "Pricing Overview", "Models", "Plugins", "Usage", "Feedback", "Offload", "Calls", "Workflow", "Memory"]) {
    expect(within(nav).queryByRole("link", { name: old })).not.toBeInTheDocument();
  }
  expect(await screen.findByRole("tab", { name: "AI & Agent Settings" })).toHaveAttribute("href", "/admin/agents");
});

test("an old developer address opens its view of the Design Studio's developer tab (Old address)", async () => {
  stubDeveloper();
  show("/admin/conversations");
  expect(await screen.findByRole("heading", { level: 1, name: "Design Studio" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "AI & Agent Settings" })).toHaveAttribute("aria-selected", "true");
  const [column] = screen.getAllByRole("navigation", { name: "AI & Agent Settings views" });
  expect(within(column).getByRole("link", { name: "Agent Calls" })).toHaveAttribute("aria-current", "page");
  const nav = screen.getByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { name: "Design Studio" })).toHaveAttribute("aria-current", "page");
});

test("without the developer gate a developer address opens Pieces and the rail has no developer tab (Not a developer)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /packages") return { body: [] };
  });
  show("/admin/agents/models");
  expect(await screen.findByRole("tab", { name: "Pieces" })).toHaveAttribute("aria-selected", "true");
  expect(screen.queryByRole("tab", { name: "AI & Agent Settings" })).not.toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "AI & Agent Settings views" })).not.toBeInTheDocument();
});

test("a reloaded developer tab waits for the developer check instead of leaving the page", async () => {
  stubDeveloper();
  const stubbed = globalThis.fetch;
  // The developer check answers after the session check, as on a real reload.
  vi.stubGlobal("fetch", async (input: RequestInfo, init?: RequestInit) => {
    if (String(input) === "/admin/models") await new Promise((resolve) => setTimeout(resolve, 50));
    return stubbed(input, init);
  });
  show("/admin/agents/usage");
  expect(await screen.findByRole("tab", { name: "AI & Agent Settings" })).toHaveAttribute("aria-selected", "true");
  const [column] = screen.getAllByRole("navigation", { name: "AI & Agent Settings views" });
  expect(within(column).getByRole("link", { name: "Token Usage" })).toHaveAttribute("aria-current", "page");
});
