import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { Rail } from "./Rail";

const panels = [
  { id: "brief", label: "Brief", icon: "brief" as const, content: <p>brief facts</p> },
  { id: "project", label: "Project", icon: "project" as const, content: <p>project facts</p> },
];

function Harness() {
  const [open, setOpen] = useState<string | null>(null);
  return <Rail panels={panels} open={open} onOpen={setOpen} />;
}

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

test("the rail is collapsed to icons until the owner shows the labels, and remembers the choice", () => {
  const { unmount } = render(<Harness />);
  const toggle = screen.getByRole("button", { name: "Show labels" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("navigation", { name: "Panels" })).toHaveClass("w-12");

  fireEvent.click(toggle);
  const hide = screen.getByRole("button", { name: "Hide labels" });
  expect(hide).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("navigation", { name: "Panels" })).toHaveClass("w-36");
  expect(window.localStorage.getItem("studio.rail.expanded")).toBe("true");

  unmount();
  render(<Harness />);
  expect(screen.getByRole("button", { name: "Hide labels" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Hide labels" }));
  expect(screen.getByRole("button", { name: "Show labels" })).toBeInTheDocument();
});

test("a browser that cannot store the choice shows the rail collapsed without an error", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  render(<Harness />);
  expect(screen.getByRole("navigation", { name: "Panels" })).toHaveClass("w-12");
  fireEvent.click(screen.getByRole("button", { name: "Show labels" }));
  expect(screen.getByRole("navigation", { name: "Panels" })).toHaveClass("w-36");
});

test("a panel opens, switches, and closes with its button, another icon or Escape", () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "Brief" }));
  expect(screen.getByRole("dialog", { name: "Brief" })).toBeInTheDocument();
  expect(screen.getByText("brief facts")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Project" }));
  expect(screen.getByRole("dialog", { name: "Project" })).toBeInTheDocument();
  expect(screen.queryByText("brief facts")).not.toBeInTheDocument();

  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Brief" }));
  fireEvent.click(screen.getByRole("button", { name: "Close Brief" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("the flyout opens beside the rail's current width", () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "Brief" }));
  expect(screen.getByRole("dialog", { name: "Brief" })).toHaveClass("left-14");
  fireEvent.click(screen.getByRole("button", { name: "Show labels" }));
  expect(screen.getByRole("dialog", { name: "Brief" })).toHaveClass("left-[9.5rem]");
});

test("an action entry opens no dialog and closes an open flyout", () => {
  const onSelect = vi.fn();
  function WithAction() {
    const [open, setOpen] = useState<string | null>(null);
    return (
      <Rail
        variant="row"
        panels={[...panels, { id: "piece", label: "Piece", icon: "piece", onSelect }]}
        open={open}
        onOpen={setOpen}
      />
    );
  }
  render(<WithAction />);
  fireEvent.click(screen.getByRole("button", { name: "Brief" }));
  expect(screen.getByRole("dialog", { name: "Brief" })).toBeInTheDocument();

  const piece = screen.getByRole("button", { name: "Piece" });
  expect(piece).not.toHaveAttribute("aria-expanded");
  expect(piece).toHaveAttribute("title", "Piece");
  fireEvent.click(piece);
  expect(onSelect).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
