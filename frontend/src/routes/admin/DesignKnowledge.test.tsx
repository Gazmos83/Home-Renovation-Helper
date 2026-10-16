import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes, useLocation, useParams } from "react-router-dom";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import { DesignKnowledgeTab, KNOWLEDGE_VIEWS } from "./DesignKnowledge";

function Address() {
  return <output aria-label="address">{useLocation().pathname}</output>;
}

/** The tab body with plain links standing in for the Design Studio sub-menu. */
function Tab() {
  const { tab } = useParams();
  return (
    <>
      {KNOWLEDGE_VIEWS.map((v) => (
        <Link key={v.id} to={`/admin/design-knowledge/${v.id}`}>{v.label}</Link>
      ))}
      <DesignKnowledgeTab view={tab} />
    </>
  );
}

function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/admin/design-knowledge" element={<Tab />} />
          <Route path="/admin/design-knowledge/:tab" element={<Tab />} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const urls = (calls: [string, string, unknown][]) => calls.map(([, url]) => url);

test("the tab opens on Guidelines with the views in the owner's order", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/guidelines") return { body: [] };
    if (call === "GET /guideline-notes") return { body: [] };
    if (call === "GET /hardware-data") return { body: [] };
  });
  show("/admin/design-knowledge");
  expect(KNOWLEDGE_VIEWS.map((v) => v.label)).toEqual(["Guidelines", "Engineering Knowledge", "Design Rules"]);
  expect(await screen.findByRole("heading", { name: "Guideline PDFs" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Guideline notes" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Hardware data" })).toBeInTheDocument();
});

test("choosing a view changes the address and shows only that view", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /admin/guidelines") return { body: [] };
    if (call === "GET /guideline-notes") return { body: [] };
    if (call === "GET /hardware-data") return { body: [] };
  });
  show("/admin/design-knowledge/guidelines");
  await screen.findByRole("heading", { name: "Guideline PDFs" });
  await user.click(screen.getByRole("link", { name: "Design Rules" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/admin/design-knowledge/rules");
  await waitFor(() => expect(urls(calls)).toContain("/admin/rules"));
  expect(screen.queryByRole("heading", { name: "Guideline PDFs" })).not.toBeInTheDocument();
});

test("a view address opens that view and loads only its content", async () => {
  const calls = stubFetch((call) => (call === "GET /admin/knowledge" ? { body: [] } : undefined));
  show("/admin/design-knowledge/engineering");
  await waitFor(() => expect(urls(calls)).toContain("/admin/knowledge"));
  expect(urls(calls)).not.toContain("/admin/guidelines");
  expect(urls(calls)).not.toContain("/admin/rules");
});

test("an unknown view opens Guidelines", async () => {
  stubFetch(() => undefined);
  show("/admin/design-knowledge/quotes");
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/admin/design-knowledge/guidelines"));
  expect(await screen.findByRole("heading", { name: "Guideline PDFs" })).toBeInTheDocument();
});
