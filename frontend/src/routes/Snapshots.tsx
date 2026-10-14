import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../lib/api";
import { FieldError, fieldError, formError } from "../lib/form";
import { toCents } from "../lib/money";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";

const FIELDS = ["retailer", "url", "product_name", "price", "specification", "captured_on", "key", "category", "unit"];

export default function Snapshots() {
  const queryClient = useQueryClient();
  const snapshots = useQuery({ queryKey: ["snapshots"], queryFn: api.snapshots });
  const [retailer, setRetailer] = useState("toom");
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [specification, setSpecification] = useState("");
  const [capturedOn, setCapturedOn] = useState("");
  const [prefill, setPrefill] = useState(false);
  const [entryKey, setEntryKey] = useState("");
  const [local, setLocal] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: api.createSnapshot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["snapshots"] });
      queryClient.invalidateQueries({ queryKey: ["price-list"] });
    },
  });
  const remove = useMutation({
    mutationFn: api.deleteSnapshot,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["snapshots"] }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const cents = price.trim() ? toCents(price) : null;
    if (price.trim() && cents === null) return setLocal("Enter the price as euros, for example 12,50.");
    setLocal(null);
    create.mutate({
      retailer, url, product_name: name, specification, captured_on: capturedOn,
      price: cents === null ? null : (cents / 100).toFixed(2), currency: cents === null ? null : "EUR",
      availability: null, store_name: null,
      ...(prefill ? { prefill: { key: entryKey, category: "panel", unit: "per_piece" } } : {}),
    });
  }

  return (
    <>
      <p>A page the crawl cannot reach, recorded by hand.</p>
      {(snapshots.data ?? []).map((snapshot) => (
        <section key={snapshot.id} className={cardClass}>
          <div className="flex items-center justify-between gap-4">
            <div>
              <strong>{snapshot.product_name}</strong>
              <br /><small className="text-muted-foreground">{snapshot.retailer} · {snapshot.captured_on}{snapshot.price ? ` · ${snapshot.price} ${snapshot.currency ?? ""}` : ""}</small>
            </div>
            <Button variant="secondary" size="sm" onClick={() => remove.mutate(snapshot.id)}>Delete {snapshot.product_name}</Button>
          </div>
        </section>
      ))}
      <form onSubmit={submit} className={cardClass} aria-label="Record a snapshot">
        <h2>Record a snapshot</h2>
        <Label htmlFor="retailer">Retailer</Label>
        <Input id="retailer" value={retailer} onChange={(e) => setRetailer(e.target.value)} />
        <FieldError message={fieldError(create.error, "retailer")} />
        <Label htmlFor="snapshot-url">Page URL</Label>
        <Input id="snapshot-url" value={url} onChange={(e) => setUrl(e.target.value)} />
        <FieldError message={fieldError(create.error, "url")} />
        <Label htmlFor="product-name">Product name</Label>
        <Input id="product-name" value={name} onChange={(e) => setName(e.target.value)} />
        <FieldError message={fieldError(create.error, "product_name")} />
        <Label htmlFor="snapshot-price">Price (€)</Label>
        <Input id="snapshot-price" value={price} onChange={(e) => setPrice(e.target.value)} />
        <FieldError message={local ?? fieldError(create.error, "price")} />
        <Label htmlFor="specification">Specification</Label>
        <Input id="specification" value={specification} onChange={(e) => setSpecification(e.target.value)} />
        <FieldError message={fieldError(create.error, "specification")} />
        <Label htmlFor="captured-on">Captured on</Label>
        <Input id="captured-on" type="date" value={capturedOn} onChange={(e) => setCapturedOn(e.target.value)} />
        <FieldError message={fieldError(create.error, "captured_on")} />
        <Label>
          <Input type="checkbox" checked={prefill} onChange={(e) => setPrefill(e.target.checked)} /> Also create a price-list entry
        </Label>
        {prefill && (
          <>
            <Label htmlFor="entry-key">Entry key</Label>
            <Input id="entry-key" value={entryKey} onChange={(e) => setEntryKey(e.target.value)} />
            <FieldError message={fieldError(create.error, "key")} />
          </>
        )}
        <FieldError message={formError(create.error, FIELDS)} />
        <p><Button type="submit">Record snapshot</Button></p>
      </form>
    </>
  );
}
