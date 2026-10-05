import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import Models from "./Models";

const payload = {
  registry: [
    { slug: "deepseek/deepseek-v4-pro-0813", display_name: "Pro", supports_images: false },
    { slug: "anthropic/claude-haiku-4.5", display_name: "Haiku", supports_images: false },
  ],
  slots: [{ slot: "designer", model: "deepseek/deepseek-v4-pro-0813", override: false }],
  models: [
    {
      slug: "deepseek/deepseek-v4-pro-0813",
      temperature: null,
      max_output_tokens: null,
      context_budget_tokens: 32000,
      daily_token_ceiling: 2000000,
      usage_today: 0,
    },
  ],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/admin/routing/")) {
        return new Response(
          JSON.stringify({
            detail: { failure_class: "probe_failed", reason: "model blocked by gateway", field: "model" },
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/budget") && init?.method === "PUT") {
        return new Response(
          JSON.stringify({
            detail: { failure_class: "invalid_budget", reason: "daily_token_ceiling must be at least 1", field: "daily_token_ceiling" },
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/admin/models")) {
        return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response("nope", { status: 404 });
    }),
  );
});

function ui() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Models />
    </QueryClientProvider>,
  );
}

test("a refused routing change is shown next to the slot", async () => {
  const user = userEvent.setup();
  ui();
  const select = await screen.findByLabelText("Model");
  await user.selectOptions(select, "anthropic/claude-haiku-4.5");
  expect(await screen.findByText("model blocked by gateway")).toBeInTheDocument();
});

test("a refused budget value is shown next to its field", async () => {
  const user = userEvent.setup();
  ui();
  const daily = await screen.findByLabelText("Daily ceiling");
  await user.clear(daily);
  await user.type(daily, "0");
  await user.click(screen.getByText("Save budget"));
  expect(await screen.findByText("daily_token_ceiling must be at least 1")).toBeInTheDocument();
});
