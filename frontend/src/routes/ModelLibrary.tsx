import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { api } from "../lib/api";
import { FieldError, fieldError, formError } from "../lib/form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";

function message(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}

/** Bought furniture and decor as 3D models, laid out like the Pieces page (split-rooms-page). */
export default function ModelLibrary() {
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
    <>
      <p>Bought furniture and decor as 3D models: a GLB file, or a zip with one glTF or OBJ model and its files.</p>
      {library.error && <FieldError message={message(library.error)} />}
      {library.data && library.data.length === 0 && <p>No models yet.</p>}
      {(library.data ?? []).map((model) => (
        <section key={model.model_id} className={cardClass} aria-label={model.name}>
          <div className="flex flex-wrap items-center gap-2">
            <h2>{model.name}</h2>
            <Badge variant={model.state === "refused" ? "destructive" : "outline"}>{model.state}</Badge>
          </div>
          <p className="text-sm">
            {model.width_mm} × {model.depth_mm} × {model.height_mm} mm
          </p>
          {model.reason && <p className="text-sm text-muted-foreground">{model.reason}</p>}
          <div>
            <Button variant="secondary" size="sm" onClick={() => remove.mutate(model.model_id)}>
              Delete {model.name}
            </Button>
          </div>
        </section>
      ))}
      <FieldError message={message(remove.error)} />
      <form onSubmit={submit} className={cardClass} aria-label="Upload a model">
        <h2>Upload a model</h2>
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
    </>
  );
}
