import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import path from "path";

// NOTE: TanStackRouterVite auto-generates src/routeTree.gen.ts from src/routes/**
// on `npm run dev` / `npm run build`. A hand-written fallback routeTree.gen.ts
// ships in this repo so the app also runs before the generator's first pass.
export default defineConfig({
  plugins: [TanStackRouterVite(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
});
