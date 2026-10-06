import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Remnants from "./Remnants";

const rack = { id: "r1", material_key: "panel:birch:18", length_mm: 800, width_mm: 400, grain_axis: "length", quantity: 2 };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Remnants /></QueryClientProvider>);
}

test("a remnant is added with numbers and removed again", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /remnants") return { body: [rack] };
    if (call === "POST /remnants") return { status: 201, body: rack };
    if (call === "DELETE /remnants/r1") return { status: 204 };
  });
  show();
  expect(await screen.findByText(/2 × panel:birch:18, 800 × 400 mm/)).toBeInTheDocument();
  await user.type(screen.getByLabelText("Material key"), "panel:birch:18");
  await user.type(screen.getByLabelText("Length (mm)"), "800");
  await user.type(screen.getByLabelText("Width (mm)"), "400");
  await user.click(screen.getByRole("button", { name: "Add remnant" }));
  await user.click(screen.getByRole("button", { name: "Remove panel:birch:18 800×400" }));
  expect(calls.find(([m, u]) => m === "POST" && u === "/remnants")![2]).toEqual({
    material_key: "panel:birch:18", length_mm: 800, width_mm: 400, grain_axis: "length", quantity: 1,
  });
  expect(calls.some(([m, u]) => m === "DELETE" && u === "/remnants/r1")).toBe(true);
});

test("a refused remnant names the field", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /remnants") return { body: [] };
    if (call === "POST /remnants") return { status: 422, body: { detail: { failure_class: "refused", reason: "unknown material", field: "material_key" } } };
  });
  show();
  await user.type(await screen.findByLabelText("Material key"), "nope");
  await user.click(screen.getByRole("button", { name: "Add remnant" }));
  expect(await screen.findByText("unknown material")).toBeInTheDocument();
});
