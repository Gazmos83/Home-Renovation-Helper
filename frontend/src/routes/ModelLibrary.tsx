import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Package } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, modelThumbnail, type ModelAsset } from "../lib/api";
import { FieldError, fieldError, formError } from "../lib/form";
import { drawModel } from "../lib/modelThumbnail";
import { useMediaQuery } from "../lib/useMediaQuery";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tile } from "@/components/studio/Tile";
import { LAPTOP, LAPTOP_PAGE, PHONE_PAGE, TileGrid } from "@/components/studio/TileGrid";
import { useStudioDialog } from "@/components/studio/useStudioDialog";

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

function size(model: ModelAsset): string {
  return `${model.width_mm} × ${model.depth_mm} × ${model.height_mm} mm`;
}

function StateBadge({ model }: { model: ModelAsset }) {
  return <Badge variant={model.state === "refused" ? "destructive" : "outline"}>{model.state}</Badge>;
}

/** One model in its dialog: picture, stated and measured size, check state, delete (studio-tile-grid). */
function ModelDetail({ model }: { model: ModelAsset }) {
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: () => api.deleteModel(model.model_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["model-library"] }),
  });
  const measured = model.measured_mm;
  return (
    <>
      <DialogHeader>
        <DialogTitle>{model.name}</DialogTitle>
        <StateBadge model={model} />
      </DialogHeader>
      <div className="flex h-64 items-center justify-center rounded-md border bg-muted">
        {model.has_thumbnail ? (
          <img src={modelThumbnail(model.model_id)} alt={`Picture of ${model.name}`} className="size-full object-contain p-2" />
        ) : (
          <Package aria-hidden size={48} className="text-muted-foreground" />
        )}
      </div>
      <p className="text-sm">Stated size: {size(model)}</p>
      {model.state === "ready" && measured && (
        <p className="text-sm">
          Measured: {Math.round(measured.x)} × {Math.round(measured.y)} × {Math.round(measured.z)} mm
          {model.triangles !== null && `, ${model.triangles} triangles`}
        </p>
      )}
      {model.reason && <p className="text-sm text-muted-foreground">{model.reason}</p>}
      <div>
        <Button variant="secondary" size="sm" disabled={remove.isPending} onClick={() => remove.mutate()}>
          Delete {model.name}
        </Button>
      </div>
      <FieldError message={message(remove.error)} />
    </>
  );
}

/**
 * Draws each ready model that has no preview picture, one at a time, and stores the picture. A model
 * that cannot be drawn keeps its placeholder and is not tried again while the view stays open.
 */
function usePreviewPictures(models: ModelAsset[] | undefined) {
  const queryClient = useQueryClient();
  const failed = useRef(new Set<string>());
  const busy = useRef(false);
  const [attempts, setAttempts] = useState(0);
  useEffect(() => {
    if (busy.current) return;
    const next = models?.find((m) => m.state === "ready" && !m.has_thumbnail && !failed.current.has(m.model_id));
    if (!next) return;
    busy.current = true;
    drawModel(next)
      .then((picture) => api.storeModelThumbnail(next.model_id, picture))
      .then(() => queryClient.invalidateQueries({ queryKey: ["model-library"] }))
      .catch(() => failed.current.add(next.model_id))
      .finally(() => {
        busy.current = false;
        setAttempts((n) => n + 1);
      });
  }, [models, attempts]);
}

/** The upload form, in the "Upload model" dialog; a refusal keeps what was typed. */
function UploadForm({ onUploaded }: { onUploaded: (model: ModelAsset) => void }) {
  const files = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [width, setWidth] = useState("");
  const [depth, setDepth] = useState("");
  const [height, setHeight] = useState("");
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadModel(file, name, width, depth, height),
    onSuccess: onUploaded,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const file = files.current?.files?.[0];
    if (file) upload.mutate(file);
  }

  return (
    <form onSubmit={submit} aria-label="Upload a model" className="[&_input]:block [&_label]:mb-1.5 [&_label]:mt-3">
      <DialogHeader>
        <DialogTitle>Upload a model</DialogTitle>
      </DialogHeader>
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
      <p className="mt-4"><Button type="submit" disabled={upload.isPending}>Upload model</Button></p>
    </form>
  );
}

/**
 * Bought furniture and decor as 3D models (split-rooms-page): "Uploaded models" as tiles, each opening
 * its dialog at `/studio/models/<id>`, and "Upload model" as a dialog at `/studio/models/upload` (studio-tile-grid).
 */
export default function ModelLibrary() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const dialog = useStudioDialog("models");
  const pageSize = useMediaQuery(LAPTOP) ? LAPTOP_PAGE : PHONE_PAGE;
  const library = useQuery({
    queryKey: ["model-library"],
    queryFn: api.modelLibrary,
    // A model is checked in the background; follow it until every check is over.
    refetchInterval: (query) => (query.state.data?.some((m) => m.state === "checking") ? 2000 : false),
  });
  usePreviewPictures(library.data);
  const uploading = dialog.segments.length === 1 && dialog.segments[0] === "upload";
  const opened = uploading ? undefined : library.data?.find((m) => dialog.segments.length === 1 && m.model_id === dialog.segments[0]);
  // An address naming no model (unknown, or just deleted) shows the grid.
  const missing = Boolean(library.data) && dialog.segments.length > 0 && !uploading && !opened;
  useEffect(() => {
    if (missing) dialog.dismiss();
  }, [missing]);

  function uploaded(model: ModelAsset) {
    const listed = [...(library.data ?? []), model];
    queryClient.setQueryData(["model-library"], listed);
    queryClient.invalidateQueries({ queryKey: ["model-library"] });
    // Models are listed oldest first: the new one is on the last page.
    const page = Math.ceil(listed.length / pageSize);
    navigate(page > 1 ? `/studio/models?page=${page}` : "/studio/models", { replace: true });
  }

  return (
    <>
      <p>Bought furniture and decor as 3D models: a GLB file, or a zip with one glTF or OBJ model and its files.</p>
      {library.error && <FieldError message={message(library.error)} />}
      {library.data && library.data.length === 0 && <p>No models yet. Choose Upload model to add one.</p>}
      <TileGrid label="Uploaded models" items={library.data ?? []} keyOf={(model) => model.model_id}>
        {(model) => (
          <Tile
            name={model.name}
            detail={size(model)}
            picture={model.has_thumbnail ? modelThumbnail(model.model_id) : null}
            placeholder={Package}
            badge={<StateBadge model={model} />}
            onOpen={() => dialog.open(model.model_id)}
          />
        )}
      </TileGrid>
      <Dialog open={uploading || Boolean(opened)} onOpenChange={(open) => !open && dialog.close()}>
        {uploading && (
          <DialogContent aria-describedby={undefined}>
            <UploadForm onUploaded={uploaded} />
          </DialogContent>
        )}
        {opened && (
          <DialogContent aria-describedby={undefined}>
            <ModelDetail key={opened.model_id} model={opened} />
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
