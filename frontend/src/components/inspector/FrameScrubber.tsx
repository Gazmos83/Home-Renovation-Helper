import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

/** How far the pointer moves across the picture for one frame, in pixels. */
const DRAG_PX_PER_FRAME = 12;

/** `index` moved by `step`, wrapping at both ends of `count` frames. */
export function wrapFrame(index: number, step: number, count: number): number {
  return (((index + step) % count) + count) % count;
}

/**
 * A turntable played inside the app (two-tier-renders): the first frame at once, then a
 * slider, a drag across the picture or the arrow keys move through the frames, wrapping at
 * both ends. Only the frame on screen and its two neighbours are requested, so a long
 * turntable is never downloaded all at once.
 */
export function FrameScrubber({
  label,
  count,
  frameUrl,
}: {
  label: string;
  count: number;
  frameUrl: (index: number) => string;
}) {
  const [index, setIndex] = useState(0);
  const drag = useRef<{ x: number; start: number } | null>(null);
  const shown = Math.min(index, count - 1);
  const neighbours = count > 1 ? [...new Set([wrapFrame(shown, -1, count), wrapFrame(shown, 1, count)])] : [];

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowRight") setIndex(wrapFrame(shown, 1, count));
    else if (event.key === "ArrowLeft") setIndex(wrapFrame(shown, -1, count));
    else return;
    event.preventDefault();
  }

  function onPointerDown(event: PointerEvent<HTMLImageElement>) {
    drag.current = { x: event.clientX, start: shown };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLImageElement>) {
    if (!drag.current) return;
    const steps = Math.trunc((event.clientX - drag.current.x) / DRAG_PX_PER_FRAME);
    setIndex(wrapFrame(drag.current.start, steps, count));
  }

  function onPointerUp() {
    drag.current = null;
  }

  return (
    <div
      role="group"
      aria-label={`${label} frames`}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="grid gap-2 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <img
        src={frameUrl(shown)}
        alt={`${label}, frame ${shown + 1} of ${count}`}
        draggable={false}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        className="max-h-[60vh] w-full cursor-ew-resize touch-none rounded-md border object-contain"
      />
      {neighbours.map((n) => (
        <img key={n} src={frameUrl(n)} alt="" aria-hidden className="hidden" data-role="prefetch" />
      ))}
      <div className="flex items-center gap-2 text-sm">
        <input
          type="range"
          min={0}
          max={count - 1}
          step={1}
          value={shown}
          aria-label={`${label} frame`}
          onChange={(event) => setIndex(Number(event.target.value))}
          className="flex-1"
        />
        <span role="status">
          Frame {shown + 1} of {count}
        </span>
      </div>
    </div>
  );
}
