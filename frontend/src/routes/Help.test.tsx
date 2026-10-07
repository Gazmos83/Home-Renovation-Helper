import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import Help, { MEASUREMENTS } from "./Help";

test("the help page lists every measurement Intake needs and the accepted files", () => {
  render(<Help />);
  const blueprint = within(screen.getByRole("region", { name: "Preparing a blueprint" }));
  for (const needed of [
    /each room's name/i,
    /length of every wall, edge by edge, going round the room in one direction/i,
    /corner angle that is not 90°/i,
    /ceiling height/i,
    /wall thickness/i,
    /door and window: the wall it is on, its offset from that wall's starting corner, its width and its height, and for a window its sill height/i,
    /scale reference: a dimension line, a printed area or a known door width/i,
    /one plan frame/i,
  ]) {
    expect(blueprint.getByText(needed)).toBeInTheDocument();
  }
  expect(blueprint.getAllByRole("listitem")).toHaveLength(MEASUREMENTS.length);
  expect(blueprint.getByRole("img", { name: /Example: a hall/ })).toBeInTheDocument();
  const files = within(screen.getByRole("region", { name: "Files" }));
  expect(files.getByText(/PNG or JPEG/)).toBeInTheDocument();
  expect(files.getByText(/Markdown \(\.md\) or plain text/)).toBeInTheDocument();
});
