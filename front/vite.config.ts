import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En producción el front se sirve DETRÁS del gateway Traefik (mismo origen que la
// API), así que las llamadas a `/api/...` resuelven solas. Para desarrollo local
// con `npm run dev`, se proxean esas mismas rutas al gateway en :80.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:80",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
