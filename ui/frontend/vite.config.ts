import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies /ask to the FastAPI backend (ui/api.py) so the frontend
// can always call the relative path "/ask" -- same as in the production build,
// where FastAPI serves this app's static bundle directly and /ask is same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/ask": "http://localhost:8502",
    },
  },
  build: {
    outDir: "dist",
  },
});
