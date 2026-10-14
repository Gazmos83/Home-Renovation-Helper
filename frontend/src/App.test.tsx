import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
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
  show("/pricing/remnants");
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

test("without a session the model library is the sign-in page", async () => {
  stubFetch((call) => (call === "GET /auth/me" ? { status: 401, body: { detail: "Not authenticated" } } : undefined));
  show("/studio/models");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("a conversation deep link still opens the conversation view", async () => {
  stubFetch((call) => {
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
  });
  show("/conversations/t1");
  expect(await screen.findByRole("heading", { name: "Hall bench" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "All pieces" })).toHaveAttribute("href", "/pieces");
});

test("the nav has one Pricing Overview item and no Price list, Snapshots or Remnants", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /remnants") return { body: [] };
  });
  show("/pricing/remnants");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  const pricing = within(nav).getByRole("link", { name: "Pricing Overview" });
  expect(pricing).toHaveAttribute("href", "/pricing");
  expect(pricing).toHaveAttribute("aria-current", "page");
  for (const old of ["Price list", "Snapshots", "Remnants"]) {
    expect(within(nav).queryByRole("link", { name: old })).not.toBeInTheDocument();
  }
});

test("an old address opens its tab on the Pricing Overview page", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /snapshots") return { body: [] };
  });
  show("/snapshots");
  expect(await screen.findByRole("heading", { level: 1, name: "Pricing Overview" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Snapshots" })).toHaveAttribute("aria-selected", "true");
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

test("the developer nav has one AI & Agent Settings item in place of the eight agent pages", async () => {
  stubDeveloper();
  show("/pieces");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  const settings = await within(nav).findByRole("link", { name: "AI & Agent Settings" });
  expect(settings).toHaveAttribute("href", "/admin/agents");
  const labels = within(nav).getAllByRole("link").map((link) => link.textContent);
  expect(labels.slice(labels.indexOf("AI & Agent Settings"))).toEqual(["AI & Agent Settings", "Guidelines", "Knowledge", "Rules"]);
  for (const old of ["Models", "Plugins", "Usage", "Feedback", "Offload", "Calls", "Workflow", "Memory"]) {
    expect(within(nav).queryByRole("link", { name: old })).not.toBeInTheDocument();
  }
});

test("an old developer address opens its tab on the AI & Agent Settings page", async () => {
  stubDeveloper();
  show("/admin/conversations");
  expect(await screen.findByRole("heading", { level: 1, name: "AI & Agent Settings" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Agent Calls" })).toHaveAttribute("aria-selected", "true");
  const nav = screen.getByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { name: "AI & Agent Settings" })).toHaveAttribute("aria-current", "page");
});

test("without the developer gate the AI & Agent Settings page is not shown", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /packages") return { body: [] };
  });
  show("/admin/agents/models");
  expect(await screen.findByRole("navigation", { name: "Main" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "AI & Agent Settings" })).not.toBeInTheDocument();
  expect(screen.queryByRole("tab")).not.toBeInTheDocument();
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
  expect(await screen.findByRole("heading", { level: 1, name: "AI & Agent Settings" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Token Usage" })).toHaveAttribute("aria-selected", "true");
});
