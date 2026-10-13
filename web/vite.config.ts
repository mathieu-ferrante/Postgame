import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// En développement, l'API tourne sur le service Python (port 8765).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8765" } },
  build: { outDir: "dist", emptyOutDir: true },
  test: { environment: "node" },
});
