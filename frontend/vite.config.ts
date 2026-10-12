import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

const API = process.env.API_PROXY ?? "http://127.0.0.1:8000";

// These pages share their path with an API route: a browser navigation (it asks for
// HTML) gets the app, every other request goes to the API.
const page = { target: API, bypass: (req: { headers: { accept?: string } }) => (req.headers.accept?.includes("text/html") ? "/index.html" : undefined) };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: {
      "/chat": API,
      "/auth": API,
      "/admin": page,
      "/health": API,
      // API-only: the Studio route is /pieces; without this proxy GET /packages
      // is the SPA HTML and the Pieces page never leaves Loading.
      "/packages": API,
      "/design-import": API,
      "/compositions": API,
      "/models": API,
      "/uploads": API,
      "/apartments": API,
      "/reviews": API,
      "/pricings": API,
      "/stores": API,
      "/rooms": page,
      "/price-list": page,
      "/snapshots": page,
      "/remnants": page,
      "/guideline-notes": page,
      // API-only: hardware data sheets live on the guidelines page, not their own route.
      "/hardware-data": API,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
