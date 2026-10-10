import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Vite serves the React app and compiles Tailwind from src/index.css.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Same-origin /api calls in dev reach the local API. The launcher owns process startup.
    proxy: {
      "/api": "http://localhost:8000",
      "/portraits": "http://localhost:8000",
    },
  },
});
