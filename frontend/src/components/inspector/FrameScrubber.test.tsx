import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { FrameScrubber, wrapFrame } from "./FrameScrubber";

const url = (n: number) => `/frames/${n}`;

function sources(): string[] {
  return [...document.querySelectorAll("img")].map((img) => img.getAttribute("src") as string);
}

test("wrapFrame wraps at both ends", () => {
  expect(wrapFrame(35, 1, 36)).toBe(0);
  expect(wrapFrame(0, -1, 36)).toBe(35);
  expect(wrapFrame(3, 40, 36)).toBe(7);
});

test("the first frame is shown at once and only it and its neighbours are requested", () => {
  render(<FrameScrubber label="Detailed turntable" count={36} frameUrl={url} />);
  expect(screen.getByRole("img", { name: "Detailed turntable, frame 1 of 36" })).toHaveAttribute("src", "/frames/0");
  expect(sources().sort()).toEqual(["/frames/0", "/frames/1", "/frames/35"]);
  expect(screen.getByRole("status")).toHaveTextContent("Frame 1 of 36");
});

test("the arrow keys step through the frames and wrap from the last to the first", () => {
  render(<FrameScrubber label="Detailed turntable" count={36} frameUrl={url} />);
  const group = screen.getByRole("group", { name: "Detailed turntable frames" });
  fireEvent.keyDown(group, { key: "ArrowLeft" });
  expect(screen.getByRole("status")).toHaveTextContent("Frame 36 of 36");
  fireEvent.keyDown(group, { key: "ArrowRight" });
  expect(screen.getByRole("status")).toHaveTextContent("Frame 1 of 36");
  fireEvent.keyDown(group, { key: "ArrowRight" });
  expect(screen.getByRole("img", { name: "Detailed turntable, frame 2 of 36" })).toHaveAttribute("src", "/frames/1");
  expect(sources().sort()).toEqual(["/frames/0", "/frames/1", "/frames/2"]);
});

test("the slider and a drag across the picture move through the frames", () => {
  render(<FrameScrubber label="Walnut" count={12} frameUrl={url} />);
  fireEvent.change(screen.getByRole("slider", { name: "Walnut frame" }), { target: { value: "11" } });
  expect(screen.getByRole("status")).toHaveTextContent("Frame 12 of 12");
  const picture = screen.getByRole("img", { name: "Walnut, frame 12 of 12" });
  fireEvent.pointerDown(picture, { clientX: 100, pointerId: 1 });
  fireEvent.pointerMove(picture, { clientX: 130, pointerId: 1 });
  fireEvent.pointerUp(picture, { pointerId: 1 });
  expect(screen.getByRole("status")).toHaveTextContent("Frame 2 of 12");
});
