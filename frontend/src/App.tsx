import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { api, onUnauthorized } from "./lib/api";
import { Page } from "@/components/Page";
import Conversation from "./routes/Conversation";
import Conversations from "./routes/Conversations";
import GuidelineNotes from "./routes/GuidelineNotes";
import Login from "./routes/Login";
import Pieces from "./routes/Pieces";
import PieceInspector from "./routes/PieceInspector";
import PriceList from "./routes/PriceList";
import Remnants from "./routes/Remnants";
import Rooms from "./routes/Rooms";
import Snapshots from "./routes/Snapshots";
import Feedback from "./routes/admin/Feedback";
import Models from "./routes/admin/Models";
import Offload from "./routes/admin/Offload";
import Plugins from "./routes/admin/Plugins";
import Usage from "./routes/admin/Usage";

const links = [
  ["/conversations", "Conversations"],
  ["/pieces", "Pieces"],
  ["/rooms", "Rooms"],
  ["/price-list", "Price list"],
  ["/snapshots", "Snapshots"],
  ["/remnants", "Remnants"],
  ["/guidelines", "Guidelines"],
] as const;
const adminLinks = [
  ["/admin/models", "Models"],
  ["/admin/plugins", "Plugins"],
  ["/admin/usage", "Usage"],
  ["/admin/feedback", "Feedback"],
  ["/admin/offload", "Offload"],
] as const;

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent",
          isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground",
        )
      }
    >
      {label}
    </NavLink>
  );
}

export default function App() {
  const location = useLocation();
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [dev, setDev] = useState(false);

  useEffect(() => {
    api
      .me()
      .then(() => setSignedIn(true))
      .catch(() => setSignedIn(false));
  }, [location.pathname]);

  // Any call answered 401 returns the owner to sign-in.
  useEffect(() => onUnauthorized(() => setSignedIn(false)), []);

  useEffect(() => {
    if (!signedIn) {
      setDev(false);
      return;
    }
    api
      .models()
      .then(() => setDev(true))
      .catch(() => setDev(false));
  }, [signedIn]);

  if (signedIn === null) return <Page>Loading…</Page>;

  return (
    <>
      {signedIn && (
        <header className="border-b bg-card">
          <nav aria-label="Main" className="mx-auto flex max-w-5xl flex-wrap items-center gap-1 px-4 py-2 sm:px-6">
            <span className="mr-4 font-semibold">Home Renovation</span>
            {links.map(([to, label]) => (
              <NavItem key={to} to={to} label={label} />
            ))}
            {dev && (
              <>
                <span className="mx-2 h-5 w-px bg-border" aria-hidden />
                {adminLinks.map(([to, label]) => (
                  <NavItem key={to} to={to} label={label} />
                ))}
              </>
            )}
          </nav>
        </header>
      )}
      <Routes>
        <Route path="/login" element={<Login onSignedIn={() => setSignedIn(true)} />} />
        <Route
          path="/conversations"
          element={signedIn ? <Conversations /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/conversations/:threadId"
          element={signedIn ? <Conversation /> : <Navigate to="/login" replace />}
        />
        <Route path="/pieces" element={signedIn ? <Pieces /> : <Navigate to="/login" replace />} />
        <Route
          path="/pieces/:packageId/versions/:version"
          element={signedIn ? <PieceInspector /> : <Navigate to="/login" replace />}
        />
        <Route path="/rooms" element={signedIn ? <Rooms /> : <Navigate to="/login" replace />} />
        <Route path="/price-list" element={signedIn ? <PriceList /> : <Navigate to="/login" replace />} />
        <Route path="/snapshots" element={signedIn ? <Snapshots /> : <Navigate to="/login" replace />} />
        <Route path="/remnants" element={signedIn ? <Remnants /> : <Navigate to="/login" replace />} />
        <Route path="/guidelines" element={signedIn ? <GuidelineNotes /> : <Navigate to="/login" replace />} />
        <Route
          path="/admin/models"
          element={signedIn && dev ? <Models /> : <Navigate to={signedIn ? "/conversations" : "/login"} replace />}
        />
        <Route
          path="/admin/plugins"
          element={signedIn && dev ? <Plugins /> : <Navigate to={signedIn ? "/conversations" : "/login"} replace />}
        />
        <Route
          path="/admin/usage"
          element={signedIn && dev ? <Usage /> : <Navigate to={signedIn ? "/conversations" : "/login"} replace />}
        />
        <Route
          path="/admin/feedback"
          element={signedIn && dev ? <Feedback /> : <Navigate to={signedIn ? "/conversations" : "/login"} replace />}
        />
        <Route
          path="/admin/offload"
          element={signedIn && dev ? <Offload /> : <Navigate to={signedIn ? "/conversations" : "/login"} replace />}
        />
        <Route path="*" element={<Navigate to={signedIn ? "/conversations" : "/login"} replace />} />
      </Routes>
    </>
  );
}
