import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { SubMenu } from "./SubMenu";

const ITEMS = [
  { id: "uploaded", label: "Uploaded models", to: "/studio/models" },
  { id: "upload", label: "Upload model", to: "/studio/models/upload" },
];

function show(layout: "column" | "row") {
  render(
    <MemoryRouter>
      <SubMenu label="Model Library views" items={ITEMS} current="uploaded" layout={layout} />
    </MemoryRouter>,
  );
  return screen.getByRole("navigation", { name: "Model Library views" });
}

describe("SubMenu", () => {
  it("is a column from 768 px wide, with every label and the chosen view marked", () => {
    const nav = show("column");
    expect(nav).toHaveClass("hidden", "md:flex", "flex-col", "border-r");
    expect(screen.getByRole("link", { name: "Uploaded models" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Upload model" })).toHaveAttribute("href", "/studio/models/upload");
    expect(screen.getByRole("link", { name: "Upload model" })).not.toHaveAttribute("aria-current");
  });

  it("is a scrolling tab row below 768 px", () => {
    const nav = show("row");
    expect(nav).toHaveClass("flex", "md:hidden", "overflow-x-auto");
    expect(nav).not.toHaveClass("flex-col");
  });

  it("cuts a long name short, shows it in full on hover, and scrolls a long list", () => {
    const long = "a-very-long-piece-name-that-does-not-fit-the-column";
    render(
      <MemoryRouter>
        <SubMenu label="Pieces" items={[{ id: long, label: long, to: `/studio/pieces/${long}` }]} current={null} layout="column" />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: long });
    expect(link).toHaveAttribute("title", long);
    expect(link.querySelector("span")).toHaveClass("truncate");
    expect(link).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("navigation", { name: "Pieces" })).toHaveClass("overflow-y-auto");
  });

  it("says when there is nothing to list", () => {
    render(
      <MemoryRouter>
        <SubMenu label="Pieces" items={[]} current={null} layout="column" empty="No pieces yet" />
      </MemoryRouter>,
    );
    expect(screen.getByText("No pieces yet")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("gives the column an x and the row none", () => {
    const onClose = vi.fn();
    const { unmount } = render(
      <MemoryRouter>
        <SubMenu label="Pricing views" items={ITEMS} current={null} layout="column" onClose={onClose} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Close Pricing views" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    unmount();

    render(
      <MemoryRouter>
        <SubMenu label="Pricing views" items={ITEMS} current={null} layout="row" onClose={onClose} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("button", { name: "Close Pricing views" })).toBeNull();
  });
});
