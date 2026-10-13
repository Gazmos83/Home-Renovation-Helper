import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import type { DrillingList, PieceSpec, SpecPart } from "@/lib/api";
import { changedCutIds, CutListTables } from "./CutListTables";

const base: PieceSpec = {
  overall: { w: 1500, h: 400, d: 250 }, layers: {}, parts: [], hardware: [{ id: "shelf-pin", item: "Shelf pin", qty: "", notes: "No quantity" }],
};

const side: SpecPart = {
  id: "cabinet-side", name: "Side", qty: 2, l: 400, w: 250, t: 18,
  material: "birch", grain: "along", banding: "", notes: "", module: "cabinet",
};
const divider: SpecPart = {
  id: "cabinet-divider", name: "Divider", qty: 1, l: 383, w: 388, t: 18,
  material: "birch", grain: "along", banding: "", notes: "", module: "cabinet",
};

const entries: DrillingList["entries"] = [
  {
    calculation: "brackets", part: "wall-shelf-1", what: "brackets", missing: [], problem: null,
    text: "wall-shelf-1: brackets 1 and 3 at 100–200 mm from each end; bracket 2 evenly spaced between them (topnotch-shelf-brackets)",
    positions: [],
  },
];

const pinEntry: DrillingList["entries"][number] = {
  calculation: "shelf_pins", part: "m-side", what: "shelf-pin holes", missing: [], problem: null,
  text: "m-side, inner face: front column 37 mm from the front edge; rear column 37 mm from the back; holes at 68, 100, … 652 mm (shelf-pin data sheet)",
  positions: [],
};

function show(drilling: DrillingList | undefined) {
  render(<CutListTables spec={{ ...base, drilling }} />);
  return screen.getByRole("region", { name: "Drilling" });
}

test("drilling is shown for adjustable shelves with no banner", () => {
  const section = show({
    calculated: true, complete: true, warnings: [],
    counts: { hinge_cup_borings: 0, shelf_pin_holes: 76 },
    entries: [pinEntry],
  });
  expect(within(section).getByText("m-side")).toBeInTheDocument();
  expect(within(section).getByText(/front column 37 mm from the front edge/)).toBeInTheDocument();
  expect(within(section).getByText(/holes at 68, 100/)).toBeInTheDocument();
  expect(within(section).getByText(/shelf-pin data sheet/)).toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("ranged bracket ends and an inner bracket in words are shown with no banner", () => {
  const section = show({ calculated: true, complete: true, warnings: [], counts: { hinge_cup_borings: 0, brackets: 3 }, entries });
  expect(within(section).getByText(/100–200 mm from each end; bracket 2 evenly spaced between them/)).toBeInTheDocument();
  expect(within(section).getByText("wall-shelf-1")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(within(section).getByText("Drilling work: 0 hinge cup borings.")).toBeInTheDocument();
});

test("an incomplete list shows a banner naming the missing value", () => {
  const section = show({
    calculated: true, complete: false,
    warnings: ["drilling positions missing: cup edge distance (m-door-1, hinges)"],
    counts: { hinge_cup_borings: 2, shelf_pin_holes: null },
    entries: [{ ...entries[0], part: "m-door-1", text: "m-door-1: hinges at 100 mm; blank, missing: cup edge distance (hinge-concealed-110 data sheet)", missing: ["cup edge distance"] }],
  });
  const banner = screen.getByRole("alert");
  expect(banner).toHaveTextContent("The drilling list is incomplete.");
  expect(banner).toHaveTextContent("cup edge distance");
  expect(banner.compareDocumentPosition(screen.getByRole("region", { name: "Cut list" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(within(section).getByText("Drilling work: 2 hinge cup borings, shelf-pin holes not counted.")).toBeInTheDocument();
});

test("an old version says drilling was not calculated", () => {
  const section = show(undefined);
  expect(within(section).getByText("Drilling was not calculated for this version.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a hardware line with no quantity says so", () => {
  show(undefined);
  expect(within(screen.getByRole("region", { name: "Hardware" })).getByText("no quantity")).toBeInTheDocument();
});

test("a new divider and a changed confirmat quantity are marked changed", () => {
  const before: PieceSpec = {
    ...base,
    parts: [side],
    hardware: [{ id: "confirmat-7x50", item: "Confirmat screw 7×50 mm", qty: 24, notes: "" }],
  };
  const after: PieceSpec = {
    ...base,
    parts: [side, divider],
    hardware: [{ id: "confirmat-7x50", item: "Confirmat screw 7×50 mm", qty: 28, notes: "" }],
  };
  const changed = changedCutIds(after, before);
  expect([...changed.parts]).toEqual(["cabinet-divider"]);
  expect([...changed.hardware]).toEqual(["confirmat-7x50"]);
  render(<CutListTables spec={after} baseline={before} />);
  expect(screen.getByText("cabinet-divider").closest("tr")).toHaveAttribute("data-changed", "true");
  expect(screen.getByText("cabinet-side").closest("tr")).not.toHaveAttribute("data-changed");
  expect(screen.getByText("Confirmat screw 7×50 mm").closest("tr")).toHaveAttribute("data-changed", "true");
});

test("without a baseline no row is marked changed", () => {
  const spec: PieceSpec = { ...base, parts: [side, divider] };
  expect([...changedCutIds(spec, null).parts]).toEqual([]);
  render(<CutListTables spec={spec} />);
  expect(screen.getByText("cabinet-divider").closest("tr")).not.toHaveAttribute("data-changed");
});
