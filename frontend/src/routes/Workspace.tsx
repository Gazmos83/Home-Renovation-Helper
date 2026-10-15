import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Navigate, useNavigate } from "react-router-dom";
import { useDefaultLayout, type LayoutStorage } from "react-resizable-panels";
import { ApiError, api } from "../lib/api";
import { FieldError } from "../lib/form";
import { useMediaQuery } from "../lib/useMediaQuery";
import { WORKSPACE_WIDE, hasPane, setWorkspaceLayout, useWorkspaceLayout, type WorkspaceLayout } from "../lib/workspaceLayout";
import { Button } from "@/components/ui/button";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { cn } from "@/lib/utils";
import { ChatPane, PiecePane, RoomPane, useConversation } from "./Conversation";

// Each layout's sizes are remembered per browser; a browser that cannot store them uses the defaults.
const storage: LayoutStorage = {
  getItem(key) {
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  setItem(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      // Not remembered; the panes still resize.
    }
  },
};

/** A resizable group whose sizes are remembered under `id`. */
function SavedGroup({ id, orientation, children }: { id: string; orientation: "horizontal" | "vertical"; children: ReactNode }) {
  const saved = useDefaultLayout({ id, storage });
  return (
    <ResizablePanelGroup id={id} orientation={orientation} defaultLayout={saved.defaultLayout} onLayoutChanged={saved.onLayoutChanged}>
      {children}
    </ResizablePanelGroup>
  );
}

/** A pane of a layout: at least a fifth of its group, half of it at first unless told otherwise. */
function Pane({ id, size = "50%", children }: { id: string; size?: string; children: ReactNode }) {
  return (
    <ResizablePanel id={id} defaultSize={size} minSize="20%">
      {children}
    </ResizablePanel>
  );
}

function Layout({ layout, chat, piece, room }: { layout: WorkspaceLayout; chat: ReactNode; piece: ReactNode; room: ReactNode }) {
  if (layout === "piece-room") {
    return (
      <SavedGroup key={layout} id="workspace.piece-room.rows" orientation="vertical">
        <Pane id="top" size="60%">
          <SavedGroup id="workspace.piece-room.cols" orientation="horizontal">
            <Pane id="piece">{piece}</Pane>
            <ResizableHandle withHandle aria-label="Resize the piece and the room" />
            <Pane id="room">{room}</Pane>
          </SavedGroup>
        </Pane>
        <ResizableHandle withHandle aria-label="Resize the piece and room above the chat" />
        <Pane id="chat" size="40%">{chat}</Pane>
      </SavedGroup>
    );
  }
  const other = layout === "chat-piece" ? "piece" : "room";
  return (
    <SavedGroup key={layout} id={`workspace.${layout}`} orientation="horizontal">
      <Pane id="chat">{chat}</Pane>
      <ResizableHandle withHandle aria-label={`Resize the chat and the ${other}`} />
      <Pane id={other}>{other === "piece" ? piece : room}</Pane>
    </SavedGroup>
  );
}

/**
 * A pane's own element. The pane is rendered into it once, and the element is moved into whichever
 * slot the layout puts it in, so changing the layout keeps the pane's state: a half-typed message,
 * the scroll position, the 3D camera.
 */
function usePaneElement(): HTMLDivElement {
  const [element] = useState(() => {
    const div = document.createElement("div");
    div.className = "h-full min-h-0";
    return div;
  });
  return element;
}

/** Where a layout shows a pane: the pane's element is moved in here. */
function Slot({ element }: { element: HTMLElement }) {
  const slot = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const here = slot.current;
    here?.appendChild(element);
    return () => {
      if (element.parentNode === here) here?.removeChild(element);
    };
  }, [element]);
  return <div ref={slot} className="h-full min-h-0" />;
}

type PhonePane = "chat" | "piece" | "room";
const PHONE_TABS: { id: PhonePane; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "piece", label: "Piece" },
  { id: "room", label: "Room" },
];

/** One conversation in the chosen layout, or one pane at a time on a narrow screen. */
function ConversationWorkspace({ threadId }: { threadId: string }) {
  const layout = useWorkspaceLayout();
  const wide = useMediaQuery(WORKSPACE_WIDE);
  const [phonePane, setPhonePane] = useState<PhonePane>("chat");
  // Opening a piece version or the room shows its pane: the layout switches when it has none.
  const c = useConversation(threadId, (pane) => {
    if (!wide) setPhonePane(pane);
    else if (!hasPane(layout, pane)) setWorkspaceLayout(pane === "piece" ? "chat-piece" : "chat-room");
  });
  // The panes fill the window below their top edge, less the page's bottom padding.
  const box = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(0);
  useLayoutEffect(() => {
    function measure() {
      if (box.current) setTop(box.current.getBoundingClientRect().top + window.scrollY);
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [wide]);

  const chatElement = usePaneElement();
  const pieceElement = usePaneElement();
  const roomElement = usePaneElement();

  if (c.thread.error instanceof ApiError && c.thread.error.status === 404) {
    return <p>This conversation was not found. Choose another one or start a new conversation.</p>;
  }
  // Only the panes the layout (or the phone's tab) shows are rendered, so no hidden 3D view runs.
  const shows = (pane: "piece" | "room") => (wide ? hasPane(layout, pane) : phonePane === pane);
  const panes = (
    <>
      {createPortal(<ChatPane c={c} />, chatElement)}
      {shows("piece") && createPortal(<PiecePane c={c} />, pieceElement)}
      {shows("room") && createPortal(<RoomPane c={c} />, roomElement)}
    </>
  );
  const chat = <Slot element={chatElement} />;
  const piece = <Slot element={pieceElement} />;
  const room = <Slot element={roomElement} />;
  const height = { height: `max(28rem, calc(100dvh - ${top}px - 2rem))` };

  if (!wide) {
    return (
      <div ref={box} className="flex flex-col gap-2" style={height}>
        <div role="tablist" aria-label="Panes" className="flex gap-2 border-b pb-2">
          {PHONE_TABS.map((tab) => (
            <Button
              key={tab.id}
              type="button"
              role="tab"
              size="sm"
              variant="ghost"
              aria-selected={phonePane === tab.id}
              className={cn(phonePane === tab.id && "bg-accent font-semibold")}
              onClick={() => setPhonePane(tab.id)}
            >
              {tab.label}
            </Button>
          ))}
        </div>
        {/* The chat stays mounted out of sight; a piece or room pane runs only while its tab is chosen. */}
        <div role="tabpanel" aria-label={PHONE_TABS.find((tab) => tab.id === phonePane)?.label} className="min-h-0 flex-1 rounded-xl border">
          {phonePane === "chat" ? chat : phonePane === "piece" ? piece : room}
        </div>
        {panes}
      </div>
    );
  }
  return (
    <div ref={box} className="overflow-hidden rounded-xl border" style={height}>
      <Layout layout={layout} chat={chat} piece={piece} room={room} />
      {panes}
    </div>
  );
}

/** Start a conversation and open it in the Workspace. */
export function useNewConversation() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.createThread(),
    onSuccess: (thread) => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      navigate(`/studio/workspace/${thread.thread_id}`);
    },
  });
}

/**
 * The Design Studio's Workspace tab (studio-pricing-and-agent-settings-tabs): one conversation with its
 * piece and room in the layout chosen from the title row. Without a conversation in the address it opens
 * the most recent one, or offers to start one.
 */
export default function Workspace({ threadId }: { threadId?: string }) {
  const threads = useQuery({ queryKey: ["threads"], queryFn: api.threads, enabled: !threadId });
  const create = useNewConversation();
  if (threadId) return <ConversationWorkspace key={threadId} threadId={threadId} />;
  if (threads.error) return <FieldError message={threads.error.message} />;
  if (!threads.data) return <p>Loading…</p>;
  const newest = threads.data[0];
  if (newest) return <Navigate to={`/studio/workspace/${newest.thread_id}`} replace />;
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground">No conversations yet.</p>
      <Button type="button" disabled={create.isPending} onClick={() => create.mutate()}>
        New conversation
      </Button>
      <FieldError message={create.error?.message ?? null} />
    </div>
  );
}
