import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";
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

test("the homeowner nav has Pieces and no Conversations", async () => {
  stubFetch((call) => {
    if (call === "GET /auth/me") return { body: { email: "owner@example.com" } };
    if (call === "GET /admin/models") return { status: 403, body: { detail: "no" } };
    if (call === "GET /packages") return { body: [] };
  });
  show("/pieces");
  const nav = await screen.findByRole("navigation", { name: "Main" });
  expect(within(nav).getByRole("link", { name: "Pieces" })).toHaveAttribute("href", "/pieces");
  expect(within(nav).queryByRole("link", { name: "Conversations" })).not.toBeInTheDocument();
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
