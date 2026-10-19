import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import Users from "./Users";

const owner = { id: "1", email: "owner@example.com", created_at: "2026-10-19T00:00:00Z", is_owner: true };
const member = { id: "2", email: "member@example.com", created_at: "2026-10-19T00:00:00Z", is_owner: false };

function json(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Users />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

test("the owner has no Remove button and a member does", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json([owner, member])));
  show();
  expect(await screen.findByText("member@example.com")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(1);
});

test("adding a member sends the email and password", async () => {
  const fetch = vi.fn(async (_url: string, init?: RequestInit) => (init?.method === "POST" ? json(member, 201) : json([owner])));
  vi.stubGlobal("fetch", fetch);
  show();
  await screen.findByText("owner@example.com");
  await userEvent.type(screen.getByLabelText("Email"), "member@example.com");
  await userEvent.type(screen.getByLabelText(/Starting password/), "member-password-1");
  await userEvent.click(screen.getByRole("button", { name: "Add member" }));
  const post = fetch.mock.calls.find(([, init]) => init?.method === "POST");
  expect(post?.[0]).toContain("/admin/users");
  expect(JSON.parse(String(post?.[1]?.body))).toEqual({ email: "member@example.com", password: "member-password-1" });
});
