import { describe, expect, it } from "vitest";
import type { Composition, RoomSummary } from "./api";
import { isOpen, roomEntries } from "./rooms";

const room = (name: string, slug: string | null = null) =>
  ({ name, composition: slug ? { slug, versions: [1] } : null }) as unknown as RoomSummary;
const composition = (name: string, slug: string, scope = "room") => ({ name, slug, scope }) as unknown as Composition;

describe("roomEntries", () => {
  it("lists rooms first, then the compositions no room claims, each with its dialog path", () => {
    const entries = roomEntries(
      [room("Hall"), room("Wohnen", "wohnen")],
      [composition("Wohnung", "wohnung", "apartment"), composition("Wohnen", "wohnen")],
      true,
    );
    expect(entries.map((e) => [e.kind, e.name, e.segments])).toEqual([
      ["room", "Hall", ["Hall"]],
      ["room", "Wohnen", ["Wohnen"]],
      ["composition", "Wohnung", ["compositions", "wohnung"]],
    ]);
  });

  it("lists no composition on its own until the rooms are read", () => {
    expect(roomEntries(undefined, [composition("Wohnen", "wohnen")], false)).toEqual([]);
    expect(roomEntries(undefined, [composition("Wohnen", "wohnen")], true).map((e) => e.name)).toEqual(["Wohnen"]);
  });

  it("matches an entry to its dialog address", () => {
    const [hall, wohnung] = roomEntries([room("Hall")], [composition("Wohnung", "wohnung", "apartment")], true);
    expect(isOpen(hall, ["Hall"])).toBe(true);
    expect(isOpen(hall, ["compositions", "Hall"])).toBe(false);
    expect(isOpen(wohnung, ["compositions", "wohnung"])).toBe(true);
    expect(isOpen(wohnung, ["Wohnung"])).toBe(false);
  });
});
