import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../../test/fetchStub";
import Rules from "./Rules";

const fileRule = {
  id: "shelf-bracket-count", origin: "file", valid: true, problem: null, applies_to: "piece",
  check: "shelf_bracket_count_for_length", params: { table: [] }, severity: "warn",
  source: { publication: "topnotch-shelf-brackets", section: "How many", quote: "Up to 60cm: 2 brackets" },
};
const panelRule = {
  id: "shelf-span", origin: "panel", valid: false, problem: "rule 'shelf-span': source 'owner:x' names an owner note that does not exist",
  applies_to: "piece", check: "shelf_span_mm_for_thickness", params: { table: [] }, severity: "warn",
  source: { publication: "owner:x", section: "p. 1", quote: "q" },
};
const payload = {
  rules: [fileRule, panelRule],
  checks: [{ name: "shelf_span_mm_for_thickness", applies_to: "piece" }],
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Rules />
    </QueryClientProvider>,
  );
}

test("rules show their origin and source, an invalid one says why, and open items are listed", async () => {
  stubFetch((call) => {
    if (call === "GET /admin/rules") return { body: payload };
    if (call === "GET /admin/open-items")
      return { body: [{ file: "config/design_rules.yaml", line: 57, text: "even_tolerance_mm is your own" }] };
    if (call === "GET /admin/guidelines") return { body: [] };
    if (call === "GET /guideline-notes") return { body: [] };
  });
  show();
  expect(await screen.findByText("(checked-in table)")).toBeInTheDocument();
  expect(screen.getByText(/Not in force: .*does not exist/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  expect(await screen.findByText("config/design_rules.yaml:57")).toBeInTheDocument();
});

test("a new rule is saved with its check, parameters and a note as its source", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /admin/rules") return { body: payload };
    if (call === "GET /admin/open-items") return { body: [] };
    if (call === "GET /admin/guidelines") return { body: [] };
    if (call === "GET /guideline-notes")
      return { body: [{ id: "n1", title: "Span table", body: "", value: null, unit: null, citation: "book p. 3" }] };
    if (call === "PUT /admin/rules/span-18") return { body: payload };
  });
  show();
  const user = userEvent.setup();
  await screen.findByText("Add a rule");
  await user.type(screen.getByLabelText("Id"), "span-18");
  await user.selectOptions(screen.getByLabelText("Check"), "shelf_span_mm_for_thickness");
  const params = screen.getByLabelText("Parameters (JSON)");
  await user.clear(params);
  await user.click(params);
  await user.paste('{"table": [{"thickness_mm": 18, "max_span_mm": 800}]}');
  await screen.findByRole("option", { name: "Your note: Span table" });
  await user.selectOptions(screen.getByLabelText("Source"), "owner:n1");
  await user.type(screen.getByLabelText("Section"), "p. 3");
  await user.type(screen.getByLabelText("Quoted clause"), "18 mm: 800 mm");
  await user.click(screen.getByRole("button", { name: "Save rule" }));
  const put = calls.find(([method, url]) => method === "PUT" && url === "/admin/rules/span-18");
  expect(put?.[2]).toEqual({
    id: "span-18", check: "shelf_span_mm_for_thickness", applies_to: "piece",
    params: { table: [{ thickness_mm: 18, max_span_mm: 800 }] }, severity: "warn",
    source: { publication: "owner:n1", section: "p. 3", quote: "18 mm: 800 mm" },
  });
});
