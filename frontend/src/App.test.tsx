import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

test("the name sits at the left and Help, About and Sign out at the right (Header layout)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /remnants") return { body: [] };
  });
  show("/remnants");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(nav).not.toHaveClass("max-w-5xl");
  expect(nav.firstElementChild).toBe(within(nav).getByRole("link", { name: "Little Homey" }));
  const right = within(nav).getByRole("link", { name: "Help" }).parentElement!;
  expect(right).toHaveClass("ml-auto");
  expect(within(right).getAllByRole("link").map((link) => link.textContent)).toEqual(["Help", "About"]);
  expect(within(right).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
});

test("the footer stays at the bottom of the screen while the page scrolls (Footer frozen at the bottom)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /remnants") return { body: [] };
  });
  show("/remnants");
  expect(await screen.findByRole("contentinfo")).toHaveClass("fixed", "bottom-0");
});

test("the homeowner nav has no Design Studio and no Conversations item, and the name links home (Nav without Conversations)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /packages") return { body: [] };
  });
  show("/studio/pieces");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).queryByRole("link", { name: "Design Studio" })).not.toBeInTheDocument();
  expect(within(nav).queryByRole("link", { name: "Conversations" })).not.toBeInTheDocument();
  expect(within(nav).getByRole("link", { name: "Little Homey" })).toHaveAttribute("href", "/studio/workspace");
});

test("the nav has no Design Studio, Pieces, Measured Rooms or Model Library item (Navigation)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /models") return { body: [] };
  });
  show("/studio/models");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(["Little Homey", "Help", "About"]);
  for (const old of ["Design Studio", "Pieces", "Measured Rooms", "Model Library", "Rooms"]) {
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
  for (const old of ["Design Studio", "Pricing Overview", "Price list", "Snapshots", "Remnants", "AI & Agent Settings"]) {
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

test("the developer header has the name and Help only, with no developer entries (Navigation)", async () => {
  stubDeveloper();
  show("/pieces");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(await screen.findByRole("tab", { name: "AI & Agent Settings" })).toHaveAttribute("href", "/admin/agents");
  expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(["Little Homey", "Help", "About"]);
  expect(screen.getByRole("tab", { name: "Design Knowledge" })).toHaveAttribute("href", "/admin/design-knowledge");
});

test("the homeowner header has no Guidelines entry", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /packages") return { body: [] };
  });
  show("/studio/pieces");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(["Little Homey", "Help", "About"]);
});

test.each([
  ["/guidelines", "Guidelines"],
  ["/admin/guidelines", "Guidelines"],
  ["/admin/knowledge", "Engineering Knowledge"],
  ["/admin/rules", "Design Rules"],
])("the old address %s opens the %s view of Design Knowledge (Old addresses)", async (path, view) => {
  stubDeveloper();
  show(path);
  expect(await screen.findByRole("tab", { name: "Design Knowledge" })).toHaveAttribute("aria-selected", "true");
  const [column] = screen.getAllByRole("navigation", { name: "Design Knowledge views" });
  expect(within(column).getByRole("link", { name: view })).toHaveAttribute("aria-current", "page");
});

test("a reloaded Design Knowledge view keeps its view (View address reloaded)", async () => {
  stubDeveloper();
  show("/admin/design-knowledge/engineering");
  const [column] = await screen.findAllByRole("navigation", { name: "Design Knowledge views" });
  expect(within(column).getByRole("link", { name: "Engineering Knowledge" })).toHaveAttribute("aria-current", "page");
});

test.each(["/guidelines", "/admin/design-knowledge/guidelines"])(
  "without the developer gate %s opens the Workspace with no Design Knowledge tab (Not a developer)",
  async (path) => {
    stubFetch((call) => {
      if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
      if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
      if (call === "GET /packages") return { body: [] };
      if (call === "GET /chat/threads") return { body: [] };
    });
    show(path);
    expect(await screen.findByRole("tab", { name: "Workspace" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("tab", { name: "Design Knowledge" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Guideline notes" })).not.toBeInTheDocument();
  },
);

test("an old developer address opens its view of the Design Studio's developer tab (Old address)", async () => {
  stubDeveloper();
  show("/admin/conversations");
  expect(await screen.findByRole("heading", { level: 1, name: "Design Studio" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "AI & Agent Settings" })).toHaveAttribute("aria-selected", "true");
  const [column] = screen.getAllByRole("navigation", { name: "AI & Agent Settings views" });
  expect(within(column).getByRole("link", { name: "Agent Calls" })).toHaveAttribute("aria-current", "page");
});

test("without the developer gate a developer address opens the Workspace and the rail has no developer tab (Not a developer)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /packages") return { body: [] };
    if (call === "GET /chat/threads") return { body: [] };
  });
  show("/admin/agents/models");
  expect(await screen.findByRole("tab", { name: "Workspace" })).toHaveAttribute("aria-selected", "true");
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

test.each(["/", "/studio", "/somewhere-unknown"])("a signed-in owner opening %s lands on the Workspace (Home address)", async (path) => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /packages") return { body: [] };
    if (call === "GET /chat/threads") return { body: [] };
  });
  show(path);
  expect(await screen.findByRole("tab", { name: "Workspace" })).toHaveAttribute("aria-selected", "true");
  // The sub-menu and the empty Workspace each offer one.
  expect((await screen.findAllByRole("button", { name: "New conversation" })).length).toBeGreaterThan(0);
});

test("signing in lands on the Workspace (Sign-in lands on the Workspace)", async () => {
  let signedIn = false;
  stubFetch((call) => {
    if (call === "GET /auth/me") return signedIn ? { body: { email: "owner@example.com" } } : { status: 401, body: { detail: "Not authenticated" } };
    if (call === "POST /auth/login") {
      signedIn = true;
      return { body: { email: "owner@example.com" } };
    }
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /chat/threads") return { body: [] };
  });
  const user = userEvent.setup();
  show("/login");
  await user.type(await screen.findByLabelText("Email"), "owner@example.com");
  await user.type(screen.getByLabelText("Password"), "secret");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("tab", { name: "Workspace" })).toHaveAttribute("aria-selected", "true");
});

test("Sign out ends the session and shows the sign-in page (Sign out)", async () => {
  let signedIn = true;
  const calls = stubFetch((call) => {
    if (call === "GET /auth/me") return signedIn ? { body: { email: "owner@example.com" } } : { status: 401, body: { detail: "Not authenticated" } };
    if (call === "POST /auth/logout") {
      signedIn = false;
      return { body: { signed_out: true } };
    }
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /chat/threads") return { body: [] };
  });
  const user = userEvent.setup();
  show("/studio/workspace");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  await user.click(within(nav).getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("POST /auth/logout");
});

test("a failed sign-out keeps the owner signed in and says why (Sign-out fails)", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "POST /auth/logout") return { status: 503, body: { detail: "The service is unavailable." } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /chat/threads") return { body: [] };
  });
  const user = userEvent.setup();
  show("/studio/workspace");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  await user.click(within(nav).getByRole("button", { name: "Sign out" }));
  expect(await within(nav).findByRole("alert")).toHaveTextContent("The service is unavailable.");
  expect(within(nav).getByRole("button", { name: "Sign out" })).toBeEnabled();
  expect(screen.queryByRole("heading", { name: "Sign in" })).not.toBeInTheDocument();
});
