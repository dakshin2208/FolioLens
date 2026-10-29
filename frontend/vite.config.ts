import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const proxy = { "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000" };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, host: true, proxy },
  preview: { port: 4173, proxy },
  build: {
    // Fonts must be served as files: the CSP (default-src 'self') blocks data: URIs.
    assetsInlineLimit: 0,
    rollupOptions: {
      output: { manualChunks: { react: ["react", "react-dom", "react-router-dom"], charts: ["recharts"] } },
    },
  },
});
