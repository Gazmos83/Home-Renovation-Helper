import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes, useLocation, useParams } from "react-router-dom";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { PRICING_VIEWS, PricingTab } from "./Pricing";

const entry = {
  key: "foam", label: "Foam", category: "panel", unit: "per_piece", base_cents: 999,
  provenance: "snapshot", source_url: "https://toom.de/p/y", captured_at: "2026-10-01T10:00:00Z",
  override_cents: null, override_note: null, effective_cents: 999, unconfirmed: false,
};
const snapshot = {
  id: "s1", retailer: "toom", url: "https://toom.de/p/y", product_name: "Foam", price: "9.99", currency: "EUR",
  specification: "5 cm", captured_on: "2026-10-01", availability: null, store_name: null,
};

function Address() {
  return <output aria-label="address">{useLocation().pathname}</output>;
}

/** The tab body with plain links standing in for the Design Studio sub-menu. */
function Tab() {
  const { view } = useParams();
  return (
    <>
      {PRICING_VIEWS.map((v) => (
        <Link key={v.id} to={`/studio/pricing/${v.id}`}>{v.label}</Link>
      ))}
      <PricingTab view={view} />
    </>
  );
}

function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/studio/pricing" element={<Tab />} />
          <Route path="/studio/pricing/:view" element={<Tab />} />
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

test("the views are Prices, Snapshots and Remnants, and the tab opens on Prices", async () => {
  stubAll();
  show("/studio/pricing");
  expect(PRICING_VIEWS.map((v) => v.label)).toEqual(["Prices", "Snapshots", "Remnants"]);
  expect(screen.getByRole("table")).toBeInTheDocument();
  expect(screen.queryByRole("form", { name: "Record a snapshot" })).not.toBeInTheDocument();
});

test("choosing a view changes the address and shows only that view", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/studio/pricing/prices");
  await user.click(screen.getByRole("link", { name: "Remnants" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/pricing/remnants");
  expect(await screen.findByText("The rack is empty.")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("form", { name: "Record a snapshot" })).not.toBeInTheDocument();
});

test("a view address opens that view", () => {
  stubAll();
  show("/studio/pricing/snapshots");
  expect(screen.getByRole("form", { name: "Record a snapshot" })).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("an unknown view opens Prices", async () => {
  stubAll();
  show("/studio/pricing/quotes");
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/studio/pricing/prices"));
  expect(screen.getByRole("table")).toBeInTheDocument();
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
  show("/studio/pricing/prices");
  await user.click(screen.getByRole("link", { name: "Snapshots" }));
  await user.type(await screen.findByLabelText("Page URL"), "https://toom.de/p/y");
  await user.type(screen.getByLabelText("Product name"), "Foam");
  await user.type(screen.getByLabelText("Price (€)"), "9,99");
  await user.type(screen.getByLabelText("Specification"), "5 cm");
  await user.type(screen.getByLabelText("Captured on"), "2026-10-01");
  await user.click(screen.getByLabelText("Also create a price-list entry"));
  await user.type(screen.getByLabelText("Entry key"), "foam");
  await user.click(screen.getByRole("button", { name: "Record snapshot" }));
  expect(await screen.findByRole("button", { name: "Delete Foam" })).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Prices" }));
  expect(await screen.findByText("Foam")).toBeInTheDocument();
});
