import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../lib/api";
import { FieldError, fieldError, formError } from "../lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

export default function Remnants() {
  const queryClient = useQueryClient();
  const rack = useQuery({ queryKey: ["remnants"], queryFn: api.remnants });
  const [materialKey, setMaterialKey] = useState("");
  const [length, setLength] = useState("");
  const [width, setWidth] = useState("");
  const [grain, setGrain] = useState<"length" | "width">("length");
  const [quantity, setQuantity] = useState("1");
  const reload = () => queryClient.invalidateQueries({ queryKey: ["remnants"] });
  const add = useMutation({ mutationFn: api.addRemnant, onSuccess: reload });
  const remove = useMutation({ mutationFn: api.removeRemnant, onSuccess: reload });

  function submit(event: FormEvent) {
    event.preventDefault();
    add.mutate({
      material_key: materialKey, length_mm: Number(length), width_mm: Number(width),
      grain_axis: grain, quantity: Number(quantity),
    });
  }

  return (
    <Page>
      <h1>Remnants</h1>
      <p>Offcuts in the workshop. Pricing uses them before it counts a new sheet.</p>
      {rack.data && rack.data.length === 0 && <p>The rack is empty.</p>}
      {(rack.data ?? []).map((r) => (
        <section key={r.id} className={cardClass}>
          <div className="flex items-center justify-between gap-4">
            <span>{r.quantity} × {r.material_key}, {r.length_mm} × {r.width_mm} mm, grain along its {r.grain_axis}</span>
            <Button variant="secondary" size="sm" onClick={() => remove.mutate(r.id)}>Remove {r.material_key} {r.length_mm}×{r.width_mm}</Button>
          </div>
        </section>
      ))}
      <form onSubmit={submit} className={cardClass} aria-label="Add a remnant">
        <h2>Add a remnant</h2>
        <Label htmlFor="material-key">Material key</Label>
        <Input id="material-key" value={materialKey} onChange={(e) => setMaterialKey(e.target.value)} />
        <FieldError message={fieldError(add.error, "material_key")} />
        <Label htmlFor="remnant-length">Length (mm)</Label>
        <Input id="remnant-length" value={length} onChange={(e) => setLength(e.target.value)} />
        <FieldError message={fieldError(add.error, "length_mm")} />
        <Label htmlFor="remnant-width">Width (mm)</Label>
        <Input id="remnant-width" value={width} onChange={(e) => setWidth(e.target.value)} />
        <FieldError message={fieldError(add.error, "width_mm")} />
        <Label htmlFor="grain">Grain runs along its</Label>
        <Select id="grain" value={grain} onChange={(e) => setGrain(e.target.value as "length" | "width")}>
          <option>length</option>
          <option>width</option>
        </Select>
        <Label htmlFor="remnant-quantity">Quantity</Label>
        <Input id="remnant-quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        <FieldError message={fieldError(add.error, "quantity")} />
        <FieldError message={formError(add.error, ["material_key", "length_mm", "width_mm", "quantity"])} />
        <p><Button type="submit">Add remnant</Button></p>
      </form>
    </Page>
  );
}
