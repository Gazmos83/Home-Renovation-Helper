import { useEffect, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation, useParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import { api, onUnauthorized } from "./lib/api";
import { Page } from "@/components/Page";
import Help from "./routes/Help";
import Login from "./routes/Login";
import PieceInspector from "./routes/PieceInspector";
import Studio from "./routes/Studio";

const links = [
  ["/studio", "Design Studio"],
  ["/help", "Help"],
] as const;

/** The Design Studio's developer tabs keep the developer route tree, so its entry is current there too. */
const ALSO_CURRENT: Record<string, string[]> = { "/studio": ["/admin/agents", "/admin/design-knowledge"] };

const navItemClass = (active: boolean) =>
  cn(
    "shrink-0 rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors hover:bg-accent",
    active ? "bg-accent text-accent-foreground" : "text-muted-foreground",
  );

function NavItem({ to, label }: { to: string; label: string }) {
  const { pathname } = useLocation();
  const also = ALSO_CURRENT[to] ?? [];
  // NavLink marks only its own path current, so the other paths get a plain link marked by hand.
  if (also.some((path) => pathname === path || pathname.startsWith(`${path}/`))) {
    return (
      <Link to={to} aria-current="page" className={navItemClass(true)}>
        {label}
      </Link>
    );
  }
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
          <nav aria-label="Main" className="mx-auto flex h-full max-w-5xl items-center gap-1 overflow-x-auto px-4 sm:px-6">
            <span className="mr-4 shrink-0 font-semibold whitespace-nowrap">Home Renovation</span>
            {links.map(([to, label]) => (
              <NavItem key={to} to={to} label={label} />
            ))}
          </nav>
        </header>
      )}
      <Routes>
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
          element={signedIn && dev ? <Navigate to="/admin/design-knowledge/guidelines" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route path="/help" element={signedIn ? <Help /> : <Navigate to="/login" replace />} />
        <Route
          path="/admin/agents"
          element={signedIn && dev ? <Studio dev fixedTab="agents" /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/agents/:tab"
          element={signedIn && dev ? <Studio dev fixedTab="agents" /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/models"
          element={signedIn && dev ? <Navigate to="/admin/agents/models" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/plugins"
          element={signedIn && dev ? <Navigate to="/admin/agents/plugins" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/usage"
          element={signedIn && dev ? <Navigate to="/admin/agents/usage" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/feedback"
          element={signedIn && dev ? <Navigate to="/admin/agents/score" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/offload"
          element={signedIn && dev ? <Navigate to="/admin/agents/offload" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/conversations"
          element={signedIn && dev ? <Navigate to="/admin/agents/calls" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/workflow"
          element={signedIn && dev ? <Navigate to="/admin/agents/workflow" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/design-knowledge"
          element={signedIn && dev ? <Studio dev fixedTab="design-knowledge" /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/design-knowledge/:tab"
          element={signedIn && dev ? <Studio dev fixedTab="design-knowledge" /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/guidelines"
          element={signedIn && dev ? <Navigate to="/admin/design-knowledge/guidelines" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/rules"
          element={signedIn && dev ? <Navigate to="/admin/design-knowledge/rules" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/knowledge"
          element={signedIn && dev ? <Navigate to="/admin/design-knowledge/engineering" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route
          path="/admin/memory"
          element={signedIn && dev ? <Navigate to="/admin/agents/memory" replace /> : <Navigate to={signedIn ? "/pieces" : "/login"} replace />}
        />
        <Route path="*" element={<Navigate to={signedIn ? "/pieces" : "/login"} replace />} />
      </Routes>
    </>
  );
}
