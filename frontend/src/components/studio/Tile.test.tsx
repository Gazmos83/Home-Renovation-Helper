import { fireEvent, render, screen } from "@testing-library/react";
import { Package } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { Badge } from "@/components/ui/badge";
import { Tile } from "./Tile";

describe("Tile", () => {
  it("shows the picture, name, detail and badge as one named button", () => {
    const { container } = render(
      <Tile
        name="Sofa"
        detail="2200 × 950 × 800 mm"
        picture="/models/1/thumbnail"
        placeholder={Package}
        badge={<Badge variant="outline">ready</Badge>}
        onOpen={() => {}}
      />,
    );
    const tile = screen.getByRole("button", { name: "Sofa" });
    expect(tile).toHaveTextContent("2200 × 950 × 800 mm");
    expect(tile).toHaveTextContent("ready");
    expect(container.querySelector("img")).toHaveAttribute("src", "/models/1/thumbnail");
    expect(screen.queryByTestId("tile-placeholder")).toBeNull();
  });

  it("shows a placeholder icon and no error without a picture", () => {
    render(<Tile name="hall-bench" placeholder={Package} onOpen={() => {}} />);
    expect(screen.getByTestId("tile-placeholder")).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });

  it("opens on activation and prefetches on hover and focus", () => {
    const onOpen = vi.fn();
    const onPrefetch = vi.fn();
    render(<Tile name="Sofa" placeholder={Package} onOpen={onOpen} onPrefetch={onPrefetch} />);
    const tile = screen.getByRole("button", { name: "Sofa" });
    fireEvent.focus(tile);
    fireEvent.pointerEnter(tile);
    expect(onPrefetch).toHaveBeenCalledTimes(2);
    fireEvent.click(tile);
    expect(onOpen).toHaveBeenCalledOnce();
  });
});
