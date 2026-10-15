import { useSyncExternalStore } from "react";

/** The Workspace's three arrangements of the chat, piece and room panes (studio-pricing-and-agent-settings-tabs). */
export type WorkspaceLayout = "chat-piece" | "chat-room" | "piece-room";

export const LAYOUTS: { id: WorkspaceLayout; label: string }[] = [
  { id: "chat-piece", label: "Chat and piece" },
  { id: "chat-room", label: "Chat and room" },
  { id: "piece-room", label: "Piece and room, chat below" },
];

/** The width from which the Workspace's panes sit side by side; below it one pane is shown at a time. */
export const WORKSPACE_WIDE = "(min-width: 1024px)";

const KEY = "studio.workspace.layout";
const DEFAULT: WorkspaceLayout = "chat-piece";

function isLayout(value: unknown): value is WorkspaceLayout {
  return LAYOUTS.some((layout) => layout.id === value);
}

// Remembered per browser; a browser that cannot store it starts on the default and keeps the choice in memory.
function read(): WorkspaceLayout {
  try {
    const stored = window.localStorage.getItem(KEY);
    return isLayout(stored) ? stored : DEFAULT;
  } catch {
    return DEFAULT;
  }
}

let current: WorkspaceLayout | null = null;
const listeners = new Set<() => void>();

/** Choose a layout: shown by every mounted Workspace and its layout menu at once, and remembered. */
export function setWorkspaceLayout(layout: WorkspaceLayout): void {
  current = layout;
  try {
    window.localStorage.setItem(KEY, layout);
  } catch {
    // Not remembered; the layout still changes.
  }
  for (const listener of listeners) listener();
}

/** Forget the in-memory choice, so the next read comes from the browser again (for tests). */
export function resetWorkspaceLayout(): void {
  current = null;
}

/** The chosen layout, shared by the Design Studio's layout menu and the Workspace. */
export function useWorkspaceLayout(): WorkspaceLayout {
  return useSyncExternalStore(
    (onChange) => {
      listeners.add(onChange);
      return () => listeners.delete(onChange);
    },
    () => (current ??= read()),
  );
}

/** Whether a layout has a pane for the piece or the room. */
export function hasPane(layout: WorkspaceLayout, pane: "piece" | "room"): boolean {
  return layout === "piece-room" || layout === `chat-${pane}`;
}
