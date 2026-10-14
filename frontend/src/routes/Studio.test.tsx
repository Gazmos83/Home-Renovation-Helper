import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import { stubFetch } from "../test/fetchStub";
import Studio from "./Studio";

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
          <Route path="/studio" element={<Studio />} />
          <Route path="/studio/:tab" element={<Studio />} />
        </Routes>
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function stubAll() {
  return stubFetch((call) => {
    if (call === "GET /packages") return { body: [] };
    if (call === "GET /rooms") return { body: [] };
    if (call === "GET /compositions") return { body: [] };
    if (call === "GET /models") return { body: [] };
  });
}

test("the page opens on the Pieces tab", async () => {
  stubAll();
  show("/studio");
  expect(screen.getByRole("heading", { level: 1, name: "Design Studio" })).toBeInTheDocument();
  const tabs = screen.getAllByRole("tab").map((tab) => tab.getAttribute("aria-label"));
  expect(tabs).toEqual(["Pieces", "Measured Rooms", "Model Library"]);
  expect(screen.getByRole("tab", { name: "Pieces" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByRole("button", { name: "Create A New Piece" })).toBeInTheDocument();
});

test("choosing a tab changes the address and shows only that tab", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/studio/pieces");
  await user.click(screen.getByRole("tab", { name: "Model Library" }));
  expect(screen.getByLabelText("address")).toHaveTextContent("/studio/models");
  expect(screen.getByRole("tab", { name: "Model Library" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Pieces" })).toHaveAttribute("aria-selected", "false");
  expect(await screen.findByText("No models yet.")).toBeInTheDocument();
  expect(screen.getByRole("form", { name: "Upload a model" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Create A New Piece" })).not.toBeInTheDocument();
  expect(screen.queryByText(/No rooms measured yet/)).not.toBeInTheDocument();
});

test("a tab address opens that tab", async () => {
  stubAll();
  show("/studio/rooms");
  expect(screen.getByRole("tab", { name: "Measured Rooms" })).toHaveAttribute("aria-selected", "true");
  expect(await screen.findByText(/No rooms measured yet/)).toBeInTheDocument();
});

test("an unknown tab opens Pieces", async () => {
  stubAll();
  show("/studio/quotes");
  await waitFor(() => expect(screen.getByLabelText("address")).toHaveTextContent("/studio/pieces"));
  expect(screen.getByRole("tab", { name: "Pieces" })).toHaveAttribute("aria-selected", "true");
});

test("the tabs sit in a rail of icons that shows and hides its labels like the conversation's", async () => {
  const user = userEvent.setup();
  stubAll();
  show("/studio/pieces");
  const list = screen.getByRole("tablist", { name: "Design Studio" });
  expect(list).toHaveAttribute("aria-orientation", "vertical");
  expect(within(list).queryByText("Model Library")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Show labels" }));
  expect(within(list).getByText("Model Library")).toBeInTheDocument();
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("true");
  await user.click(screen.getByRole("button", { name: "Hide labels" }));
  expect(within(list).queryByText("Model Library")).not.toBeInTheDocument();
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("false");
});

test("the labels follow the choice made on another rail", () => {
  window.localStorage.setItem("studio.rail.expanded", "true");
  stubAll();
  show("/studio/models");
  const list = screen.getByRole("tablist", { name: "Design Studio" });
  expect(within(list).getByText("Measured Rooms")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Hide labels" })).toBeInTheDocument();
});
