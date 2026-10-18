import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ruler } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Composition, type RoomSummary } from "../lib/api";
import { FieldError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DeleteCompositionVersion } from "@/components/DeleteCompositionVersion";
import { RoomVariants } from "@/components/Variants";
import { RoomView, VersionSelect } from "@/components/inspector/RoomView";
import { isOpen, roomEntries } from "../lib/rooms";
import { Tile } from "@/components/studio/Tile";
import { TileGrid } from "@/components/studio/TileGrid";
import { useStudioDialog } from "@/components/studio/useStudioDialog";
import { VersionFiles, type VersionFile } from "@/components/studio/VersionFiles";

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

/** A composition version's downloadable files, named as the file route serves them. */
function roomFiles(view: { blend?: string | null; model: string | null; picture: string | null }): VersionFile[] {
  const files: VersionFile[] = [];
  if (view.blend) files.push({ name: "model.blend", href: view.blend });
  if (view.model) files.push({ name: "model.glb", href: view.model });
  const picture = view.picture?.split("/").pop()?.split("?")[0];
  if (view.picture && picture) files.push({ name: picture, href: view.picture });
  return files;
}

/**
 * A composition and its chosen version: a dialog of its own, or, inside its measured room's
 * dialog, a group under a "Composition" heading (split-rooms-page, studio-tile-grid).
 */
function CompositionCard({ composition, inRoom = false }: { composition: Composition; inRoom?: boolean }) {
  const queryClient = useQueryClient();
  const scope = composition.scope === "room" ? "Room" : "Apartment";
  const [open3d, setOpen3d] = useState(false);
  // The newest five versions, the latest chosen at first (project-room-inspection).
  const views = composition.version_views ?? [];
  const [chosen, setChosen] = useState<number | null>(null);
  const view = views.find((v) => v.version === chosen) ?? views[0];
  const shown = view ?? {
    version: composition.latest_version,
    status: composition.status,
    items: composition.items,
    picture: composition.picture,
    viewer: composition.viewer,
    model: composition.model ?? null,
    surfaces: composition.surfaces ?? null,
    dimensions: null,
    approved_at: null,
  };
  const version = shown.version;
  const approved =
    Boolean(shown.approved_at) || (version !== null && composition.approved_version === version);
  const succeeded = shown.status === "succeeded" && version !== null;
  const only = (composition.versions?.length ?? views.length) === 1;
  const reload = () => {
    queryClient.invalidateQueries({ queryKey: ["compositions"] });
    queryClient.invalidateQueries({ queryKey: ["progress"] });
  };
  const change = useMutation({
    mutationFn: (approve: boolean) =>
      approve
        ? api.approveCompositionVersion(composition.slug, version as number)
        : api.unapproveCompositionVersion(composition.slug, version as number),
    onSuccess: reload,
  });
  const body = (
    <>
      <div className={inRoom ? "flex flex-wrap items-center gap-2" : "flex flex-wrap items-center gap-2 pr-8"}>
        {inRoom ? (
          <h3>Composition</h3>
        ) : (
          <>
            <DialogTitle>{composition.name}</DialogTitle>
            <Badge variant="secondary">{scope}</Badge>
          </>
        )}
        {views.length > 0 ? (
          <VersionSelect name={composition.name} versions={views} value={shown.version as number} onChange={setChosen} />
        ) : (
          shown.version !== null && <span>version {shown.version}</span>
        )}
        {shown.status && <Badge variant="outline">{shown.status}</Badge>}
        {approved && <Badge>Approved</Badge>}
      </div>
      {succeeded && (
        <div className="grid gap-2" role="group" aria-label={`Approval of ${composition.name} version ${version}`}>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant={approved ? "outline" : "default"}
              disabled={change.isPending}
              onClick={() => change.mutate(!approved)}
            >
              {approved ? "Unapprove" : "Approve"} version {version}
            </Button>
          </div>
          <FieldError message={message(change.error)} />
          {!approved && (
            <DeleteCompositionVersion
              key={version}
              slug={composition.slug}
              name={composition.name}
              version={version as number}
              only={only}
              onDeleted={reload}
            />
          )}
        </div>
      )}
      {version !== null && !succeeded && !approved && (
        <DeleteCompositionVersion
          key={version}
          slug={composition.slug}
          name={composition.name}
          version={version}
          only={only}
          onDeleted={reload}
        />
      )}
      {shown.items.length === 0 && <p>The room only, no furniture.</p>}
      <ul className="space-y-1">
        {shown.items.map((item) => (
          <li key={item.id}>
            <strong>{item.name}</strong> <span className="text-muted-foreground">({item.type})</span>
            {item.no_longer_approved && <Badge variant="destructive" className="ml-2">no longer approved</Badge>}
          </li>
        ))}
      </ul>
      {shown.picture && (
        <img src={shown.picture} alt={`Picture of ${composition.name}, version ${shown.version}`} className="max-h-72 rounded-md border" />
      )}
      {succeeded && composition.slug && version !== null && (
        <RoomVariants slug={composition.slug} version={version} />
      )}
      {succeeded && composition.slug && version !== null && (
        <VersionFiles
          owner={composition.slug}
          version={version}
          files={roomFiles(shown)}
          heading="Download the room"
          note="Open the .blend in Blender: the room, its openings and every placed piece, in millimetres."
        />
      )}
      {shown.viewer && (
        <p>
          <a href={shown.viewer} target="_blank" rel="noreferrer" className="underline">
            Open the turntable viewer of {composition.name}
          </a>
        </p>
      )}
      {shown.model && shown.surfaces ? (
        open3d ? (
          <RoomView
            key={shown.model}
            name={composition.name}
            model={shown.model}
            report={shown.surfaces}
            dimensions={shown.dimensions}
            apartment={composition.scope === "apartment"}
          />
        ) : (
          <p>
            <Button type="button" variant="outline" onClick={() => setOpen3d(true)}>
              Open the 3D view of {composition.name}
            </Button>
          </p>
        )
      ) : (
        shown.status === "succeeded" && (
          <p className="text-sm text-muted-foreground">
            Composing {composition.name} again adds the 3D view.
          </p>
        )
      )}
    </>
  );
  return inRoom ? (
    <div role="group" aria-label={composition.name} className="grid gap-4 border-t pt-4">
      {body}
    </div>
  ) : (
    body
  );
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/**
 * One measured room, with its delete action and the warning of what it touches (rooms-page),
 * and its composition once the compositions are read (split-rooms-page), shown in its dialog.
 */
function MeasuredRoom({
  room,
  composition,
  loaded,
}: {
  room: RoomSummary;
  composition: Composition | undefined;
  loaded: boolean;
}) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const remove = useMutation({
    mutationFn: () => api.deleteRoom(room.name),
    onSuccess: () => {
      for (const key of ["rooms", "compositions", "pieces"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  const shape = room.corners === 4 ? "" : `, ${room.corners} corners`;
  const effects = [
    room.pieces.length > 0 &&
      `${room.pieces.map((p) => p.name).join(", ")} will have no room`,
    room.conversations > 0 &&
      `${plural(room.conversations, "conversation", "conversations")} will need to confirm a room again`,
    room.composition &&
      `its composition and ${plural(room.composition.versions.length, "version", "versions")} will be removed`,
  ].filter(Boolean);
  return (
    <>
      <DialogHeader>
        <DialogTitle>{room.name}</DialogTitle>
        {room.apartment && <Badge variant="secondary">{room.apartment}</Badge>}
      </DialogHeader>
      <p className="text-sm">
        {room.width_mm} × {room.depth_mm} mm{shape}, ceiling {room.height_mm} mm,{" "}
        {plural(room.openings, "opening", "openings")}
      </p>
      <p className="text-sm text-muted-foreground">
        {room.pieces.length > 0 ? `Pieces: ${room.pieces.map((p) => p.name).join(", ")}` : "No pieces in this room."}
      </p>
      {room.apartment ? (
        <p className="text-sm text-muted-foreground">
          {room.name} belongs to the apartment {room.apartment}; it cannot be deleted on its own yet.
        </p>
      ) : confirming ? (
        <div className="grid gap-2" role="group" aria-label={`Delete ${room.name}?`}>
          <p className="text-sm">
            Delete “{room.name}”?{" "}
            {effects.length > 0 ? `${effects.join("; ")}.` : "Nothing else uses it."} A deleted room cannot be
            restored.
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate()}>
              Delete
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setConfirming(false);
                remove.reset();
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <Button type="button" variant="ghost" size="sm" onClick={() => setConfirming(true)}>
            Delete {room.name}
          </Button>
        </div>
      )}
      <FieldError message={message(remove.error)} />
      {composition ? (
        <CompositionCard composition={composition} inRoom />
      ) : (
        loaded &&
        !room.composition && (
          <p className="text-sm text-muted-foreground">
            No composition yet. Ask the Designer in a conversation to compose {room.name}.
          </p>
        )
      )}
    </>
  );
}

function roomSize(room: RoomSummary): string {
  return `${room.width_mm} × ${room.depth_mm} mm, ceiling ${room.height_mm} mm`;
}

/**
 * Measured rooms, then the compositions with no room of their own, as tiles; each opens its dialog at
 * `/studio/rooms/<room>` or `/studio/rooms/compositions/<slug>` (split-rooms-page, studio-tile-grid).
 */
export default function Rooms() {
  const dialog = useStudioDialog("rooms");
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: api.rooms });
  const compositions = useQuery({ queryKey: ["compositions"], queryFn: api.compositions });
  const listed = compositions.data ?? [];
  // Rooms, then apartment compositions and a room's whose room is gone, each with a tile of its own.
  const items = roomEntries(rooms.data, compositions.data, Boolean(rooms.data || rooms.error));
  const roomComposition = (room: RoomSummary) =>
    room.composition ? listed.find((c) => c.slug === room.composition?.slug) : undefined;

  const opened = items.find((item) => isOpen(item, dialog.segments));
  const openRoom = opened?.kind === "room" ? opened.room : undefined;
  const openComposition = opened?.kind === "composition" ? opened.composition : undefined;
  // An address naming nothing listed (unknown, or just deleted) shows the grid once both lists are read.
  const read = Boolean(rooms.data || rooms.error) && Boolean(compositions.data || compositions.error);
  const missing = read && dialog.segments.length > 0 && !openRoom && !openComposition;
  useEffect(() => {
    if (missing) dialog.dismiss();
  }, [missing]);

  return (
    <>
      <p>
        Your measured rooms, each with its composition: your approved pieces placed in the room with the rest of the
        furniture. Ask the Designer in a conversation to compose a room.
      </p>
      {rooms.error && <FieldError message={message(rooms.error)} />}
      {compositions.error && <FieldError message={message(compositions.error)} />}
      {rooms.data && rooms.data.length === 0 && <p>No rooms measured yet. Describe one in a conversation.</p>}
      <TileGrid label="Measured rooms" items={items} keyOf={(item) => item.segments.join("/")}>
        {(item) =>
          item.kind === "room" ? (
            <Tile
              name={item.room.name}
              detail={roomSize(item.room)}
              picture={roomComposition(item.room)?.picture}
              placeholder={Ruler}
              badge={item.room.apartment ? <Badge variant="secondary">{item.room.apartment}</Badge> : undefined}
              onOpen={() => dialog.open(item.room.name)}
            />
          ) : (
            <Tile
              name={item.composition.name}
              picture={item.composition.picture}
              placeholder={Ruler}
              badge={<Badge variant="secondary">{item.composition.scope === "room" ? "Room" : "Apartment"}</Badge>}
              onOpen={() => dialog.open("compositions", item.composition.slug)}
            />
          )
        }
      </TileGrid>
      <Dialog open={Boolean(openRoom || openComposition)} onOpenChange={(open) => !open && dialog.close()}>
        {openRoom && (
          <DialogContent aria-describedby={undefined}>
            <MeasuredRoom
              key={openRoom.name}
              room={openRoom}
              composition={roomComposition(openRoom)}
              loaded={Boolean(compositions.data)}
            />
          </DialogContent>
        )}
        {openComposition && (
          <DialogContent aria-describedby={undefined}>
            <CompositionCard key={openComposition.slug} composition={openComposition} />
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
