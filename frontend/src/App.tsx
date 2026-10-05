import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./lib/api";
import Conversations from "./routes/Conversations";
import Login from "./routes/Login";
import Models from "./routes/admin/Models";
import Plugins from "./routes/admin/Plugins";
import Usage from "./routes/admin/Usage";

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

  if (signedIn === null) return <main>Loading…</main>;

  return (
    <>
      {signedIn && (
        <nav>
          <Link to="/conversations">Conversations</Link>
          {dev && (
            <>
              <Link to="/admin/models">Models</Link>
              <Link to="/admin/plugins">Plugins</Link>
              <Link to="/admin/usage">Usage</Link>
            </>
          )}
        </nav>
      )}
      <Routes>
        <Route path="/login" element={<Login onSignedIn={() => setSignedIn(true)} />} />
        <Route
          path="/conversations"
          element={signedIn ? <Conversations /> : <Navigate to="/login" replace />}
        />
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
        <Route path="*" element={<Navigate to={signedIn ? "/conversations" : "/login"} replace />} />
      </Routes>
    </>
  );
}
