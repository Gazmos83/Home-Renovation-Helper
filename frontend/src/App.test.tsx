import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
  show("/remnants");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});
