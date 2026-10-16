import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Bubble } from "./Bubble";

test("a compact bubble is on the left, light, with its speaker inline before the text", () => {
  render(<Bubble side="right" speaker="You" compact><p>Make it narrower</p></Bubble>);
  const outer = screen.getByText("Make it narrower").closest("[data-side]")!;
  expect(outer).toHaveAttribute("data-side", "left");
  const row = outer.firstElementChild!;
  expect(row).toHaveClass("flex", "border");
  expect(row).not.toHaveClass("bg-primary");
  expect(row.firstElementChild).toHaveTextContent("You:");
});

test("without compact the owner's bubble stays on the right with its speaker above", () => {
  render(<Bubble side="right" speaker="You"><p>Make it narrower</p></Bubble>);
  const outer = screen.getByText("Make it narrower").closest("[data-side]")!;
  expect(outer).toHaveAttribute("data-side", "right");
  expect(outer.firstElementChild).toHaveTextContent("You");
  expect(outer.lastElementChild).toHaveClass("bg-primary");
});
