import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { setScreenWidth } from "@/test/media";
import { useMediaQuery } from "./useMediaQuery";

function Probe() {
  return <p>{useMediaQuery("(min-width: 1024px)") ? "laptop" : "phone"}</p>;
}

describe("useMediaQuery", () => {
  it("follows the screen width across the breakpoint", () => {
    render(<Probe />);
    expect(screen.getByText("laptop")).toBeInTheDocument();
    act(() => setScreenWidth(360));
    expect(screen.getByText("phone")).toBeInTheDocument();
    act(() => setScreenWidth(1024));
    expect(screen.getByText("laptop")).toBeInTheDocument();
  });
});
