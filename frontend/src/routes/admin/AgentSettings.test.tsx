import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import AgentSettings from "./AgentSettings";

const memoryDefaults = {
  trigger_percent: 100, keep_turns: 0, note_tokens: 400, note_instructions: "You keep the notes.", tool_result_chars: 300,
  reviews: "auto", save_preferences: true, other_builds: "line", include_preferences: true,
  include_review_items: true, render_ratings: 5, include_extension_requests: true,
};
const memory = { settings: memoryDefaults, defaults: memoryDefaults, fixed_rules: ["Generator-extension requests are always saved."] };

afterEach(() => window.localStorage.clear());

function Address() {
  return <output aria-label="address">{useLocation().pathname}</output>;
}

function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/admin/agents" element={<AgentSettings />} />
          <Route path="/admin/agents/:tab" element={<AgentSettings />} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function stubAll() {
  return stubFetch((call) => {
    if (call === "GET /admin/memory") return { body: memory };
    if (call.startsWith("GET /admin/usage?")) return { body: [] };
  });
}

test("the page opens on the Agent Memory tab with the tabs in the owner's order", async () => {
  stubAll();
  show("/admin/agents");
  expect(screen.getByRole("heading", { level: 1, name: "AI & Agent Settings" })).toBeInTheDocument();
  expect(screen.getAllByRole("tab").map((tab) => tab.getAttribute("aria-label"))).toEqual([
    "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins", "Models and Routing",
  ]);
  expect(screen.getByRole("tab", { name: "Agent Memory" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByText("Generator-extension requests are always saved.")).toBeInTheDocument();
});

test("choosing a tab changes the address and shows only that tab", async () => {
  const user = userEvent.setup();
  const calls = stubAll();
  show("/admin/agents/memory");
  await screen.findByText("Generator-extension requests are always saved.");
  await user.click(screen.getByRole("tab", { name: "Token Usage" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/admin/agents/usage");
  expect(screen.getByRole("tab", { name: "Token Usage" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Agent Memory" })).toHaveAttribute("aria-selected", "false");
  expect(await screen.findByRole("table")).toBeInTheDocument();
  expect(screen.queryByText("Generator-extension requests are always saved.")).not.toBeInTheDocument();
  expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("GET /admin/usage?days=1");
});

test("a tab address opens that tab and loads only its content", async () => {
  const calls = stubFetch((call) => (call === "GET /admin/offload" ? { status: 503, body: { detail: "down" } } : undefined));
  show("/admin/agents/offload");
  expect(screen.getByRole("tab", { name: "Render Offload" })).toHaveAttribute("aria-selected", "true");
  await waitFor(() => expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("GET /admin/offload"));
  expect(calls.map(([, url]) => url)).not.toContain("/admin/memory");
});

test("an unknown tab opens Agent Memory", async () => {
  stubAll();
  show("/admin/agents/quotes");
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/admin/agents/memory"));
  expect(screen.getByRole("tab", { name: "Agent Memory" })).toHaveAttribute("aria-selected", "true");
});

test("the tabs sit in a rail of icons that shows and hides its labels like the conversation's", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/admin/agents/memory");
  const list = screen.getByRole("tablist", { name: "AI & Agent Settings" });
  expect(list).toHaveAttribute("aria-orientation", "vertical");
  expect(within(list).queryByText("Token Usage")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Show labels" }));
  expect(within(list).getByText("Token Usage")).toBeInTheDocument();
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("true");
  await user.click(screen.getByRole("button", { name: "Hide labels" }));
  expect(within(list).queryByText("Token Usage")).not.toBeInTheDocument();
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("false");
});

test("the labels follow the choice made on the other rails", () => {
  window.localStorage.setItem("studio.rail.expanded", "true");
  stubAll();
  show("/admin/agents/memory");
  const list = screen.getByRole("tablist", { name: "AI & Agent Settings" });
  expect(within(list).getByText("Models and Routing")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Hide labels" })).toBeInTheDocument();
});
