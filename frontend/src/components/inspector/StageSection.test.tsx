import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { StageSection } from "./InspectorView";

/** inspector-side-column: one fold-out heading of the stage's side column. */

test("a section starts open, folds on a click of its heading and keeps its children mounted", async () => {
  const user = userEvent.setup();
  render(
    <StageSection title="Parts">
      <button type="button">fronts</button>
    </StageSection>,
  );
  const heading = screen.getByText("Parts");
  const section = heading.closest("details")!;
  expect(section).toHaveAttribute("open");

  await user.click(heading);
  expect(section).not.toHaveAttribute("open");
  expect(screen.getByText("fronts")).toBeInTheDocument();

  await user.click(heading);
  expect(section).toHaveAttribute("open");
});
