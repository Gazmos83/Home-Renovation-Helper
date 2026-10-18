import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

// The footer's version and build (little-homey-brand-about-footer): read once when Vite starts.
const VERSION = JSON.parse(readFileSync(path.resolve(__dirname, "package.json"), "utf-8")).version as string;
function commit(): string {
  try {
    return execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim() || "dev";
  } catch {
    return "dev";
  }
}

const API = process.env.API_PROXY ?? "http://127.0.0.1:8000";

// These pages share their path with an API route: a browser navigation (it asks for
// HTML) gets the app, every other request goes to the API.
const page = { target: API, bypass: (req: { headers: { accept?: string } }) => (req.headers.accept?.includes("text/html") ? "/index.html" : undefined) };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Fixed values under Vitest, so tests never depend on the checkout.
  define: process.env.VITEST
    ? { __APP_VERSION__: JSON.stringify("0.0.0"), __APP_BUILD__: JSON.stringify("test") }
    : { __APP_VERSION__: JSON.stringify(VERSION), __APP_BUILD__: JSON.stringify(commit()) },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: {
      // Long Foreman turns stream for minutes; default proxy idle timeouts drop the SSE
      // socket and the SPA shows "NetworkError when attempting to fetch resource."
      "/chat": { target: API, timeout: 0, proxyTimeout: 0 },
      "/auth": API,
      // Before "/admin": a remote benchmark or a pod start can run for over ten minutes, and the
      // default proxy timeouts would drop the answer, leaving the panel without its message.
      "/admin/offload": { target: API, timeout: 0, proxyTimeout: 0 },
      "/admin": page,
      "/health": API,
      // API-only: the Studio route is /pieces; without this proxy GET /packages
      // is the SPA HTML and the Pieces page never leaves Loading.
      "/packages": API,
      "/design-import": API,
      "/compositions": API,
      "/models": page,
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
      "/help": page,
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
