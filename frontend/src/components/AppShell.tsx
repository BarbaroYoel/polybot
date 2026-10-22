import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useOnlineStatus } from "../lib/useOnlineStatus";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import "./AppShell.css";

export function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const online = useOnlineStatus();
  const location = useLocation();

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="shell">
      <a className="shell__skip" href="#contenido">
        Saltar al contenido
      </a>

      <Sidebar open={drawerOpen} onClose={() => setDrawerOpen(false)} />

      <div className="shell__main">
        <TopBar onOpenMenu={() => setDrawerOpen(true)} />
        {!online && (
          <p className="shell__offline" role="status">
            Sin conexión. La carcasa de la app funciona, pero la conversación y la voz necesitan red.
          </p>
        )}
        <main className="shell__content" id="contenido">
          <Outlet />
        </main>
      </div>

      {drawerOpen && (
        <button
          type="button"
          className="shell__scrim"
          aria-label="Cerrar menú de navegación"
          onClick={() => setDrawerOpen(false)}
        />
      )}
    </div>
  );
}
