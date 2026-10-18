import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { Reply } from "./Reply";

afterEach(() => vi.restoreAllMocks());

const ANSWER = "The gap between the murphy bed and wall 3 is 1350 mm.\n\n```calc\n5700 - 1350 - 3000 = 1350\n```";

test("the maths is hidden at first behind a Show the maths button", () => {
  render(<Reply text={ANSWER} />);
  expect(screen.getByText("The gap between the murphy bed and wall 3 is 1350 mm.")).toBeInTheDocument();
  const button = screen.getByRole("button", { name: "Show the maths" });
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("figure", { name: "Calculation" })).not.toBeInTheDocument();
  expect(screen.queryByText(/5700 - 1350/)).not.toBeInTheDocument();
});

test("pressing the button shows the framed calculation and offers Hide the maths", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  const user = userEvent.setup();
  render(<Reply text={ANSWER} />);
  await user.click(screen.getByRole("button", { name: "Show the maths" }));
  const box = screen.getByRole("figure", { name: "Calculation" });
  expect(box).toHaveTextContent("5700 - 1350 - 3000 = 1350");
  expect(box.className).toContain("border-2");
  const hide = screen.getByRole("button", { name: "Hide the maths" });
  expect(hide).toHaveAttribute("aria-expanded", "true");
  await user.click(hide);
  expect(screen.queryByRole("figure", { name: "Calculation" })).not.toBeInTheDocument();
  expect(fetchSpy).not.toHaveBeenCalled();
});

test("two calc blocks toggle independently", async () => {
  const user = userEvent.setup();
  render(<Reply text={"First:\n\n```calc\n1 + 1 = 2\n```\n\nSecond:\n\n```calc\n2 + 2 = 4\n```"} />);
  const [first] = screen.getAllByRole("button", { name: "Show the maths" });
  await user.click(first);
  const boxes = screen.getAllByRole("figure", { name: "Calculation" });
  expect(boxes).toHaveLength(1);
  expect(within(boxes[0]).getByText("1 + 1 = 2")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Show the maths" })).toBeInTheDocument();
});

test("a reply without a calc block has no maths button", () => {
  render(<Reply text={"Plain answer.\n\n```\nsome code\n```"} />);
  expect(screen.queryByRole("button", { name: /maths/ })).not.toBeInTheDocument();
});
