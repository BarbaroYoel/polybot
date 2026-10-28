import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Codespaces serves the dev server through <codespace>-5173.app.github.dev.
    allowedHosts: [".app.github.dev"],
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // The interpreter is the only WebSocket of the app (ADR-022).
        ws: true,
      },
    },
  },
  preview: {
    port: 4173,
    allowedHosts: [".app.github.dev"],
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // The interpreter is the only WebSocket of the app (ADR-022).
        ws: true,
      },
    },
  },
});
