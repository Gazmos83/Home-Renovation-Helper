import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import Workflow from "./Workflow";

const map = {
  homeowner: "homeowner",
  entry: "foreman",
  nodes: [
    { name: "foreman", model: "~deepseek/deepseek-v4-flash-latest", tools: [] },
    {
      name: "designer", model: "anthropic/claude-haiku-4.5",
      tools: [{ name: "revise_package", plugin: "revise_package", enabled: true, confirmation: true, render_guard: false }],
    },
    {
      name: "builder", model: "deepseek/deepseek-v4-pro-0813",
      tools: [{ name: "render_turntable", plugin: "render_turntable", enabled: false, confirmation: false, render_guard: true }],
    },
  ],
  handoffs: [
    { from: "homeowner", to: "foreman" },
    { from: "foreman", to: "designer" },
    { from: "foreman", to: "builder" },
  ],
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Workflow />
    </QueryClientProvider>,
  );
}

test("the map shows each agent with its routed model, its tools and their markers", async () => {
  stubFetch((call) => (call === "GET /admin/workflow" ? { body: map } : undefined));
  show();
  expect(await screen.findByRole("img", { name: "Agent workflow map" })).toBeInTheDocument();
  expect(screen.getAllByText("anthropic/claude-haiku-4.5").length).toBeGreaterThan(0);
  expect(screen.getByText(/revise_package \(revise_package\), waits for confirmation/)).toBeInTheDocument();
  expect(screen.getByText(/render_turntable \(render_turntable\), passes the render guard, disabled/)).toBeInTheDocument();
});

test("a graph that is not running is reported", async () => {
  stubFetch((call) =>
    call === "GET /admin/workflow"
      ? { status: 503, body: { detail: { failure_class: "graph_unavailable", reason: "the agent graph is not running" } } }
      : undefined,
  );
  show();
  expect(await screen.findByText(/The workflow map is not available/)).toBeInTheDocument();
});
