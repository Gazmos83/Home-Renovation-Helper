import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { FieldError } from "@/lib/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cardClass } from "@/components/ui/card";

/**
 * The owner's account list. A member signs in like the owner and sees only its own pieces, rooms and
 * conversations; it never sees these developer pages. The owner account cannot be removed.
 */
export default function Users() {
  const queryClient = useQueryClient();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: api.adminUsers });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  const add = useMutation({
    mutationFn: () => api.addMember({ email: email.trim(), password }),
    onSuccess: () => {
      setEmail("");
      setPassword("");
      void refresh();
    },
  });
  const remove = useMutation({ mutationFn: api.removeMember, onSuccess: () => void refresh() });
  const error = (failed: unknown) => (failed instanceof Error ? failed.message : null);

  return (
    <div className="space-y-4">
      <h1>Accounts</h1>
      <section className={cardClass} aria-label="Accounts">
        {users.isLoading ? <p>Loading…</p> : null}
        <ul className="divide-y">
          {(users.data ?? []).map((user) => (
            <li key={user.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                {user.email} <span className="text-sm text-muted-foreground">{user.is_owner ? "owner" : "member"}</span>
              </span>
              {user.is_owner ? null : (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(user.id)}
                >
                  Remove
                </Button>
              )}
            </li>
          ))}
        </ul>
        <FieldError message={error(remove.error)} />
      </section>
      <section className={cardClass} aria-label="Add a member">
        <h2>Add a member</h2>
        <div className="grid gap-2 sm:max-w-md">
          <label className="grid gap-1 text-sm">
            Email
            <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="grid gap-1 text-sm">
            Starting password (at least 10 characters)
            <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <div>
            <Button type="button" size="sm" disabled={add.isPending || !email.trim() || !password} onClick={() => add.mutate()}>
              Add member
            </Button>
          </div>
          <FieldError message={error(add.error)} />
        </div>
      </section>
    </div>
  );
}
