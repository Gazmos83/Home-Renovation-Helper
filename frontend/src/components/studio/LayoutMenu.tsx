import { LayoutPanelLeft } from "lucide-react";
import { LAYOUTS, WORKSPACE_WIDE, setWorkspaceLayout, useWorkspaceLayout, type WorkspaceLayout } from "@/lib/workspaceLayout";
import { useMediaQuery } from "@/lib/useMediaQuery";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** A 32 × 20 picture of a layout: C is the chat, P the piece, R the room. */
function Pictogram({ layout }: { layout: WorkspaceLayout }) {
  const boxes =
    layout === "piece-room"
      ? [
          { x: 1, y: 1, w: 14, h: 10, label: "P" },
          { x: 17, y: 1, w: 14, h: 10, label: "R" },
          { x: 1, y: 13, w: 30, h: 6, label: "C" },
        ]
      : [
          { x: 1, y: 1, w: 14, h: 18, label: "C" },
          { x: 17, y: 1, w: 14, h: 18, label: layout === "chat-piece" ? "P" : "R" },
        ];
  return (
    <svg aria-hidden width="32" height="20" viewBox="0 0 32 20" className="shrink-0 text-muted-foreground">
      {boxes.map((box) => (
        <g key={box.label}>
          <rect x={box.x} y={box.y} width={box.w} height={box.h} rx="1.5" fill="none" stroke="currentColor" />
          <text x={box.x + box.w / 2} y={box.y + box.h / 2 + 2.5} fontSize="7" textAnchor="middle" fill="currentColor">
            {box.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

/**
 * The Workspace's layout button at the right end of the Design Studio title row: a menu of the three
 * layouts with the current one marked (studio-pricing-and-agent-settings-tabs). Hidden on a narrow
 * screen, where the Workspace shows one pane at a time.
 */
export function LayoutMenu() {
  const layout = useWorkspaceLayout();
  const wide = useMediaQuery(WORKSPACE_WIDE);
  if (!wide) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="outline" size="sm" aria-label="Layout" title="Layout">
          <LayoutPanelLeft aria-hidden size={18} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Layout</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={layout} onValueChange={(value) => setWorkspaceLayout(value as WorkspaceLayout)}>
          {LAYOUTS.map((item) => (
            <DropdownMenuRadioItem key={item.id} value={item.id}>
              <Pictogram layout={item.id} />
              {item.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
