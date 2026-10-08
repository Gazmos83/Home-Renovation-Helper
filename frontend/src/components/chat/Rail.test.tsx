import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { Rail } from "./Rail";

const panels = [
  { id: "tools", label: "Tools", icon: "tools" as const, content: <p>tool list</p> },
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
  fireEvent.click(screen.getByRole("button", { name: "Tools" }));
  expect(screen.getByRole("dialog", { name: "Tools" })).toBeInTheDocument();
  expect(screen.getByText("tool list")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Project" }));
  expect(screen.getByRole("dialog", { name: "Project" })).toBeInTheDocument();
  expect(screen.queryByText("tool list")).not.toBeInTheDocument();

  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Tools" }));
  fireEvent.click(screen.getByRole("button", { name: "Close Tools" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("the flyout opens beside the rail's current width", () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole("button", { name: "Tools" }));
  expect(screen.getByRole("dialog", { name: "Tools" })).toHaveClass("left-14");
  fireEvent.click(screen.getByRole("button", { name: "Show labels" }));
  expect(screen.getByRole("dialog", { name: "Tools" })).toHaveClass("left-[9.5rem]");
});
