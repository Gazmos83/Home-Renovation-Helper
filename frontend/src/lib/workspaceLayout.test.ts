import { afterEach, expect, test } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { hasPane, resetWorkspaceLayout, useWorkspaceLayout } from "./workspaceLayout";

const KEY = "studio.workspace.layout";

afterEach(() => {
  window.localStorage.clear();
  resetWorkspaceLayout();
});

function stored(value: string | null) {
  if (value !== null) window.localStorage.setItem(KEY, value);
  act(() => resetWorkspaceLayout());
  return renderHook(() => useWorkspaceLayout()).result.current;
}

test("a remembered 'Piece and room, chat below' opens 'Piece, room and chat above' (Old layout remembered)", () => {
  expect(stored("piece-room")).toBe("chat-above");
});

test("a remembered layout is kept, and an unknown or missing one gives the default", () => {
  expect(stored("chat-room")).toBe("chat-room");
  window.localStorage.clear();
  expect(stored("chat-below")).toBe("chat-piece");
  window.localStorage.clear();
  expect(stored(null)).toBe("chat-piece");
});

test("chat above shows the piece and the room; the chat layouts show their one pane", () => {
  expect(hasPane("chat-above", "piece")).toBe(true);
  expect(hasPane("chat-above", "room")).toBe(true);
  expect(hasPane("chat-piece", "room")).toBe(false);
  expect(hasPane("chat-room", "room")).toBe(true);
});
