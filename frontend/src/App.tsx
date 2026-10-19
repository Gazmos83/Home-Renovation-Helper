import { useEffect, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation, useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { api, onUnauthorized } from "./lib/api";
import { Page } from "@/components/Page";
import { Button } from "@/components/ui/button";
import { Footer } from "@/components/Footer";
import { HouseIcon } from "@/components/HouseIcon";
import About from "./routes/About";
import Crew from "./routes/Crew";
import Help from "./routes/Help";
import Landing, { SiteBar } from "./routes/Landing";
import Login from "./routes/Login";
import PieceInspector from "./routes/PieceInspector";
import Studio from "./routes/Studio";

/** The home page: the Design Studio's Workspace, which opens the newest conversation (workspace-chat-above-layout). */
const HOME = "/studio/workspace";

const links = [
  ["/help", "Help"],
  ["/about", "About"],
] as const;

const navItemClass = (active: boolean) =>
  cn(
    "shrink-0 rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors hover:bg-accent",
    active ? "bg-accent text-accent-foreground" : "text-muted-foreground",
  );

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink to={to} className={({ isActive }) => navItemClass(isActive)}>
      {label}
    </NavLink>
  );
}

/** `/pricing/<tab>`, the Pricing Overview page's old address, opens that view of the Design Studio's Pricing tab. */
function PricingRedirect() {
  const { tab = "prices" } = useParams();
  return <Navigate to={`/studio/pricing/${tab}`} replace />;
}

/** `/conversations/<id>`, the conversation page's old address, opens it in the Workspace with its pane choices. */
function ConversationRedirect() {
  const { threadId = "" } = useParams();
  const { search } = useLocation();
  return <Navigate to={`/studio/workspace/${threadId}${search}`} replace />;
}

/** Ends the session and returns to sign-in; a failed request leaves the owner signed in and says why. */
function SignOut({ onSignedOut }: { onSignedOut: () => void }) {
  const [refused, setRefused] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    setRefused(null);
    try {
      await api.logout();
      onSignedOut();
    } catch (caught) {
      setRefused(caught instanceof Error ? caught.message : "sign-out failed");
      setBusy(false);
    }
  }
  return (
    <div className="ml-1 flex shrink-0 items-center gap-2">
      {refused && <span role="alert" className="text-sm text-destructive">{refused}</span>}
      <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => void signOut()}>
        Sign out
      </Button>
    </div>
  );
}

export default function App() {
  const location = useLocation();
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  // null until the developer check answers, so a reloaded developer page is not redirected away.
  const [dev, setDev] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .me()
      .then(() => setSignedIn(true))
      .catch(() => setSignedIn(false));
  }, [location.pathname]);

  // Any call answered 401 returns the owner to sign-in.
  useEffect(() => onUnauthorized(() => setSignedIn(false)), []);

  useEffect(() => {
    if (signedIn === null) return;
    if (!signedIn) {
      setDev(false);
      return;
    }
    api
      .models()
      .then(() => setDev(true))
      .catch(() => setDev(false));
  }, [signedIn]);

  if (signedIn === null || (signedIn && dev === null)) return <Page>Loading…</Page>;

  return (
    <>
      {signedIn && (
        <header className="sticky top-0 z-40 h-[var(--header-h)] border-b bg-card">
          <nav aria-label="Main" className="flex h-full items-center gap-1 overflow-x-auto px-4 sm:px-6">
            <Link to={HOME} className="mr-4 flex shrink-0 items-center gap-2 font-semibold whitespace-nowrap">
              <HouseIcon />
              Little Homey
            </Link>
            <div className="ml-auto flex shrink-0 items-center gap-1">
              {links.map(([to, label]) => (
                <NavItem key={to} to={to} label={label} />
              ))}
              <SignOut onSignedOut={() => setSignedIn(false)} />
            </div>
          </nav>
        </header>
      )}
      <Routes>
        <Route path="/" element={signedIn ? <Navigate to={HOME} replace /> : <Landing />} />
        <Route
          path="/crew"
          element={
            signedIn ? (
              <Crew />
            ) : (
              <>
                <SiteBar />
                <Crew />
              </>
            )
          }
        />
        <Route path="/login" element={<Login onSignedIn={() => setSignedIn(true)} />} />
        <Route path="/conversations" element={<Navigate to="/studio/workspace" replace />} />
        <Route path="/conversations/:threadId" element={<ConversationRedirect />} />
        <Route path="/studio" element={signedIn ? <Studio dev={dev ?? false} /> : <Navigate to="/login" replace />} />
        <Route path="/studio/:tab/*" element={signedIn ? <Studio dev={dev ?? false} /> : <Navigate to="/login" replace />} />
        <Route path="/pieces" element={<Navigate to="/studio/pieces" replace />} />
        <Route
          path="/pieces/:packageId/versions/:version"
          element={signedIn ? <PieceInspector /> : <Navigate to="/login" replace />}
        />
        <Route path="/rooms" element={<Navigate to="/studio/rooms" replace />} />
        <Route path="/models" element={<Navigate to="/studio/models" replace />} />
        <Route path="/pricing" element={<Navigate to="/studio/pricing/prices" replace />} />
        <Route path="/pricing/:tab" element={<PricingRedirect />} />
        <Route path="/price-list" element={<Navigate to="/studio/pricing/prices" replace />} />
        <Route path="/snapshots" element={<Navigate to="/studio/pricing/snapshots" replace />} />
        <Route path="/remnants" element={<Navigate to="/studio/pricing/remnants" replace />} />
        <Route
          path="/guidelines"
          element={signedIn && dev ? <Navigate to="/admin/design-knowledge/guidelines" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route path="/help" element={signedIn ? <Help /> : <Navigate to="/login" replace />} />
        <Route
          path="/about"
          element={
            signedIn ? (
              <About />
            ) : (
              <>
                <SiteBar />
                <About />
              </>
            )
          }
        />
        <Route
          path="/admin/agents"
          element={signedIn && dev ? <Studio dev fixedTab="agents" /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/agents/:tab"
          element={signedIn && dev ? <Studio dev fixedTab="agents" /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/models"
          element={signedIn && dev ? <Navigate to="/admin/agents/models" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/plugins"
          element={signedIn && dev ? <Navigate to="/admin/agents/plugins" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/usage"
          element={signedIn && dev ? <Navigate to="/admin/agents/usage" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/feedback"
          element={signedIn && dev ? <Navigate to="/admin/agents/score" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/offload"
          element={signedIn && dev ? <Navigate to="/admin/agents/offload" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/conversations"
          element={signedIn && dev ? <Navigate to="/admin/agents/calls" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/workflow"
          element={signedIn && dev ? <Navigate to="/admin/agents/workflow" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/design-knowledge"
          element={signedIn && dev ? <Studio dev fixedTab="design-knowledge" /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/design-knowledge/:tab"
          element={signedIn && dev ? <Studio dev fixedTab="design-knowledge" /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/guidelines"
          element={signedIn && dev ? <Navigate to="/admin/design-knowledge/guidelines" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/rules"
          element={signedIn && dev ? <Navigate to="/admin/design-knowledge/rules" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/knowledge"
          element={signedIn && dev ? <Navigate to="/admin/design-knowledge/engineering" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route
          path="/admin/memory"
          element={signedIn && dev ? <Navigate to="/admin/agents/memory" replace /> : <Navigate to={signedIn ? HOME : "/login"} replace />}
        />
        <Route path="*" element={<Navigate to={signedIn ? HOME : "/login"} replace />} />
      </Routes>
      <Footer signedIn={Boolean(signedIn)} />
    </>
  );
}
