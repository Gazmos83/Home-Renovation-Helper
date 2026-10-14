import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Pricing from "./Pricing";

const entry = {
  key: "foam", label: "Foam", category: "panel", unit: "per_piece", base_cents: 999,
  provenance: "snapshot", source_url: "https://toom.de/p/y", captured_at: "2026-10-01T10:00:00Z",
  override_cents: null, override_note: null, effective_cents: 999, unconfirmed: false,
};
const snapshot = {
  id: "s1", retailer: "toom", url: "https://toom.de/p/y", product_name: "Foam", price: "9.99", currency: "EUR",
  specification: "5 cm", captured_on: "2026-10-01", availability: null, store_name: null,
};

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
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/pricing/:tab" element={<Pricing />} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function stubAll(priceList: unknown[] = []) {
  return stubFetch((call) => {
    if (call.startsWith("GET /price-list")) return { body: priceList };
    if (call === "GET /snapshots") return { body: [] };
    if (call === "GET /remnants") return { body: [] };
  });
}

test("the page opens on the Prices tab", async () => {
  stubAll();
  show("/pricing");
  expect(screen.getByRole("heading", { level: 1, name: "Pricing Overview" })).toBeInTheDocument();
  const tabs = screen.getAllByRole("tab").map((tab) => tab.getAttribute("aria-label"));
  expect(tabs).toEqual(["Prices", "Snapshots", "Remnants"]);
  expect(screen.getByRole("tab", { name: "Prices" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("table")).toBeInTheDocument();
});

test("choosing a tab changes the address and shows only that tab", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/pricing/prices");
  await user.click(screen.getByRole("tab", { name: "Remnants" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/pricing/remnants");
  expect(screen.getByRole("tab", { name: "Remnants" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Prices" })).toHaveAttribute("aria-selected", "false");
  expect(await screen.findByText("The rack is empty.")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("form", { name: "Record a snapshot" })).not.toBeInTheDocument();
});

test("a tab address opens that tab", () => {
  stubAll();
  show("/pricing/snapshots");
  expect(screen.getByRole("tab", { name: "Snapshots" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("form", { name: "Record a snapshot" })).toBeInTheDocument();
});

test("an unknown tab opens Prices", async () => {
  stubAll();
  show("/pricing/quotes");
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/pricing/prices"));
  expect(screen.getByRole("tab", { name: "Prices" })).toHaveAttribute("aria-selected", "true");
});

test("an entry prefilled from a snapshot is listed on the Prices tab without a reload", async () => {
  const user = userEvent.setup();
  let recorded = false;
  stubFetch((call) => {
    if (call.startsWith("GET /price-list")) return { body: recorded ? [entry] : [] };
    if (call === "GET /snapshots") return { body: recorded ? [snapshot] : [] };
    if (call === "POST /snapshots") {
      recorded = true;
      return { status: 201, body: snapshot };
    }
  });
  show("/pricing/prices");
  await user.click(screen.getByRole("tab", { name: "Snapshots" }));
  await user.type(await screen.findByLabelText("Page URL"), "https://toom.de/p/y");
  await user.type(screen.getByLabelText("Product name"), "Foam");
  await user.type(screen.getByLabelText("Price (€)"), "9,99");
  await user.type(screen.getByLabelText("Specification"), "5 cm");
  await user.type(screen.getByLabelText("Captured on"), "2026-10-01");
  await user.click(screen.getByLabelText("Also create a price-list entry"));
  await user.type(screen.getByLabelText("Entry key"), "foam");
  await user.click(screen.getByRole("button", { name: "Record snapshot" }));
  expect(await screen.findByRole("button", { name: "Delete Foam" })).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "Prices" }));
  expect(await screen.findByText("Foam")).toBeInTheDocument();
});

test("the tabs sit in a rail of icons that shows and hides its labels like the conversation's", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/pricing/prices");
  const list = screen.getByRole("tablist", { name: "Pricing Overview" });
  expect(list).toHaveAttribute("aria-orientation", "vertical");
  expect(within(list).queryByText("Snapshots")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Show labels" }));
  expect(within(list).getByText("Snapshots")).toBeInTheDocument();
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("true");
  await user.click(screen.getByRole("button", { name: "Hide labels" }));
  expect(within(list).queryByText("Snapshots")).not.toBeInTheDocument();
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("false");
});

test("the labels follow the choice made on the conversation's rail", () => {
  window.localStorage.setItem("studio.rail.expanded", "true");
  stubAll();
  show("/pricing/remnants");
  const list = screen.getByRole("tablist", { name: "Pricing Overview" });
  expect(within(list).getByText("Prices")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Hide labels" })).toBeInTheDocument();
});
