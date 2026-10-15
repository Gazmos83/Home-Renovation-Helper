import * as React from "react";
import * as ResizablePrimitive from "react-resizable-panels";
import { GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";

/** The library sets the group's size and flex direction inline, from `orientation`. */
function ResizablePanelGroup(props: React.ComponentProps<typeof ResizablePrimitive.Group>) {
  return <ResizablePrimitive.Group data-slot="resizable-panel-group" {...props} />;
}

function ResizablePanel(props: React.ComponentProps<typeof ResizablePrimitive.Panel>) {
  return <ResizablePrimitive.Panel data-slot="resizable-panel" {...props} />;
}

/**
 * The drag handle between two panels. Dragging resizes both, the arrow keys move it while it has focus,
 * and a double-click returns its panels to their default sizes (the library's own behaviour).
 */
function ResizableHandle({ withHandle, className, ...props }: React.ComponentProps<typeof ResizablePrimitive.Separator> & { withHandle?: boolean }) {
  return (
    <ResizablePrimitive.Separator
      data-slot="resizable-handle"
      className={cn(
        "relative flex w-px items-center justify-center bg-border after:absolute after:inset-y-0 after:left-1/2 after:w-2 after:-translate-x-1/2",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        "aria-[orientation=horizontal]:h-px aria-[orientation=horizontal]:w-full aria-[orientation=horizontal]:after:left-0 aria-[orientation=horizontal]:after:h-2 aria-[orientation=horizontal]:after:w-full aria-[orientation=horizontal]:after:translate-x-0 aria-[orientation=horizontal]:after:-translate-y-1/2",
        "[&[aria-orientation=horizontal]>div]:rotate-90",
        className,
      )}
      {...props}
    >
      {withHandle && (
        <div className="z-10 flex h-4 w-3 items-center justify-center rounded-sm border bg-border">
          <GripVertical aria-hidden className="size-2.5" />
        </div>
      )}
    </ResizablePrimitive.Separator>
  );
}

export { ResizableHandle, ResizablePanel, ResizablePanelGroup };
