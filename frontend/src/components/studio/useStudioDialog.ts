import { useLocation, useNavigate } from "react-router-dom";

/**
 * The open dialog of a Design Studio tab, read from the address (studio-tile-grid): the path after
 * `/studio/<tab>/`, split into decoded segments, or `[]` for the grid. Opening pushes the dialog's address,
 * keeping `?page`, so browser Back closes it; closing goes back when the dialog was opened from the grid,
 * and otherwise replaces the address with the grid's, so a dialog reached by a link never leaves the app.
 */
export function useStudioDialog(tab: string) {
  const location = useLocation();
  const navigate = useNavigate();
  const base = `/studio/${tab}`;
  const rest = location.pathname.startsWith(`${base}/`) ? location.pathname.slice(base.length + 1) : "";
  const segments = rest.split("/").filter(Boolean).map(decodeURIComponent);
  const fromGrid = (location.state as { fromGrid?: boolean } | null)?.fromGrid === true;

  return {
    segments,
    /** Open the dialog at these path segments (each encoded here). */
    open(...path: string[]) {
      navigate(`${base}/${path.map(encodeURIComponent).join("/")}${location.search}`, { state: { fromGrid: true } });
    },
    close() {
      if (fromGrid) navigate(-1);
      else navigate(`${base}${location.search}`, { replace: true });
    },
    /** Drop a dialog address naming no item (unknown, or just deleted): the grid, in place of it in history. */
    dismiss() {
      navigate(`${base}${location.search}`, { replace: true });
    },
    /** The grid address, keeping the page. */
    grid: `${base}${location.search}`,
  };
}
