import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes, useLocation, useParams } from "react-router-dom";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import { AGENT_VIEWS, AgentSettingsTab } from "./AgentSettings";

const memoryDefaults = {
  trigger_percent: 100, keep_turns: 0, note_tokens: 400, note_instructions: "You keep the notes.", tool_result_chars: 300,
  reviews: "auto", save_preferences: true, other_builds: "line", include_preferences: true,
  include_review_items: true, render_ratings: 5, include_extension_requests: true,
};
const memory = { settings: memoryDefaults, defaults: memoryDefaults, fixed_rules: ["Generator-extension requests are always saved."] };

function Address() {
  return <output aria-label="address">{useLocation().pathname}</output>;
}

/** The tab body with plain links standing in for the Design Studio sub-menu. */
function Tab() {
  const { tab } = useParams();
  return (
    <>
      {AGENT_VIEWS.map((v) => (
        <Link key={v.id} to={`/admin/agents/${v.id}`}>{v.label}</Link>
      ))}
      <AgentSettingsTab view={tab} />
    </>
  );
}

function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/admin/agents" element={<Tab />} />
          <Route path="/admin/agents/:tab" element={<Tab />} />
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

test("the tab opens on Agent Memory with the views in the owner's order", async () => {
  stubAll();
  show("/admin/agents");
  expect(AGENT_VIEWS.map((v) => v.label)).toEqual([
    "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins", "Models and Routing", "Accounts",
  ]);
  expect(await screen.findByText("Generator-extension requests are always saved.")).toBeInTheDocument();
});

test("choosing a view changes the address and shows only that view", async () => {
  const user = userEvent.setup();
  const calls = stubAll();
  show("/admin/agents/memory");
  await screen.findByText("Generator-extension requests are always saved.");
  await user.click(screen.getByRole("link", { name: "Token Usage" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/admin/agents/usage");
  expect(await screen.findByRole("table")).toBeInTheDocument();
  expect(screen.queryByText("Generator-extension requests are always saved.")).not.toBeInTheDocument();
  expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("GET /admin/usage?days=1");
});

test("a view address opens that view and loads only its content", async () => {
  const calls = stubFetch((call) => (call === "GET /admin/offload" ? { status: 503, body: { detail: "down" } } : undefined));
  show("/admin/agents/offload");
  await waitFor(() => expect(calls.map(([method, url]) => `${method} ${url}`)).toContain("GET /admin/offload"));
  expect(calls.map(([, url]) => url)).not.toContain("/admin/memory");
});

test("an unknown view opens Agent Memory", async () => {
  stubAll();
  show("/admin/agents/quotes");
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/admin/agents/memory"));
  expect(await screen.findByText("Generator-extension requests are always saved.")).toBeInTheDocument();
});
