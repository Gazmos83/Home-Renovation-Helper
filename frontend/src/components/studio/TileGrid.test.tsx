import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { setScreenWidth } from "@/test/media";
import { carryPage, TileGrid } from "./TileGrid";

function Address() {
  const location = useLocation();
  return <output aria-label="address">{location.pathname + location.search}</output>;
}

function show(count: number, address = "/studio/models") {
  const items = Array.from({ length: count }, (_, i) => `Model ${i + 1}`);
  render(
    <MemoryRouter initialEntries={[address]}>
      <TileGrid label="Uploaded models" items={items} keyOf={(item) => item}>
        {(item) => <button type="button">{item}</button>}
      </TileGrid>
      <Address />
    </MemoryRouter>,
  );
}

const tiles = () => within(screen.getByRole("list", { name: "Uploaded models" })).getAllByRole("button").map((b) => b.textContent);
const address = () => screen.getByRole("status", { name: "address" }).textContent;

describe("TileGrid", () => {
  it("shows 16 tiles a page on a laptop (Laptop grid)", () => {
    show(20);
    expect(tiles()).toHaveLength(16);
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
    expect(screen.getByRole("list", { name: "Uploaded models" })).toHaveClass("lg:grid-cols-4", "lg:grid-rows-4");
  });

  it("shows 6 tiles a page on a phone (Phone grid)", () => {
    setScreenWidth(360);
    show(8);
    expect(tiles()).toEqual(["Model 1", "Model 2", "Model 3", "Model 4", "Model 5", "Model 6"]);
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Uploaded models" })).toHaveClass("grid-cols-2", "grid-rows-3");
  });

  it("keeps the page in the address (Page in the address)", () => {
    show(20);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(address()).toBe("/studio/models?page=2");
    expect(tiles()).toEqual(["Model 17", "Model 18", "Model 19", "Model 20"]);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(address()).toBe("/studio/models");
  });

  it("opens the page the address names", () => {
    show(20, "/studio/models?page=2");
    expect(tiles()[0]).toBe("Model 17");
  });

  it("clamps a page past the last", () => {
    show(20, "/studio/models?page=9");
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();
  });

  it("shows no paging with one page (One page only)", () => {
    show(3);
    expect(tiles()).toHaveLength(3);
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("shows nothing for no items", () => {
    show(0);
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("keeps the first shown tile when the width crosses the breakpoint", () => {
    show(40, "/studio/models?page=2");
    expect(tiles()[0]).toBe("Model 17");
    act(() => setScreenWidth(360));
    expect(tiles()[0]).toBe("Model 13");
    expect(tiles()).toContain("Model 17");
    expect(address()).toBe("/studio/models?page=3");
    expect(screen.getByText("Page 3 of 7")).toBeInTheDocument();
  });

  it("carries a page across page sizes", () => {
    expect(carryPage(2, 16, 6)).toBe(3);
    expect(carryPage(3, 6, 16)).toBe(1);
    expect(carryPage(1, 16, 6)).toBe(1);
  });
});
