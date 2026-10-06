import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import PriceList from "./PriceList";

const captured = {
  key: "panel:birch:18", label: "Birch 18 mm", category: "panel", unit: "per_piece", base_cents: 6000,
  provenance: "captured", source_url: "https://toom.de/p/x", captured_at: "2026-10-01T10:00:00Z",
  override_cents: null, override_note: null, effective_cents: 6000, unconfirmed: false,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PriceList /></QueryClientProvider>);
}

test("entries show their effective price, provenance and capture date", async () => {
  stubFetch((call) => (call === "GET /price-list" ? { body: [captured] } : undefined));
  show();
  expect(await screen.findByText("Birch 18 mm")).toBeInTheDocument();
  expect(screen.getByText("60,00 €")).toBeInTheDocument();
  expect(screen.getByText("captured")).toBeInTheDocument();
  expect(screen.getByText(/captured 2026-10-01/)).toBeInTheDocument();
});

test("the filter asks the API for one category", async () => {
  const calls = stubFetch((call) => (call.startsWith("GET /price-list") ? { body: [] } : undefined));
  show();
  await userEvent.selectOptions(await screen.findByLabelText("Category", { selector: "#filter" }), "hardware");
  await screen.findByRole("table");
  expect(calls.some(([, url]) => url === "/price-list?category=hardware")).toBe(true);
});

test("a manual entry is sent in cents, and a refusal names its field", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /price-list") return { body: [] };
    if (call === "POST /price-list") return { status: 422, body: { detail: { failure_class: "refused", reason: "that key exists", field: "key" } } };
  });
  show();
  const form = await screen.findByRole("form", { name: "Add an entry" });
  await user.type(form.querySelector("#add-key")!, "hinge");
  await user.type(form.querySelector("#add-label")!, "Hinge");
  await user.type(form.querySelector("#add-price")!, "2,50");
  await user.click(screen.getByRole("button", { name: "Add" }));
  expect(await screen.findByText("that key exists")).toBeInTheDocument();
  expect(calls.find(([m, u]) => m === "POST" && u === "/price-list")![2]).toMatchObject({ key: "hinge", base_cents: 250 });
});

test("an override is set in cents and a refresh outcome is shown", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /price-list") return { body: [captured] };
    if (call.startsWith("PUT /price-list/panel%3Abirch%3A18/override")) return { body: { ...captured, override_cents: 5500 } };
    if (call.startsWith("POST") && call.endsWith("/refresh")) {
      return { body: { outcome: "refused", reason: "toom answered 403", entry: null } };
    }
  });
  show();
  await user.type(await screen.findByLabelText("override for panel:birch:18"), "55");
  await user.click(screen.getByRole("button", { name: "Set override on panel:birch:18" }));
  await user.click(screen.getByRole("button", { name: "Refresh panel:birch:18" }));
  expect(await screen.findByText(/Not refreshed \(refused\): toom answered 403/)).toBeInTheDocument();
  expect(calls.find(([m]) => m === "PUT")![2]).toEqual({ cents: 5500, note: null });
});

test("a pasted URL that is refused shows the reason", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /price-list") return { body: [] };
    if (call === "POST /price-list/from-url") {
      return { status: 422, body: { detail: { failure_class: "source_not_permitted", reason: "bauhaus.info is not a permitted source" } } };
    }
  });
  show();
  await user.type(await screen.findByLabelText("toom product URL"), "https://www.bauhaus.info/x");
  await user.type(screen.getByLabelText("Key", { selector: "#url-key" }), "foam");
  await user.click(screen.getByRole("button", { name: "Create from URL" }));
  expect(await screen.findByText("bauhaus.info is not a permitted source")).toBeInTheDocument();
});

test("a panel entry carries its sheet size", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => (call === "GET /price-list" ? { body: [] } : call === "POST /price-list" ? { status: 201, body: captured } : undefined));
  show();
  const form = await screen.findByRole("form", { name: "Add an entry" });
  await user.selectOptions(form.querySelector("#add-category")!, "panel");
  await user.type(form.querySelector("#add-key")!, "panel:birch:18");
  await user.type(form.querySelector("#add-label")!, "Birch");
  await user.type(form.querySelector("#add-price")!, "60");
  await user.type(form.querySelector("#add-sheet-length")!, "2500");
  await user.type(form.querySelector("#add-sheet-width")!, "1250");
  await user.type(form.querySelector("#add-thickness")!, "18");
  await user.click(screen.getByRole("button", { name: "Add" }));
  await screen.findByRole("form", { name: "Add an entry" });
  expect(calls.find(([m, u]) => m === "POST" && u === "/price-list")![2]).toMatchObject({
    category: "panel", sheet_length_mm: 2500, sheet_width_mm: 1250, thickness_mm: 18, base_cents: 6000,
  });
});
