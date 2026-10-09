import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { api, type Composition, type RoomSummary } from "../lib/api";
import { FieldError, fieldError, formError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";
import { RoomView } from "@/components/inspector/RoomView";

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

function CompositionCard({ composition }: { composition: Composition }) {
  const scope = composition.scope === "room" ? "Room" : "Apartment";
  const [open3d, setOpen3d] = useState(false);
  return (
    <section className={cardClass} aria-label={composition.name}>
      <div className="flex flex-wrap items-center gap-2">
        <h2>{composition.name}</h2>
        <Badge variant="secondary">{scope}</Badge>
        {composition.latest_version !== null && <span>version {composition.latest_version}</span>}
        {composition.status && <Badge variant="outline">{composition.status}</Badge>}
      </div>
      {composition.items.length === 0 && <p>The room only, no furniture.</p>}
      <ul className="space-y-1">
        {composition.items.map((item) => (
          <li key={item.id}>
            <strong>{item.name}</strong> <span className="text-muted-foreground">({item.type})</span>
            {item.no_longer_approved && <Badge variant="destructive" className="ml-2">no longer approved</Badge>}
          </li>
        ))}
      </ul>
      {composition.picture && (
        <img src={composition.picture} alt={`Latest picture of ${composition.name}`} className="max-h-72 rounded-md border" />
      )}
      {composition.viewer && (
        <p>
          <a href={composition.viewer} target="_blank" rel="noreferrer" className="underline">
            Open the turntable viewer of {composition.name}
          </a>
        </p>
      )}
      {composition.model && composition.surfaces ? (
        open3d ? (
          <RoomView name={composition.name} model={composition.model} report={composition.surfaces} />
        ) : (
          <p>
            <Button type="button" variant="outline" onClick={() => setOpen3d(true)}>
              Open the 3D view of {composition.name}
            </Button>
          </p>
        )
      ) : (
        composition.status === "succeeded" && (
          <p className="text-sm text-muted-foreground">
            Composing {composition.name} again adds the 3D view.
          </p>
        )
      )}
    </section>
  );
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** One measured room, with its delete action and the warning of what it touches (rooms-page). */
function MeasuredRoom({ room }: { room: RoomSummary }) {
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
    <section className={`${cardClass} grid gap-2`} aria-label={`Measured room ${room.name}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3>{room.name}</h3>
        {room.apartment && <Badge variant="secondary">{room.apartment}</Badge>}
        {room.composition && <Badge variant="outline">composed</Badge>}
      </div>
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
    </section>
  );
}

function MeasuredRooms() {
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: api.rooms });
  return (
    <section className="grid gap-3" aria-label="Measured rooms">
      <h2>Measured rooms</h2>
      {rooms.error && <FieldError message={message(rooms.error)} />}
      {rooms.data && rooms.data.length === 0 && <p>No rooms measured yet. Describe one in a conversation.</p>}
      {(rooms.data ?? []).map((room) => (
        <MeasuredRoom key={room.name} room={room} />
      ))}
    </section>
  );
}

function ModelLibrary() {
  const queryClient = useQueryClient();
  const library = useQuery({
    queryKey: ["model-library"],
    queryFn: api.modelLibrary,
    // A model is checked in the background; follow it until every check is over.
    refetchInterval: (query) => (query.state.data?.some((m) => m.state === "checking") ? 2000 : false),
  });
  const files = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [width, setWidth] = useState("");
  const [depth, setDepth] = useState("");
  const [height, setHeight] = useState("");
  const reload = () => queryClient.invalidateQueries({ queryKey: ["model-library"] });
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadModel(file, name, width, depth, height),
    onSuccess: () => {
      setName("");
      setWidth("");
      setDepth("");
      setHeight("");
      if (files.current) files.current.value = "";
      reload();
    },
  });
  const remove = useMutation({ mutationFn: api.deleteModel, onSuccess: reload });

  function submit(event: FormEvent) {
    event.preventDefault();
    const file = files.current?.files?.[0];
    if (file) upload.mutate(file);
  }

  return (
    <section className="space-y-4" aria-label="Model library">
      <h2>Model library</h2>
      <p>Bought furniture and decor as 3D models: a GLB file, or a zip with one glTF or OBJ model and its files.</p>
      {library.error && <FieldError message={message(library.error)} />}
      {library.data && library.data.length === 0 && <p>No models yet.</p>}
      <ul className="space-y-2">
        {(library.data ?? []).map((model) => (
          <li key={model.model_id} className={cardClass}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>
                <strong>{model.name}</strong> {model.width_mm} × {model.depth_mm} × {model.height_mm} mm{" "}
                <Badge variant={model.state === "refused" ? "destructive" : "outline"}>{model.state}</Badge>
                {model.reason && <span className="ml-2 text-sm text-muted-foreground">{model.reason}</span>}
              </span>
              <Button variant="secondary" size="sm" onClick={() => remove.mutate(model.model_id)}>
                Delete {model.name}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <FieldError message={message(remove.error)} />
      <form onSubmit={submit} className={cardClass} aria-label="Upload a model">
        <h3>Upload a model</h3>
        <Label htmlFor="model-file">File</Label>
        <input id="model-file" ref={files} type="file" accept=".glb,.zip,model/gltf-binary,application/zip" />
        <Label htmlFor="model-name">Name</Label>
        <Input id="model-name" value={name} onChange={(e) => setName(e.target.value)} />
        <Label htmlFor="model-width">Width (mm)</Label>
        <Input id="model-width" value={width} onChange={(e) => setWidth(e.target.value)} />
        <FieldError message={fieldError(upload.error, "width_mm")} />
        <Label htmlFor="model-depth">Depth (mm)</Label>
        <Input id="model-depth" value={depth} onChange={(e) => setDepth(e.target.value)} />
        <FieldError message={fieldError(upload.error, "depth_mm")} />
        <Label htmlFor="model-height">Height (mm)</Label>
        <Input id="model-height" value={height} onChange={(e) => setHeight(e.target.value)} />
        <FieldError message={fieldError(upload.error, "height_mm")} />
        <FieldError message={formError(upload.error, ["width_mm", "depth_mm", "height_mm"])} />
        <p><Button type="submit" disabled={upload.isPending}>Upload model</Button></p>
      </form>
    </section>
  );
}

export default function Rooms() {
  const compositions = useQuery({ queryKey: ["compositions"], queryFn: api.compositions });
  return (
    <Page>
      <h1>Rooms</h1>
      <p>Your approved pieces placed in a room with the rest of the furniture. Ask the Designer in a conversation to compose a room.</p>
      <MeasuredRooms />
      {compositions.error && <FieldError message={message(compositions.error)} />}
      {compositions.data && compositions.data.length === 0 && <p>No rooms composed yet.</p>}
      {(compositions.data ?? []).map((composition) => (
        <CompositionCard key={composition.slug} composition={composition} />
      ))}
      <ModelLibrary />
    </Page>
  );
}
