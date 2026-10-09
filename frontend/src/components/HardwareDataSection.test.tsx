import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { stubFetch } from "../test/fetchStub";
import { HardwareDataSection, measureText, parseMeasure } from "./HardwareDataSection";

afterEach(() => vi.unstubAllGlobals());

const hinge = {
  id: "h1", key: "hinge-concealed-110", kind: "hinge", maker: "Hettich", model: "Sensys 110",
  values: { cup_diameter_mm: { value: 35 }, end_distance_mm: { min: 80, max: 120 } },
  source_kind: "toom", page_url: "https://www.toom.de/p/hinge/1", datasheet_url: null,
  citation: "https://www.toom.de/p/hinge/1", updated_at: "2026-10-08T00:00:00Z",
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><HardwareDataSection /></QueryClientProvider>);
}

test("a data sheet lists its values with a range shown as min–max and a blank one as missing", async () => {
  stubFetch((call) => (call === "GET /hardware-data" ? { body: [hinge] } : undefined));
  show();
  const card = await screen.findByRole("region", { name: "hinge-concealed-110" });
  expect(within(card).getByText("Cup Ø: 35 mm")).toBeInTheDocument();
  expect(within(card).getByText("End distance from the door ends: 80–120 mm")).toBeInTheDocument();
  expect(within(card).getByText("Cup edge distance:")).toBeInTheDocument();
  expect(within(card).getAllByText("missing").length).toBeGreaterThan(0);
  expect(within(card).getByText("Source: https://www.toom.de/p/hinge/1")).toBeInTheDocument();
});

test("a value is entered as one number or a range and sent as such, blanks left out", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /hardware-data") return { body: [] };
    if (call === "POST /hardware-data") return { status: 201, body: hinge };
  });
  show();
  const form = await screen.findByRole("form", { name: "Add hardware data" });
  await user.type(within(form).getByLabelText("Item key"), "hinge-concealed-110");
  await user.type(within(form).getByLabelText("Maker"), "Hettich");
  await user.type(within(form).getByLabelText("Model"), "Sensys 110");
  await user.type(within(form).getByLabelText("toom page URL"), "https://www.toom.de/p/hinge/1");
  await user.type(within(form).getByLabelText("Cup Ø"), "35");
  await user.type(within(form).getByLabelText("End distance from the door ends"), "80–120");
  await user.click(within(form).getByRole("button", { name: "Add data sheet" }));
  const body = calls.find(([method]) => method === "POST")![2];
  expect(body).toMatchObject({
    key: "hinge-concealed-110", kind: "hinge", source_kind: "toom",
    values: { cup_diameter_mm: { value: 35 }, end_distance_mm: { min: 80, max: 120 } },
  });
  expect((body as { values: Record<string, unknown> }).values).not.toHaveProperty("cup_edge_distance_mm");
});

test("a page off toom is refused next to the page URL", async () => {
  const user = userEvent.setup();
  stubFetch((call) => {
    if (call === "GET /hardware-data") return { body: [] };
    if (call === "POST /hardware-data") {
      return { status: 422, body: { detail: { failure_class: "refused", reason: "a toom source must be a toom page", field: "page_url" } } };
    }
  });
  show();
  const form = await screen.findByRole("form", { name: "Add hardware data" });
  await user.type(within(form).getByLabelText("Item key"), "x");
  await user.type(within(form).getByLabelText("toom page URL"), "https://example.com/p");
  await user.click(within(form).getByRole("button", { name: "Add data sheet" }));
  const message = await screen.findByText("a toom source must be a toom page");
  expect(message.previousElementSibling).toBe(within(form).getByLabelText("toom page URL"));
});

test("a sheet can be edited and deleted", async () => {
  const user = userEvent.setup();
  const calls = stubFetch((call) => {
    if (call === "GET /hardware-data") return { body: [hinge] };
    if (call === "PUT /hardware-data/h1") return { body: hinge };
    if (call === "DELETE /hardware-data/h1") return { status: 204 };
  });
  show();
  await user.click(await screen.findByRole("button", { name: "Edit hinge-concealed-110" }));
  const form = screen.getByRole("form", { name: "Edit hinge-concealed-110" });
  expect(within(form).getByLabelText("End distance from the door ends")).toHaveValue("80–120");
  await user.click(within(form).getByRole("button", { name: "Save data sheet" }));
  await user.click(await screen.findByRole("button", { name: "Delete hinge-concealed-110" }));
  const put = calls.find(([method]) => method === "PUT")!;
  expect(put[2]).toMatchObject({ values: { cup_diameter_mm: { value: 35 }, end_distance_mm: { min: 80, max: 120 } } });
  expect(put[2]).not.toHaveProperty("key");
  expect(calls.some(([m, u]) => m === "DELETE" && u === "/hardware-data/h1")).toBe(true);
});

test("a range typed for the pins per shelf count is sent as a range so the service names it", () => {
  expect(parseMeasure("4", true)).toBe(4);
  expect(parseMeasure("4–6", true)).toEqual({ min: 4, max: 6 });
  expect(parseMeasure("", true)).toBeUndefined();
  expect(parseMeasure("32,5")).toEqual({ value: 32.5 });
  expect(measureText({ min: 80, max: 120 })).toBe("80–120");
});
