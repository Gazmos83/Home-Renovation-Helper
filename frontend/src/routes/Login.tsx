import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cardClass } from "@/components/ui/card";

export default function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.login(email, password);
      onSignedIn();
      navigate("/pieces");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "sign-in failed");
    }
  }

  return (
    <main className="mx-auto max-w-sm space-y-4 px-4 py-16">
      <h1>Sign in</h1>
      <form onSubmit={submit} className={cardClass}>
        <Label htmlFor="email">Email</Label>
        <Input id="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="mt-4 w-full">Sign in</Button>
      </form>
    </main>
  );
}
