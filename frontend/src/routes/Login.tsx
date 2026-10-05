import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

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
      navigate("/conversations");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "sign-in failed");
    }
  }

  return (
    <main>
      <h1>Sign in</h1>
      <form onSubmit={submit} className="card">
        <label htmlFor="email">Email</label>
        <input id="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <p className="error">{error}</p>}
        <p>
          <button type="submit">Sign in</button>
        </p>
      </form>
    </main>
  );
}
