import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, type GuidelineNote } from "../lib/api";
import { FieldError, fieldError, formError } from "../lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";
import { Page } from "@/components/Page";

const FIELDS = ["title", "body", "citation", "value", "unit"];

function NoteForm({ note, onDone }: { note?: GuidelineNote; onDone: () => void }) {
  const [title, setTitle] = useState(note?.title ?? "");
  const [body, setBody] = useState(note?.body ?? "");
  const [value, setValue] = useState(note?.value === null || note?.value === undefined ? "" : String(note.value));
  const [unit, setUnit] = useState(note?.unit ?? "");
  const [citation, setCitation] = useState(note?.citation ?? "");
  const save = useMutation({
    mutationFn: (payload: Omit<GuidelineNote, "id">) => (note ? api.updateNote(note.id, payload) : api.createNote(payload)),
    onSuccess: () => {
      if (!note) { setTitle(""); setBody(""); setValue(""); setUnit(""); setCitation(""); }
      onDone();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({
      title, body, citation, unit: unit.trim() || null,
      value: value.trim() ? Number(value.replace(",", ".")) : null,
    });
  }
  const id = note?.id ?? "new";

  return (
    <form onSubmit={submit} className={cardClass} aria-label={note ? `Edit ${note.title}` : "Add a note"}>
      <h2>{note ? "Edit note" : "Add a note"}</h2>
      <Label htmlFor={`title-${id}`}>Title</Label>
      <Input id={`title-${id}`} value={title} onChange={(e) => setTitle(e.target.value)} />
      <FieldError message={fieldError(save.error, "title")} />
      <Label htmlFor={`body-${id}`}>Text</Label>
      <Input id={`body-${id}`} value={body} onChange={(e) => setBody(e.target.value)} />
      <FieldError message={fieldError(save.error, "body")} />
      <Label htmlFor={`value-${id}`}>Number (optional)</Label>
      <Input id={`value-${id}`} value={value} onChange={(e) => setValue(e.target.value)} />
      <Label htmlFor={`unit-${id}`}>Unit</Label>
      <Input id={`unit-${id}`} value={unit} onChange={(e) => setUnit(e.target.value)} />
      <FieldError message={fieldError(save.error, "unit") ?? fieldError(save.error, "value")} />
      <Label htmlFor={`citation-${id}`}>Source citation</Label>
      <Input id={`citation-${id}`} value={citation} onChange={(e) => setCitation(e.target.value)} />
      <FieldError message={fieldError(save.error, "citation")} />
      <FieldError message={formError(save.error, FIELDS)} />
      <p><Button type="submit">{note ? "Save note" : "Add note"}</Button></p>
    </form>
  );
}

export default function GuidelineNotes() {
  const queryClient = useQueryClient();
  const notes = useQuery({ queryKey: ["guideline-notes"], queryFn: api.guidelineNotes });
  const [editing, setEditing] = useState<string | null>(null);
  const reload = () => queryClient.invalidateQueries({ queryKey: ["guideline-notes"] });
  const remove = useMutation({ mutationFn: api.deleteNote, onSuccess: reload });

  return (
    <Page>
      <h1>Guideline notes</h1>
      <p>Rules and numbers from your own sources. The designer can look them up and cites the source you give.</p>
      {(notes.data ?? []).map((note) =>
        editing === note.id ? (
          <NoteForm key={note.id} note={note} onDone={() => { setEditing(null); reload(); }} />
        ) : (
          <section key={note.id} className={cardClass}>
            <div className="flex items-center justify-between gap-4">
              <div>
                <strong>{note.title}</strong>
                {note.value !== null && <> — {note.value} {note.unit}</>}
                <p>{note.body}</p>
                <small className="text-muted-foreground">Source: {note.citation}</small>
              </div>
              <div>
                <Button variant="secondary" size="sm" onClick={() => setEditing(note.id)}>Edit {note.title}</Button>{" "}
                <Button variant="secondary" size="sm" onClick={() => remove.mutate(note.id)}>Delete {note.title}</Button>
              </div>
            </div>
          </section>
        ),
      )}
      <NoteForm onDone={reload} />
    </Page>
  );
}
