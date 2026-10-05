import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import Usage from "./Usage";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            model: "deepseek/deepseek-v4-pro-0813",
            day: "2026-10-06",
            input_tokens: 30,
            output_tokens: 12,
            calls: 3,
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }),
  );
});

test("usage today is shown per model", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Usage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("deepseek/deepseek-v4-pro-0813")).toBeInTheDocument();
  expect(screen.getByText("30")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
});
