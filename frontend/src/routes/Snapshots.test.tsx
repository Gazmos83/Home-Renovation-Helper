import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Snapshots from "./Snapshots";

const row = {
  id: "s1", retailer: "toom", url: "https://toom.de/p/x", product_name: "Birch ply", price: "42.00",
  currency: "EUR", availability: null, specification: "18 mm", store_name: null, captured_on: "2026-10-01",
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Snapshots /></QueryClientProvider>);
}

test("a snapshot is listed and can be deleted", async () => {
  const calls = stubFetch((call) => {
    if (call === "GET /snapshots") return { body: [row] };
    if (call === "DELETE /snapshots/s1") return { status: 204 };
  });
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Delete Birch ply" }));
  expect(calls.some(([m, u]) => m === "DELETE" && u === "/snapshots/s1")).toBe(true);
});

test("a future date is refused next to the date field", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /snapshots") return { body: [] };
    if (call === "POST /snapshots") {
      return { status: 422, body: { detail: { failure_class: "invalid_snapshot", reason: "captured_on: must not be in the future", field: "captured_on" } } };
    }
  });
  show();
  await user.type(await screen.findByLabelText("Page URL"), "https://toom.de/p/y");
  await user.type(screen.getByLabelText("Product name"), "Foam");
  await user.type(screen.getByLabelText("Specification"), "5 cm");
  await user.type(screen.getByLabelText("Captured on"), "2999-01-01");
  await user.click(screen.getByRole("button", { name: "Record snapshot" }));
  const message = await screen.findByText("captured_on: must not be in the future");
  expect(message.previousElementSibling).toBe(screen.getByLabelText("Captured on"));
});

test("a snapshot can prefill a price-list entry", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => (call === "GET /snapshots" ? { body: [] } : call === "POST /snapshots" ? { status: 201, body: row } : undefined));
  show();
  await user.type(await screen.findByLabelText("Page URL"), "https://toom.de/p/y");
  await user.type(screen.getByLabelText("Product name"), "Foam");
  await user.type(screen.getByLabelText("Price (€)"), "9,99");
  await user.type(screen.getByLabelText("Specification"), "5 cm");
  await user.type(screen.getByLabelText("Captured on"), "2026-10-01");
  await user.click(screen.getByLabelText("Also create a price-list entry"));
  await user.type(screen.getByLabelText("Entry key"), "foam");
  await user.click(screen.getByRole("button", { name: "Record snapshot" }));
  await screen.findByRole("button", { name: "Record snapshot" });
  const body = calls.find(([m, u]) => m === "POST" && u === "/snapshots")![2] as { price: string; prefill: { key: string } };
  expect(body.price).toBe("9.99");
  expect(body.prefill.key).toBe("foam");
});
