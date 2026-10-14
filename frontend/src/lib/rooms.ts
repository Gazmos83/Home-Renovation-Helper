import type { Composition, RoomSummary } from "./api";

/** One entry of the Measured Rooms grid and sub-menu, with the path segments of its dialog. */
export type RoomEntry = { name: string; segments: string[] } & (
  | { kind: "room"; room: RoomSummary }
  | { kind: "composition"; composition: Composition }
);

/**
 * The Measured Rooms order (split-rooms-page, studio-submenu-names): every room, then each composition no
 * room claims (an apartment's, or a room's whose room is gone). Those are listed only once the rooms are
 * read (or failed to read), so a room's own composition never shows on its own while the rooms load.
 */
export function roomEntries(
  rooms: RoomSummary[] | undefined,
  compositions: Composition[] | undefined,
  roomsRead: boolean,
): RoomEntry[] {
  const claimed = new Set((rooms ?? []).flatMap((room) => (room.composition ? [room.composition.slug] : [])));
  const unclaimed = roomsRead ? (compositions ?? []).filter((c) => !claimed.has(c.slug)) : [];
  return [
    ...(rooms ?? []).map((room) => ({ kind: "room" as const, room, name: room.name, segments: [room.name] })),
    ...unclaimed.map((composition) => ({
      kind: "composition" as const,
      composition,
      name: composition.name,
      segments: ["compositions", composition.slug],
    })),
  ];
}

/** Whether `entry` is the one the dialog address (its path segments) names. */
export function isOpen(entry: RoomEntry, segments: string[]): boolean {
  return entry.segments.length === segments.length && entry.segments.every((segment, i) => segment === segments[i]);
}
