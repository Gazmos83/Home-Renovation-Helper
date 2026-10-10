import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { ModelPrices } from "./ModelPrices";

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModelPrices />
    </QueryClientProvider>,
  );
}

test("prices per million tokens are shown, an unpriced slug says so, and a refresh replaces them", async () => {
  let refreshed = false;
  const calls = stubFetch((call) => {
    if (call === "GET /admin/model-prices")
      return {
        body: [
          { slug: "deepseek/deepseek-v4.1-flash", input_per_million_usd: 0.27, output_per_million_usd: 1.1, fetched_at: "2026-10-10T08:00:00Z" },
          { slug: "~deepseek/deepseek-v4-flash-latest", input_per_million_usd: null, output_per_million_usd: null, fetched_at: null },
        ],
      };
    if (call === "POST /admin/model-prices/refresh") {
      refreshed = true;
      return { body: [{ slug: "deepseek/deepseek-v4.1-flash", input_per_million_usd: 0.3, output_per_million_usd: 1.2, fetched_at: "2026-10-11T08:00:00Z" }] };
    }
  });
  show();
  const table = await screen.findByRole("table");
  const rows = within(table).getAllByRole("row").slice(1);
  expect(within(rows[0]).getByText("$0.2700")).toBeInTheDocument();
  expect(within(rows[1]).getAllByText("no price")).toHaveLength(2);
  await userEvent.setup().click(screen.getByRole("button", { name: "Refresh prices" }));
  expect(await screen.findByText("$0.3000")).toBeInTheDocument();
  expect(refreshed).toBe(true);
  expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("POST /admin/model-prices/refresh");
});

test("a failed refresh is reported and the stored prices stay", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/model-prices")
      return { body: [{ slug: "a", input_per_million_usd: 1, output_per_million_usd: 2, fetched_at: "2026-10-10T08:00:00Z" }] };
    if (call === "POST /admin/model-prices/refresh")
      return { status: 502, body: { detail: { failure_class: "price_refresh_failed", reason: "the model list could not be fetched (ConnectError)" } } };
  });
  show();
  await screen.findByText("$1.00");
  await userEvent.setup().click(screen.getByRole("button", { name: "Refresh prices" }));
  expect(await screen.findByText(/Prices were not refreshed/)).toBeInTheDocument();
  expect(screen.getByText("$1.00")).toBeInTheDocument();
});
