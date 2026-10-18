import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useMediaQuery } from "@/lib/useMediaQuery";

/** 4 × 4 tiles from 1024 px wide, 2 × 3 below (studio-tile-grid). */
export const LAPTOP = "(min-width: 1024px)";
export const LAPTOP_PAGE = 16;
export const PHONE_PAGE = 6;
// Below the grid: the pager, the gap above it and the page's bottom padding.
const BELOW_PX = 96;

/** The page a 1-based `page` of `from`-sized pages becomes in `to`-sized pages: the one holding its first tile. */
export function carryPage(page: number, from: number, to: number): number {
  return Math.floor(((page - 1) * from) / to) + 1;
}

/**
 * Items as a grid of tiles that fills the screen from where it starts, one page at a time. The page
 * number is the address's `?page`; it is clamped to the pages there are, and kept on the first shown tile
 * when the screen crosses the breakpoint. The rows keep a minimum height, so a short screen scrolls.
 */
export function TileGrid<T>({
  label,
  items,
  keyOf,
  children,
}: {
  label: string;
  items: T[];
  keyOf: (item: T) => string;
  children: (item: T) => ReactNode;
}) {
  const size = useMediaQuery(LAPTOP) ? LAPTOP_PAGE : PHONE_PAGE;
  const [params, setParams] = useSearchParams();
  const lastSize = useRef(size);
  const list = useRef<HTMLUListElement>(null);
  const [top, setTop] = useState<number | null>(null);
  const requested = Math.max(1, Math.floor(Number(params.get("page"))) || 1);
  // The address still counts in the old page size for the one render after the breakpoint is crossed.
  const wanted = lastSize.current === size ? requested : carryPage(requested, lastSize.current, size);
  const pages = Math.max(1, Math.ceil(items.length / size));
  const page = Math.min(wanted, pages);

  function goTo(next: number) {
    setParams(
      (current) => {
        const kept = new URLSearchParams(current);
        if (next === 1) kept.delete("page");
        else kept.set("page", String(next));
        return kept;
      },
      { replace: true },
    );
  }

  // Runs only when the breakpoint is crossed: the address then counts in the new page size.
  useEffect(() => {
    if (lastSize.current === size) return;
    lastSize.current = size;
    if (wanted !== requested) goTo(wanted);
  }, [size]);

  // The grid fills the screen from where it starts on the page; the min-height classes stop it squashing.
  useLayoutEffect(() => {
    const measure = () => {
      if (list.current) setTop(list.current.getBoundingClientRect().top + window.scrollY);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [items.length === 0]);

  if (items.length === 0) return null;
  const shown = items.slice((page - 1) * size, page * size);
  return (
    <div className="grid gap-3">
      <ul
        ref={list}
        aria-label={label}
        style={top === null ? undefined : { height: `calc(100dvh - ${Math.round(top + BELOW_PX)}px - var(--footer-h))` }}
        className="grid min-h-[24rem] grid-cols-2 grid-rows-3 gap-3 lg:min-h-[32rem] lg:grid-cols-4 lg:grid-rows-4"
      >
        {shown.map((item) => (
          <li key={keyOf(item)} className="min-h-0 min-w-0">
            {children(item)}
          </li>
        ))}
      </ul>
      {pages > 1 && (
        <nav aria-label={`Pages of ${label}`} className="flex items-center justify-center gap-3 text-sm">
          <Button type="button" variant="outline" size="sm" disabled={page === 1} onClick={() => goTo(page - 1)}>
            Previous
          </Button>
          <span aria-live="polite">
            Page {page} of {pages}
          </span>
          <Button type="button" variant="outline" size="sm" disabled={page === pages} onClick={() => goTo(page + 1)}>
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}
